# -*- coding: utf-8 -*-
"""CBZ ComicInfo validation: Mylar metatag stamp + DB compare (no Comic Vine API).

Only .cbz archives with ComicInfo.xml are checked; CBR and other formats are skipped.
"""

import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from xml.dom.minidom import parseString

import mylar
from mylar import db, logger

from mylar_housekeeping.audit import EXCLUDED_ISSUE_STATUSES

MYLAR_META_TAGGED_RE = re.compile(r"\[MylarMetaTagged:([^\]]+)\]")
MYLAR_META_STAMP_FMT = "[MylarMetaTagged:{ts}]"
ISSUE_ID_IN_NOTES_RE = re.compile(r"(?:CVDB|Issue ID)[^0-9]*(\d+)", re.I)
COMICINFO_NAMES = frozenset({"comicinfo.xml"})


def is_cbz_path(path):
    if not path or str(path).strip() in ("", "None"):
        return False
    return str(path).lower().endswith(".cbz")


def extract_mylar_tagged_date(notes):
    if not notes:
        return None
    m = MYLAR_META_TAGGED_RE.search(str(notes))
    return m.group(1) if m else None


def parse_issue_id_from_notes(notes):
    if not notes or str(notes) in ("None", ""):
        return None
    m = ISSUE_ID_IN_NOTES_RE.search(str(notes))
    if m and m.group(1).isdigit():
        return m.group(1)
    return None


def _norm_text(value):
    if value is None or str(value).strip() in ("", "None"):
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_series_name(name):
    s = _norm_text(name)
    s = re.sub(r"\s*\(\d{4}\)\s*$", "", s).strip()
    return s


def _norm_issue_number(value):
    if value is None or str(value).strip() in ("", "None"):
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"^#+", "", s)
    s = re.sub(r"^0+(?=\d)", "", s)
    return s


def _comicinfo_member_name(name):
    base = os.path.basename(name.replace("\\", "/")).lower()
    return base in COMICINFO_NAMES


def read_comicinfo_from_cbz(cbz_path):
    """
    Read ComicInfo.xml from a CBZ. Returns dict of key fields or None if not CBZ / no XML.
    """
    if not is_cbz_path(cbz_path) or not os.path.isfile(cbz_path):
        return None
    try:
        with zipfile.ZipFile(cbz_path, "r") as zf:
            xml_name = None
            for name in zf.namelist():
                if _comicinfo_member_name(name):
                    xml_name = name
                    break
            if not xml_name:
                return None
            raw = zf.read(xml_name)
    except (OSError, zipfile.BadZipFile) as e:
        logger.fdebug("[CBZ-META] Unreadable archive %s: %s", cbz_path, e)
        return None

    try:
        dom = parseString(raw)
    except Exception as e:
        logger.fdebug("[CBZ-META] Invalid ComicInfo.xml in %s: %s", cbz_path, e)
        return None

    fields = {}
    for tag in (
        "Title",
        "Series",
        "Number",
        "Volume",
        "Notes",
        "Web",
        "Year",
    ):
        fields[tag.lower()] = None
        for node in dom.getElementsByTagName(tag):
            if node.firstChild and node.firstChild.wholeText is not None:
                fields[tag.lower()] = node.firstChild.wholeText.strip()
                break
    return fields


