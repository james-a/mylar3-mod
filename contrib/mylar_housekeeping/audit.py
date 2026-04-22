# -*- coding: utf-8 -*-
"""Library housekeeping audit: one row per series with pass/fail checks.

v1: three result lines per row — series folder, issue files (CBZ + rename
helpers; Archived fails; Skipped/Wanted/Snatched/Ignored ignored), and
directory-level metadata assets (config-driven, non-empty files).

**Refresh series** on the housekeeping page runs the full background pipeline
(see `housekeepingSeriesRefresh` in `webserve`)."""

import os

import mylar
from mylar import db, helpers, filers, logger

# Issues excluded from the file-format / CBZ check (not expected on disk in library).
EXCLUDED_ISSUE_STATUSES = frozenset(
    ("Skipped", "Wanted", "Snatched", "Ignored")
)

_DISPLAY_EMPTY = {
    "publisher": "—",
    "status": "—",
}


def _display_fields_from_havetotal(row):
    """Map havetotals() row fields to publisher/status display."""
    if not row:
        return dict(_DISPLAY_EMPTY)
    return {
        "publisher": row.get("ComicPublisher") or "—",
        "status": row.get("Status") or "—",
    }


def _merge_display(row, havetotal):
    row = dict(row)
    row.update(_display_fields_from_havetotal(havetotal))
    return row


def _dedupe_by_comicid(rows):
    seen = set()
    out = []
    for r in rows:
        cid = str(r.get("comicid", "")).strip()
        if cid in ("", "—", "None"):
            out.append(r)
            continue
        if cid in seen:
            continue
        seen.add(cid)
        out.append(r)
    return out


def sanitize_rows_for_json(rows):
    out = []
    for r in rows:
        if hasattr(r, "keys"):
            r = dict(r)
        o = {}
        for k, v in r.items():
            if v is None:
                o[k] = ""
            elif isinstance(v, bool):
                o[k] = v
            elif isinstance(v, (int, float)):
                o[k] = v
            else:
                o[k] = str(v)
        out.append(o)
    return out


def _norm_filename(name):
    if name is None or str(name).strip() in ("", "None"):
        return ""
    return os.path.normcase(str(name).strip())


def _audit_issue_metrics(comic, issue, from_annuals_table):
    issue = dict(issue)
    loc = issue.get("Location")
    issueno = issue.get("Issue_Number") or issue.get("IssueNumber")
    iid = issue.get("IssueID")

    annualize = "yes" if from_annuals_table else None
    if annualize is None and loc and "annual" in str(loc).lower():
        annualize = "yes"

    if not loc or str(loc).strip() in ("", "None"):
        return {
            "no_location": True,
            "path_mismatch": False,
            "file_error": False,
        }

    if issueno is None:
        return {
            "no_location": False,
            "path_mismatch": False,
            "file_error": True,
        }

    try:
        rp = helpers.rename_param(
            str(comic["ComicID"]),
            comic["ComicName"],
            issueno,
            loc,
            comicyear=comic.get("ComicYear") or "",
            issueid=iid,
            annualize=annualize if annualize else None,
        )
        if rp is None or rp.get("nfilename") is None:
            return {
                "no_location": False,
                "path_mismatch": False,
                "file_error": True,
            }
        expected = rp.get("nfilename")
        path_mismatch = _norm_filename(expected) != _norm_filename(loc)
        return {
            "no_location": False,
            "path_mismatch": path_mismatch,
            "file_error": False,
        }
    except Exception:
        logger.exception(
            "[HOUSEKEEPING] rename_param failed %s %s", comic.get("ComicID"), iid
        )
        return {
            "no_location": False,
            "path_mismatch": False,
            "file_error": True,
        }


