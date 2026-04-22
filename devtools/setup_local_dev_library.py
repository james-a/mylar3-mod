# -*- coding: utf-8 -*-
"""
**Optional** scripted import for developers who want dummy .cbz without using the UI.

A normal Mylar install adds series from the search box, which stores ComicID as
the volume id only (e.g. 6811), not "4050-6811". This script must pass the same
form to addComictoDB. Prefer: run ensure_dev_environment (no --with-sample-library),
start the app, and add a couple of series in the web UI, then use that as your
template for what DB and folders look like.

When run, this will:
  1) Remove legacy fake series 4050-999999 if present.
  2) Import volumes via importer.addComictoDB (see DEV_VOLUMES).
  3) Align series folders, write minimal .cbz with ComicInfo.xml, forceRescan.

Requires devtools/bootstrap_local_db.py (mylar.db), [CV] comicvine_api, absolute destination_dir.

Run from repo root:
  python devtools/setup_local_dev_library.py
  python devtools/setup_local_dev_library.py --skip-import
  python devtools/setup_local_dev_library.py --issues-per-series 2
"""
from __future__ import print_function

import argparse
import os
import re
import sqlite3
import sys
import time
import zipfile
from xml.etree import ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATADIR = os.path.join(ROOT, "local-dev-data")
DB_PATH = os.path.join(DATADIR, "mylar.db")

# Comic Vine volume ids (digits only; same as stored in DB after add-by-search)
DEV_VOLUMES = (
    ("5348", "Ninjak (1993)"),
    ("6811", "300 (1998)"),
)

OLD_DUMMY_COMIC_ID = "4050-999999"

# 1x1 transparent PNG (valid CBZ page for ComicTagger / readers)
_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _normalize_comic_id(numeric_or_full):
    """Match add-by-id from the search box: only the volume id string (no 4050- prefix in DB)."""
    return re.sub(r"(?i)^4050-", "", str(numeric_or_full).strip()).strip()


