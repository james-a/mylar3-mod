"""
Create local-dev-data/config.ini and mylar.db schema without starting the web UI.
Run from repo root:  python devtools/bootstrap_local_db.py

Does NOT re-run if mylar.db already exists (protects a copied config.ini).
To wipe and recreate: delete local-dev-data/mylar.db (and config.ini if you want
defaults), then run again — or:  MYLAR_FORCE_BOOTSTRAP=1 python devtools/bootstrap_local_db.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(ROOT, "lib"))

DATADIR = os.path.join(ROOT, "local-dev-data")
os.makedirs(DATADIR, exist_ok=True)

DB_PATH = os.path.join(DATADIR, "mylar.db")
_force = os.environ.get("MYLAR_FORCE_BOOTSTRAP", "").strip().lower() in ("1", "true", "yes")
if len(sys.argv) > 1 and sys.argv[1].strip().lower() in ("--force", "-f"):
    _force = True

if os.path.isfile(DB_PATH) and not _force:
    print("[bootstrap_local_db] Skipping — mylar.db already exists:", DB_PATH)
    print("  Your config.ini was not modified.")
    print("  To recreate DB from scratch: delete mylar.db, then run this script again.")
    print("  To force full re-init (overwrites/merges config via Mylar): set MYLAR_FORCE_BOOTSTRAP=1 or pass --force")
    sys.exit(0)

import mylar  # noqa: E402

mylar.PROG_DIR = ROOT
mylar.DATA_DIR = DATADIR
mylar.CONFIG_FILE = os.path.join(DATADIR, "config.ini")
mylar.DB_FILE = os.path.join(DATADIR, "mylar.db")
mylar.MAINTENANCE = False

mylar.initialize(mylar.CONFIG_FILE)
print("[bootstrap_local_db] OK — config and DB initialized.")
print("  Config:", mylar.CONFIG_FILE)
print("  Database:", mylar.DB_FILE)
print(
    "  Full local library (CV import + dummy .cbz + rescan): "
    "python devtools/setup_local_dev_library.py"
)
