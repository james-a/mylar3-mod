"""
Insert one dummy series + issue into local-dev-data/mylar.db for UI smoke tests.
Requires bootstrap_local_db.py to have been run first.
Run:  python devtools/seed_dummy_series.py
"""
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATADIR = os.path.join(ROOT, "local-dev-data")
DB = os.path.join(DATADIR, "mylar.db")

if not os.path.isfile(DB):
    print("Missing", DB, "— run devtools/bootstrap_local_db.py first.", file=sys.stderr)
    sys.exit(1)

conn = sqlite3.connect(DB)
c = conn.cursor()

cid = "4050-999999"
c.execute("SELECT ComicID FROM comics WHERE ComicID=?", (cid,))
if c.fetchone():
    print("[seed_dummy_series] Series already present:", cid)
    conn.close()
    sys.exit(0)

c.execute(
    """INSERT INTO comics (
        ComicID, ComicName, ComicSortName, ComicYear, DateAdded, Status,
        IncludeExtras, Have, Total, ComicPublisher, ComicLocation,
        Type, LastUpdated
    ) VALUES (?, ?, ?, ?, datetime('now'), ?, 0, 0, 1, ?, ?, 'Print', datetime('now'))""",
    (
        cid,
        "Local Dev Test Series",
        "local dev test series",
        "2020",
        "Active",
        "Dev Publisher",
        os.path.join(DATADIR, "comics", "Local Dev Test Series (2020)"),
    ),
)

iid = "999999"
c.execute(
    """INSERT INTO issues (
        IssueID, ComicName, IssueName, Issue_Number, DateAdded, Status, Type,
        ComicID, ReleaseDate, Location, IssueDate, Int_IssueNumber
    ) VALUES (?, ?, ?, ?, datetime('now'), ?, 'Print', ?, ?, ?, ?, ?)""",
    (
        iid,
        "Local Dev Test Series",
        "#1",
        "1",
        "Downloaded",
        cid,
        "2020-01-01",
        "Local Dev Test Series 001 (2020).cbz",
        "2020-01-01",
        1000,
    ),
)

conn.commit()
conn.close()
print("[seed_dummy_series] Inserted dummy series", cid, "and issue", iid)
print("  Comic location (path may not exist on disk):", os.path.join(DATADIR, "comics", "Local Dev Test Series (2020)"))