def _issue_files_pass(comic, issues_list, from_annuals_table=False):
    """
    True if there is no failing in-scope issue.
    Excluded statuses are skipped. Archived always fails.
    Otherwise require .cbz and rename match.
    """
    for issue in issues_list:
        issue = dict(issue)
        st = (issue.get("Status") or "").strip()
        if st in EXCLUDED_ISSUE_STATUSES:
            continue
        if st == "Archived":
            return False
        loc = issue.get("Location")
        if not loc or str(loc).strip() in ("", "None"):
            return False
        if not str(loc).lower().endswith(".cbz"):
            return False
        m = _audit_issue_metrics(comic, issue, from_annuals_table=from_annuals_table)
        if m["file_error"] or m["path_mismatch"] or m["no_location"]:
            return False
    return True


def _issue_files_pass_with_annuals(comic, myDB, cid):
    issues_list = myDB.select(
        "SELECT * FROM issues WHERE ComicID=? ORDER BY Int_IssueNumber", [cid]
    )
    if not _issue_files_pass(comic, issues_list):
        return False
    if mylar.CONFIG.ANNUALS_ON:
        ann = myDB.select(
            "SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted "
            "ORDER BY Int_IssueNumber",
            [cid],
        )
        if not _issue_files_pass(comic, ann, from_annuals_table=True):
            return False
    return True


def _series_folder_pass(comic, fc):
    from mylar_housekeeping.folder_align import _paths_equivalent, _resolve_expected_path

    stored = comic.get("ComicLocation")
    if not stored or str(stored).strip() in ("", "None"):
        return False
    if not fc or "comlocation" not in fc:
        return False
    try:
        stored_norm = os.path.abspath(os.path.normpath(str(stored).strip()))
    except (OSError, TypeError, ValueError):
        return False
    expected = _resolve_expected_path(fc)
    if not _paths_equivalent(stored_norm, expected):
        return False
    if not os.path.isdir(stored_norm):
        return False
    return True


def _metadata_pass(comic):
    """Directory-level sidecar files: presence + non-empty, per current config."""
    required = []
    if mylar.CONFIG.SERIES_METADATA_LOCAL:
        required.append("series.json")
    if mylar.CONFIG.CVINFO:
        required.append("cvinfo")
    if mylar.CONFIG.COMIC_COVER_LOCAL:
        required.append("cover.jpg")
    if mylar.CONFIG.COVER_FOLDER_LOCAL:
        required.append("folder.jpg")
    if not required:
        return True
    loc = comic.get("ComicLocation")
    if not loc or str(loc).strip() in ("", "None"):
        return False
    loc = str(loc).strip()
    if not os.path.isdir(loc):
        return False
    for name in required:
        p = os.path.join(loc, name)
        try:
            if not os.path.isfile(p) or os.path.getsize(p) == 0:
                return False
        except OSError:
            return False
    return True


def _result_label(passed):
    return "Pass" if passed else "Fail"