def apply_mylar_metatag_stamp(cbz_path):
    """
    Append or replace [MylarMetaTagged:ISO8601Z] in ComicInfo Notes. CBZ only.
    Returns True on success.
    """
    if not is_cbz_path(cbz_path) or not os.path.isfile(cbz_path):
        return False

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = MYLAR_META_STAMP_FMT.format(ts=ts)

    def _mutate_xml(xml_bytes):
        dom = parseString(xml_bytes)
        for root in dom.getElementsByTagName("ComicInfo"):
            notes_nodes = root.getElementsByTagName("Notes")
            if notes_nodes:
                node = notes_nodes[0]
                old = (
                    node.firstChild.wholeText
                    if node.firstChild and node.firstChild.wholeText
                    else ""
                )
            else:
                node = dom.createElement("Notes")
                root.appendChild(node)
                old = ""
            cleaned = MYLAR_META_TAGGED_RE.sub("", old).strip()
            new_notes = ("%s %s" % (cleaned, stamp)).strip() if cleaned else stamp
            while node.firstChild:
                node.removeChild(node.firstChild)
            node.appendChild(dom.createTextNode(new_notes))
        return dom.toxml(encoding="utf-8")

    return _rewrite_comicinfo_in_cbz(cbz_path, _mutate_xml)


def _rewrite_comicinfo_in_cbz(cbz_path, mutator_func):
    cache_dir = getattr(mylar.CONFIG, "CACHE_DIR", None) or mylar.PROG_DIR
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".cbz", dir=cache_dir)
        os.close(fd)
        found = False
        with zipfile.ZipFile(cbz_path, "r") as zin:
            with zipfile.ZipFile(tmp_path, "w") as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if _comicinfo_member_name(item.filename):
                        new_data = mutator_func(data)
                        if isinstance(new_data, str):
                            new_data = new_data.encode("utf-8")
                        data = new_data
                        found = True
                    zout.writestr(item, data)
        if not found:
            if tmp_path and os.path.isfile(tmp_path):
                os.remove(tmp_path)
            return False
        perms = os.stat(cbz_path).st_mode
        shutil.move(tmp_path, cbz_path)
        os.chmod(cbz_path, perms)
        tmp_path = None
        return True
    except Exception as e:
        logger.warn("[CBZ-META] Failed to update ComicInfo in %s: %s", cbz_path, e)
        return False
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def resolve_issue_filepath(comic_location, location, comic_id):
    """Resolve on-disk path for an issue file (primary + secondary folder)."""
    if not location or str(location).strip() in ("", "None"):
        return None
    if not comic_location or str(comic_location).strip() in ("", "None"):
        return None
    loc = str(location).strip()
    comic_loc = str(comic_location).strip()
    primary = os.path.join(comic_loc, loc)
    if os.path.isfile(primary):
        return primary
    if mylar.CONFIG.MULTIPLE_DEST_DIRS:
        try:
            multi = mylar.CONFIG.MULTIPLE_DEST_DIRS
            if multi and str(multi) not in ("", "None"):
                base = os.path.basename(comic_loc.rstrip(os.sep))
                secondary = os.path.join(multi, base, loc)
                if os.path.isfile(secondary):
                    return secondary
                from mylar import filers

                ff = filers.FileHandlers(ComicID=str(comic_id))
                sec = ff.secondary_folders(comic_loc)
                if sec:
                    candidate = os.path.join(sec, loc)
                    if os.path.isfile(candidate):
                        return candidate
        except Exception:
            logger.exception("[CBZ-META] secondary path lookup failed")
    return primary if os.path.isfile(primary) else None


