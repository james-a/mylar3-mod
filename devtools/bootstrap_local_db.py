"""
Create local-dev-data/config.ini and mylar.db schema without starting the web UI.
Run from repo root:  python devtools/bootstrap_local_db.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(1, os.path.join(ROOT, "lib"))

DATADIR = os.path.join(ROOT, "local-dev-data")
os.makedirs(DATADIR, exist_ok=True)

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