def run_library_audit():
    """
    One row per series in the library (same sources as Manage Comics), with
    three pass/fail checks each.

    Row keys include havetotals-style display fields, results_line (multi-line
    text), and check_series_folder / check_issue_files / check_metadata (bool).
    """
    rows = []
    myDB = db.DBConnection()

    dest = mylar.CONFIG.DESTINATION_DIR
    if dest is None or str(dest).strip() in ("", "None"):
        row = {
            "series": "—",
            "comicid": "—",
            "result_series_folder": "",
            "result_issue_files": "",
            "result_metadata": "",
            "results_line": "Set Comic Location root (destination_dir) in config before auditing.",
            "have_display": "—",
            "latest_display": "—",
            "ComicImage": "cache/placeholder.jpg",
            "recentstatus": "—",
            "row_class": "config",
            "kind": "config_error",
        }
        row.update(_DISPLAY_EMPTY)
        rows.append(row)
        return rows

    hlist = helpers.havetotals()
    if not hlist:
        row = {
            "series": "—",
            "comicid": "—",
            "result_series_folder": "",
            "result_issue_files": "",
            "result_metadata": "",
            "results_line": "No series in the library database.",
            "have_display": "—",
            "latest_display": "—",
            "ComicImage": "cache/placeholder.jpg",
            "recentstatus": "—",
            "row_class": "config",
            "kind": "empty_library",
        }
        row.update(_DISPLAY_EMPTY)
        rows.append(row)
        return rows

    logger.info("[HOUSEKEEPING] Starting library audit (%s series)", len(hlist))

    for hr in hlist:
        hrow = dict(hr)
        cid = hrow["ComicID"]
        cname = hrow.get("ComicName") or ""
        cyear = hrow.get("ComicYear") or ""

        comic = myDB.selectone("SELECT * FROM comics WHERE ComicID=?", [cid]).fetchone()
        if not comic:
            continue
        comic = dict(comic)

        last_up = comic.get("LastUpdated")
        last_disp = (
            str(last_up).strip()[:19]
            if last_up and str(last_up).strip() not in ("", "None")
            else "—"
        )

        try:
            fh = filers.FileHandlers(ComicID=cid)
            if not fh.comic:
                ok_sf = False
                ok_if = False
                ok_md = False
            else:
                fc = fh.folder_create()
                ok_sf = _series_folder_pass(comic, fc)
                ok_if = _issue_files_pass_with_annuals(comic, myDB, cid)
                ok_md = _metadata_pass(comic)
        except Exception as e:
            logger.exception("[HOUSEKEEPING] Audit failed for %s: %s", cid, e)
            row = {
                "series": cname,
                "year": cyear,
                "comicid": cid,
                "last_refreshed": last_disp,
                "result_series_folder": "Fail",
                "result_issue_files": "Fail",
                "result_metadata": "Fail",
                "results_line": "Series folder: Fail\nIssue files: Fail\nMetadata: Fail",
                "check_series_folder": False,
                "check_issue_files": False,
                "check_metadata": False,
                "have_display": "%s/%s"
                % (hrow.get("haveissues", 0), hrow.get("totalissues", 0)),
                "row_class": "files",
                "kind": "series_error",
            }
            rows.append(_enrich_housekeeping_row(row, hrow))
            continue

        rsf = _result_label(ok_sf)
        rif = _result_label(ok_if)
        rmd = _result_label(ok_md)
        line = "Series folder: %s\nIssue files: %s\nMetadata: %s" % (rsf, rif, rmd)

        any_fail = not (ok_sf and ok_if and ok_md)
        row = {
            "series": cname,
            "year": cyear,
            "comicid": cid,
            "last_refreshed": last_disp,
            "result_series_folder": rsf,
            "result_issue_files": rif,
            "result_metadata": rmd,
            "results_line": line,
            "check_series_folder": ok_sf,
            "check_issue_files": ok_if,
            "check_metadata": ok_md,
            "row_class": "files" if any_fail else "ok",
            "kind": "ok" if not any_fail else "needs_attention",
        }
        rows.append(_enrich_housekeeping_row(row, hrow))

    rows = _dedupe_by_comicid(rows)
    logger.info("[HOUSEKEEPING] Audit finished (%s series rows)", len(rows))
    return rows


def _enrich_housekeeping_row(row, hrow):
    """Add Manage Comics–style display keys from a havetotals() record."""
    row = _merge_display(row, hrow)
    hrow = dict(hrow) if hrow else {}

    row["comic_name_link"] = "%s (%s)" % (hrow.get("ComicName", ""), hrow.get("ComicYear", ""))
    row["ComicImage"] = hrow.get("ComicImage", "cache/%s.jpg" % row.get("comicid", ""))
    row["LatestIssue"] = hrow.get("LatestIssue", "—")
    row["LatestDate"] = hrow.get("LatestDate", "—")
    row["latest_display"] = "%s (%s)" % (
        hrow.get("LatestIssue", "—"),
        hrow.get("LatestDate", "—"),
    )
    row["recentstatus"] = hrow.get("recentstatus", "—")
    row["ComicName"] = hrow.get("ComicName", "")
    row["ComicYear"] = hrow.get("ComicYear", "")
    row["haveissues"] = hrow.get("haveissues", 0)
    row["totalissues"] = hrow.get("totalissues", 0)
    row["percent"] = hrow.get("percent", 0)
    row["have_display"] = "%s/%s" % (
        hrow.get("haveissues", 0),
        hrow.get("totalissues", 0),
    )
    row["DateAdded"] = hrow.get("DateAdded", "—")
    return row