def _remove_dummy_series():
    if not os.path.isfile(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM issues WHERE ComicID=?", (OLD_DUMMY_COMIC_ID,))
        try:
            cur.execute(
                "DELETE FROM annuals WHERE ComicID=?", (OLD_DUMMY_COMIC_ID,)
            )
        except sqlite3.OperationalError:
            pass
        cur.execute("DELETE FROM comics WHERE ComicID=?", (OLD_DUMMY_COMIC_ID,))
        conn.commit()
        print(
            "[setup_local_dev_library] Removed legacy dummy series %s if present."
            % OLD_DUMMY_COMIC_ID
        )
    finally:
        conn.close()


def _comicinfo_xml(comic_row, issue_row):
    """ComicRack / ComicTagger-compatible ComicInfo.xml for a single issue."""
    root = ET.Element("ComicInfo")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")

    def sub(tag, text):
        if text is None:
            return
        el = ET.SubElement(root, tag)
        el.text = str(text)

    series = comic_row["ComicName"]
    num = issue_row["Issue_Number"]
    title = issue_row["IssueName"] or ("Issue %s" % num)
    year = (issue_row["IssueDate"] or "0000-00-00")[:4]
    if year == "0000":
        year = str(comic_row["ComicYear"] or "")
    cv_issue = str(issue_row["IssueID"]).strip()
    notes = (
        "Tagged for Mylar local dev. Comic Vine Issue ID %s "
        "(http://comicvine.gamespot.com/issue/4000-%s/)"
        % (cv_issue, cv_issue)
    )

    sub("Title", title)
    sub("Series", series)
    sub("Number", num)
    sub("Volume", str(comic_row["ComicYear"] or ""))
    sub("Summary", "Dummy placeholder issue for local development.")
    sub("Year", year)
    sub("Notes", notes)
    sub("Writer", "Dev")
    sub("Penciller", "Dev")
    header = '<?xml version="1.0" encoding="utf-8"?>\n'
    return header + ET.tostring(root, encoding="unicode")


def _write_dummy_cbz(target_path, comic_row, issue_row):
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    xml = _comicinfo_xml(comic_row, issue_row)
    with zipfile.ZipFile(
        target_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        zf.writestr("ComicInfo.xml", xml.encode("utf-8"))
        zf.writestr("0000-cover.png", _MINI_PNG)


def _init_mylar():
    sys.path.insert(0, ROOT)
    sys.path.insert(1, os.path.join(ROOT, "lib"))
    config_file = os.environ.get("MYLAR_CONFIG_FILE") or os.path.join(
        DATADIR, "config.ini"
    )
    if not os.path.isfile(config_file):
        print("Missing config:", config_file, file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(DB_PATH):
        print(
            "Missing",
            DB_PATH,
            "— run devtools/bootstrap_local_db.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    import mylar  # noqa: E402

    mylar.PROG_DIR = ROOT
    mylar.DATA_DIR = DATADIR
    mylar.CONFIG_FILE = config_file
    mylar.DB_FILE = DB_PATH
    mylar.MAINTENANCE = False
    mylar.initialize(mylar.CONFIG_FILE)

    api_override = os.environ.get("MYLAR_COMICVINE_API", "").strip()
    if api_override.lower() in ("none", ""):
        api_override = None
    if api_override:
        mylar.CONFIG.COMICVINE_API = api_override

    if (
        not mylar.CONFIG.COMICVINE_API
        or str(mylar.CONFIG.COMICVINE_API).strip().lower() in ("none", "")
    ):
        print(
            "Comic Vine API key missing. Set [CV] comicvine_api in %s "
            "or export MYLAR_COMICVINE_API." % config_file,
            file=sys.stderr,
        )
        sys.exit(1)

    dest = getattr(mylar.CONFIG, "DESTINATION_DIR", None) or ""
    dest = os.path.normpath(str(dest).strip())
    if not os.path.isabs(dest):
        print(
            "[setup_local_dev_library] WARNING: destination_dir is not absolute (%r). "
            "Use an absolute path in [General] destination_dir for reliable Windows paths."
            % dest,
            file=sys.stderr,
        )

    cache_dir = mylar.CONFIG.CACHE_DIR
    if cache_dir and str(cache_dir).strip().lower() not in ("none", ""):
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError as e:
            print(
                "[setup_local_dev_library] Could not create cache_dir %s: %s"
                % (cache_dir, e),
                file=sys.stderr,
            )

    return mylar


def _import_volumes(mylar):
    from mylar import db, importer  # noqa: E402

    for numeric_id, label in DEV_VOLUMES:
        comic_id = _normalize_comic_id(numeric_id)
        myDB = db.DBConnection()
        existing = myDB.selectone(
            "SELECT ComicID, ComicName FROM comics WHERE ComicID=?", [comic_id]
        ).fetchone()
        if existing:
            print(
                "[setup_local_dev_library] Already in DB: %s — %s"
                % (comic_id, existing["ComicName"])
            )
            continue
        print(
            "[setup_local_dev_library] Importing from Comic Vine: %s (%s)…"
            % (label, comic_id)
        )
        try:
            result = importer.addComictoDB(comic_id, mismatch="no")
        except Exception as e:
            print(
                "[setup_local_dev_library] FAILED %s: %s" % (comic_id, e),
                file=sys.stderr,
            )
            continue
        status = result.get("status") if isinstance(result, dict) else result
        print("[setup_local_dev_library] Result for %s: %s" % (comic_id, status))
        time.sleep(2)


def _align_folders(mylar):
    sys.path.insert(0, os.path.join(ROOT, "contrib"))
    from mylar_housekeeping.folder_align import (  # noqa: E402
        align_series_folder_to_format,
    )

    for numeric_id, label in DEV_VOLUMES:
        comic_id = _normalize_comic_id(numeric_id)
        ok, msg = align_series_folder_to_format(comic_id)
        print(
            "[setup_local_dev_library] Folder align %s (%s): %s — %s"
            % (comic_id, label, ok, msg)
        )


def _create_dummy_archives(mylar, issues_per_series):
    from mylar import db, filers, updater  # noqa: E402

    myDB = db.DBConnection()

    for numeric_id, label in DEV_VOLUMES:
        comic_id = _normalize_comic_id(numeric_id)
        comic = myDB.selectone(
            "SELECT * FROM comics WHERE ComicID=?", [comic_id]
        ).fetchone()
        if not comic:
            print(
                "[setup_local_dev_library] Skip dummy files — series not in DB: %s"
                % comic_id
            )
            continue
        comic = dict(comic)
        issues = myDB.select(
            "SELECT * FROM issues WHERE ComicID=? ORDER BY Int_IssueNumber ASC",
            [comic_id],
        )
        if not issues:
            print(
                "[setup_local_dev_library] No issues in DB for %s" % comic_id,
                file=sys.stderr,
            )
            continue

        fh = filers.FileHandlers(ComicID=comic_id)
        count = 0
        for issue in issues:
            if count >= issues_per_series:
                break
            issue = dict(issue)
            issuenum = issue["Issue_Number"]
            ren = fh.rename_file("dummy.cbz", issue=issuenum)
            if not ren:
                print(
                    "[setup_local_dev_library] rename_file failed for %s #%s"
                    % (comic_id, issuenum),
                    file=sys.stderr,
                )
                continue
            dst = ren["destination_dir"]
            nfilename = ren["nfilename"]
            print(
                "[setup_local_dev_library] Writing placeholder CBZ: %s" % dst
            )
            _write_dummy_cbz(dst, comic, issue)
            count += 1

        print(
            "[setup_local_dev_library] forceRescan(%s) …" % comic_id
        )
        updater.forceRescan(comic_id)


def main():
    parser = argparse.ArgumentParser(
        description="Import CV sample series, align folders, add dummy CBZs, rescan."
    )
    parser.add_argument(
        "--skip-remove-dummy",
        action="store_true",
        help="Do not delete legacy 4050-999999 rows.",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Do not call addComictoDB (series must already exist).",
    )
    parser.add_argument(
        "--skip-dummy-files",
        action="store_true",
        help="Import + folder align only; no CBZ creation or rescan.",
    )
    parser.add_argument(
        "--issues-per-series",
        type=int,
        default=1,
        metavar="N",
        help="How many issues per DEV volume get a placeholder CBZ (default: 1).",
    )
    args = parser.parse_args()

    mylar = _init_mylar()

    if not args.skip_remove_dummy:
        _remove_dummy_series()

    if not args.skip_import:
        _import_volumes(mylar)

    _align_folders(mylar)

    if not args.skip_dummy_files:
        _create_dummy_archives(mylar, max(1, args.issues_per_series))

    from mylar import db  # noqa: E402

    myDB = db.DBConnection()
    rows = myDB.select(
        "SELECT ComicID, ComicName, ComicYear, ComicPublisher, Status, ComicLocation "
        "FROM comics ORDER BY ComicSortName"
    )
    print("[setup_local_dev_library] Series in DB (%d):" % len(rows))
    for r in rows:
        print(
            "  %s  %s  (%s)  %s  [%s]"
            % (
                r["ComicID"],
                r["ComicName"],
                r["ComicYear"],
                r["ComicPublisher"] or "?",
                r["Status"],
            )
        )
        try:
            loc = r["ComicLocation"]
        except (KeyError, IndexError):
            loc = None
        if loc:
            print("      -> %s" % loc)


if __name__ == "__main__":
    main()