def compare_cbz_metadata(comic, issue, filepath):
    """
    Compare CBZ ComicInfo to Mylar DB row. CBZ + ComicInfo.xml only.

    Returns dict: ok, status, mylar_tagged, errors, warnings, skipped_reason.
    """
    result = {
        "ok": True,
        "status": "ok",
        "mylar_tagged": None,
        "errors": [],
        "warnings": [],
        "skipped_reason": None,
    }
    if not is_cbz_path(filepath):
        result["ok"] = True
        result["status"] = "skipped_non_cbz"
        result["skipped_reason"] = "Not a CBZ file"
        return result

    meta = read_comicinfo_from_cbz(filepath)
    if meta is None:
        result["ok"] = False
        result["status"] = "no_comicinfo"
        result["errors"].append("No ComicInfo.xml")
        return result

    notes = meta.get("notes")
    result["mylar_tagged"] = extract_mylar_tagged_date(notes)
    if not result["mylar_tagged"]:
        result["ok"] = False
        result["status"] = "never_mylar_tagged"
        result["errors"].append("Never metatagged in Mylar")

    expected_issue_id = str(issue.get("IssueID") or "").strip()
    notes_issue_id = parse_issue_id_from_notes(notes)
    if notes_issue_id and expected_issue_id and notes_issue_id != expected_issue_id:
        result["ok"] = False
        result["status"] = "wrong_issue_id"
        result["errors"].append("ID mismatch")
    elif expected_issue_id and not notes_issue_id:
        result["warnings"].append("No CV issue ID found")

    db_series = _norm_series_name(comic.get("ComicName"))
    meta_series = _norm_series_name(meta.get("series"))
    if db_series and meta_series and db_series != meta_series:
        result["ok"] = False
        if result["status"] == "ok":
            result["status"] = "field_mismatch"
        result["errors"].append("Series mismatch")

    db_num = _norm_issue_number(issue.get("Issue_Number"))
    meta_num = _norm_issue_number(meta.get("number"))
    if db_num and meta_num and db_num != meta_num:
        result["ok"] = False
        if result["status"] == "ok":
            result["status"] = "field_mismatch"
        result["errors"].append("Issue number mismatch")

    db_title = _norm_text(issue.get("IssueName"))
    meta_title = _norm_text(meta.get("title"))
    if db_title and meta_title and db_title != meta_title:
        result["warnings"].append("Title differs")

    if result["ok"] and result["status"] == "ok":
        result["status"] = "ok"
    return result


def _issues_for_series_audit(myDB, comic_id):
    rows = []
    for row in myDB.select(
        "SELECT * FROM issues WHERE ComicID=? ORDER BY Int_IssueNumber", [comic_id]
    ):
        rows.append(dict(row))
    if mylar.CONFIG.ANNUALS_ON:
        for row in myDB.select(
            "SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted "
            "ORDER BY Int_IssueNumber",
            [comic_id],
        ):
            rows.append(dict(row))
    return rows


def audit_series_cbz_metadata(comic_id):
    """
    Audit CBZ ComicInfo for one series. Returns issues dict keyed by IssueID + summary.
    """
    comic_id = str(comic_id).strip()
    myDB = db.DBConnection()
    comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [comic_id]).fetchone()
    if not comic:
        return {
            "issues": {},
            "summary": {"error": "Series not found"},
        }
    comic = dict(comic)
    comic_location = comic.get("ComicLocation")

    issues_out = {}
    summary = {
        "checked_cbz": 0,
        "failed": 0,
        "passed": 0,
        "skipped_non_cbz": 0,
        "skipped_status": 0,
        "skipped_no_file": 0,
    }

    for issue in _issues_for_series_audit(myDB, comic_id):
        issue = dict(issue)
        iid = str(issue.get("IssueID") or "").strip()
        if not iid:
            continue
        st = (issue.get("Status") or "").strip()
        if st in EXCLUDED_ISSUE_STATUSES:
            summary["skipped_status"] += 1
            continue

        location = issue.get("Location")
        filepath = resolve_issue_filepath(comic_location, location, comic_id)

        if not filepath or not os.path.isfile(filepath):
            summary["skipped_no_file"] += 1
            if st in ("Downloaded", "Archived"):
                issues_out[iid] = {
                    "ok": False,
                    "status": "missing_file",
                    "mylar_tagged": None,
                    "errors": ["File not found"],
                    "warnings": [],
                }
                summary["failed"] += 1
            continue

        if not is_cbz_path(filepath):
            summary["skipped_non_cbz"] += 1
            continue

        summary["checked_cbz"] += 1
        cmp_result = compare_cbz_metadata(comic, issue, filepath)
        issues_out[iid] = cmp_result
        if cmp_result.get("ok"):
            summary["passed"] += 1
        else:
            summary["failed"] += 1

    return {"issues": issues_out, "summary": summary}
