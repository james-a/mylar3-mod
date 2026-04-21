# -*- coding: utf-8 -*-
"""Report-only library audit: expected folder (filers.folder_create) vs ComicLocation;
expected filename (helpers.rename_param) vs issues/annuals Location."""

import os

import mylar
from mylar import db, helpers, filers, logger


def _norm_path(p):
    if p is None or str(p).strip() in ("", "None"):
        return ""
    return os.path.normcase(os.path.normpath(str(p).strip()))


def _norm_filename(name):
    if name is None or str(name).strip() in ("", "None"):
        return ""
    return os.path.normcase(str(name).strip())


def _annualize_for_issue(issue_row, from_annuals_table=False):
    if from_annuals_table:
        return "yes"
    loc = issue_row.get("Location") or ""
    if "annual" in str(loc).lower():
        return "yes"
    return None


def run_library_audit():
    """
    Scan all series in `comics` and all issues (plus annuals when enabled).
    Returns a list of row dicts: series, year, comicid, issue, kind, detail
    """
    rows = []
    myDB = db.DBConnection()

    dest = mylar.CONFIG.DESTINATION_DIR
    if dest is None or str(dest).strip() in ("", "None"):
        rows.append(
            {
                "series": "—",
                "year": "—",
                "comicid": "—",
                "issue": "—",
                "kind": "config_error",
                "detail": "DESTINATION_DIR (Comic Location root) is not set in config.",
            }
        )
        return rows

    comics = myDB.select("SELECT * FROM comics ORDER BY ComicSortName COLLATE NOCASE")
    if not comics:
        rows.append(
            {
                "series": "—",
                "year": "—",
                "comicid": "—",
                "issue": "—",
                "kind": "empty_library",
                "detail": "No series found in comics table.",
            }
        )
        return rows

    logger.info("[HOUSEKEEPING] Starting library audit (%s series)", len(comics))

    for comic in comics:
        comic = dict(comic)
        cid = comic["ComicID"]
        cname = comic["ComicName"]
        cyear = comic["ComicYear"] or ""

        try:
            fh = filers.FileHandlers(ComicID=cid)
            if not fh.comic:
                rows.append(
                    {
                        "series": cname,
                        "year": cyear,
                        "comicid": cid,
                        "issue": "—",
                        "kind": "series_error",
                        "detail": "Could not load series row for FileHandlers.",
                    }
                )
                continue

            fc = fh.folder_create()
            if not fc or "comlocation" not in fc:
                rows.append(
                    {
                        "series": cname,
                        "year": cyear,
                        "comicid": cid,
                        "issue": "—",
                        "kind": "folder_error",
                        "detail": "folder_create() did not return a path (check logs).",
                    }
                )
                continue

            expected_dir = fc["comlocation"]
            stored_dir = comic.get("ComicLocation")

            if stored_dir is None or str(stored_dir).strip() in ("", "None"):
                rows.append(
                    {
                        "series": cname,
                        "year": cyear,
                        "comicid": cid,
                        "issue": "—",
                        "kind": "folder_missing_stored",
                        "detail": "ComicLocation empty in DB; expected: %s" % expected_dir,
                    }
                )
            elif _norm_path(stored_dir) != _norm_path(expected_dir):
                rows.append(
                    {
                        "series": cname,
                        "year": cyear,
                        "comicid": cid,
                        "issue": "—",
                        "kind": "folder_mismatch",
                        "detail": "stored: %s | expected: %s"
                        % (stored_dir, expected_dir),
                    }
                )
            else:
                rows.append(
                    {
                        "series": cname,
                        "year": cyear,
                        "comicid": cid,
                        "issue": "—",
                        "kind": "folder_match",
                        "detail": "Matches folder format.",
                    }
                )

            # Issues table
            issuelist = myDB.select(
                "SELECT * FROM issues WHERE ComicID=? ORDER BY Int_IssueNumber",
                [cid],
            )
            for issue in issuelist:
                rows.extend(
                    _audit_issue_file(
                        comic,
                        issue,
                        from_annuals_table=False,
                    )
                )

            if mylar.CONFIG.ANNUALS_ON:
                annlist = myDB.select(
                    "SELECT * FROM annuals WHERE ComicID=? AND NOT Deleted ORDER BY Int_IssueNumber",
                    [cid],
                )
                for ann in annlist:
                    rows.extend(
                        _audit_issue_file(
                            comic,
                            ann,
                            from_annuals_table=True,
                        )
                    )

        except Exception as e:
            logger.exception("[HOUSEKEEPING] Audit failed for %s: %s", cid, e)
            rows.append(
                {
                    "series": cname,
                    "year": cyear,
                    "comicid": cid,
                    "issue": "—",
                    "kind": "series_error",
                    "detail": str(e),
                }
            )

    logger.info("[HOUSEKEEPING] Audit finished (%s rows)", len(rows))
    return rows


def _audit_issue_file(comic, issue, from_annuals_table):
    rows = []
    issue = dict(issue)
    cid = comic["ComicID"]
    cname = comic["ComicName"]
    cyear = comic["ComicYear"] or ""
    loc = issue.get("Location")
    issueno = issue.get("Issue_Number") or issue.get("IssueNumber")
    inum = issueno if issueno is not None else "—"
    iid = issue.get("IssueID")

    if not loc or str(loc).strip() in ("", "None"):
        rows.append(
            {
                "series": cname,
                "year": cyear,
                "comicid": cid,
                "issue": str(inum),
                "kind": "issue_no_location",
                "detail": "No filename in Location (IssueID %s)" % iid,
            }
        )
        return rows

    annualize = _annualize_for_issue(issue, from_annuals_table=from_annuals_table)

    try:
        if issueno is None:
            rows.append(
                {
                    "series": cname,
                    "year": cyear,
                    "comicid": cid,
                    "issue": str(inum),
                    "kind": "file_error",
                    "detail": "Missing Issue_Number (IssueID %s)" % iid,
                }
            )
            return rows

        rp = helpers.rename_param(
            str(cid),
            cname,
            issueno,
            loc,
            comicyear=cyear,
            issueid=iid,
            annualize=annualize,
        )
        if rp is None:
            rows.append(
                {
                    "series": cname,
                    "year": cyear,
                    "comicid": cid,
                    "issue": str(inum),
                    "kind": "file_error",
                    "detail": "rename_param returned None (IssueID %s)" % iid,
                }
            )
            return rows

        expected = rp.get("nfilename")
        if expected is None:
            rows.append(
                {
                    "series": cname,
                    "year": cyear,
                    "comicid": cid,
                    "issue": str(inum),
                    "kind": "file_error",
                    "detail": "rename_param missing nfilename (IssueID %s)" % iid,
                }
            )
            return rows

        if _norm_filename(expected) == _norm_filename(loc):
            kind = "file_match"
            detail = "Matches file format."
        else:
            kind = "file_mismatch"
            detail = "expected: %s | stored: %s" % (expected, loc)

        if from_annuals_table:
            detail += " (annual)"

        rows.append(
            {
                "series": cname,
                "year": cyear,
                "comicid": cid,
                "issue": str(inum),
                "kind": kind,
                "detail": detail,
            }
        )
    except Exception as e:
        logger.exception(
            "[HOUSEKEEPING] rename_param failed %s %s: %s", cid, iid, e
        )
        rows.append(
            {
                "series": cname,
                "year": cyear,
                "comicid": cid,
                "issue": str(inum),
                "kind": "file_error",
                "detail": str(e),
            }
        )

    return rows
