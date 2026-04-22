# -*- coding: utf-8 -*-
"""Move a series folder on disk to match filers.folder_create() and update ComicLocation."""

import os
import shutil

import mylar
from mylar import db, filers, logger


def _paths_equivalent(a, b):
    if not a or not b:
        return False
    a, b = os.path.normpath(str(a).strip()), os.path.normpath(str(b).strip())
    if os.name == "nt":
        return os.path.normcase(a) == os.path.normcase(b)
    return a == b


def _resolve_expected_path(fc):
    """
    folder_create()['comlocation'] can be root-relative on Windows (e.g. \\comics\\...),
    which resolves to the wrong tree. Anchor the tail under DESTINATION_DIR.
    """
    dest = mylar.CONFIG.DESTINATION_DIR
    if not dest or str(dest).strip() in ("", "None"):
        return os.path.normpath(fc["comlocation"])
    dest_root = os.path.abspath(os.path.normpath(str(dest).strip()))
    expected = os.path.normpath(str(fc["comlocation"]).strip())

    if expected.lower().startswith(dest_root.lower()):
        return expected

    rest = expected.replace("/", os.sep).lstrip(os.sep).split(os.sep)
    rest = [p for p in rest if p]
    base_name = os.path.basename(dest_root.rstrip(os.sep))
    if rest and base_name and rest[0].lower() == base_name.lower():
        rest = rest[1:]
    fixed = os.path.normpath(os.path.join(dest_root, *rest)) if rest else dest_root
    logger.fdebug(
        "[HOUSEKEEPING][FOLDER] Resolved comlocation %r -> %r", fc["comlocation"], fixed
    )
    return fixed


def align_series_folder_to_format(comic_id):
    """
    If ComicLocation differs from folder_create()['comlocation'], move the directory
    and update the comics row. Returns (ok: bool, message: str).
    """
    comic_id = str(comic_id).strip()
    myDB = db.DBConnection()
    comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [comic_id]).fetchone()
    if not comic:
        return False, "Series not found"
    comic = dict(comic)
    stored = comic.get("ComicLocation")
    if not stored or str(stored).strip() in ("", "None"):
        return False, "ComicLocation empty; set a path before moving"

    fh = filers.FileHandlers(ComicID=comic_id)
    if not fh.comic:
        return False, "Could not load series for file handlers"
    fc = fh.folder_create()
    if not fc or "comlocation" not in fc:
        return False, "Could not compute expected folder path"

    stored_norm = os.path.abspath(os.path.normpath(str(stored).strip()))
    expected = _resolve_expected_path(fc)

    if _paths_equivalent(stored_norm, expected):
        return True, "already aligned"

    if not os.path.isdir(stored_norm):
        logger.warn(
            "[HOUSEKEEPING][FOLDER] ComicLocation is not a directory: %s", stored_norm
        )
        return False, "stored path is not a directory"

    if os.path.exists(expected) and not _paths_equivalent(stored_norm, expected):
        logger.warn(
            "[HOUSEKEEPING][FOLDER] Target path already exists; not overwriting: %s",
            expected,
        )
        return False, "target path exists (collision)"

    parent = os.path.dirname(expected)
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as e:
        logger.exception("[HOUSEKEEPING][FOLDER] makedirs %s", parent)
        return False, str(e)

    try:
        shutil.move(stored_norm, expected)
    except OSError as e:
        logger.exception(
            "[HOUSEKEEPING][FOLDER] move %s -> %s", stored_norm, expected
        )
        return False, str(e)

    try:
        myDB.upsert("comics", {"ComicLocation": expected}, {"ComicID": comic_id})
    except Exception as e:
        logger.exception("[HOUSEKEEPING][FOLDER] DB update failed")
        return False, str(e)

    logger.info(
        "[HOUSEKEEPING][FOLDER] Moved series folder to match folder format: %s",
        expected,
    )
    return True, "moved"
