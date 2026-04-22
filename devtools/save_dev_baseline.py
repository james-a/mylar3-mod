# -*- coding: utf-8 -*-
"""
Write a point-in-time snapshot of local mylar.db + the configured comic library
folder to dev-baseline/ (sibling to local-dev-data) for rollback testing.

  python devtools/save_dev_baseline.py
"""
from __future__ import print_function

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from configparser import ConfigParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "local-dev-data")
DB_SRC = os.path.join(DATA, "mylar.db")
CONFIG = os.path.join(DATA, "config.ini")
OUT = os.path.join(ROOT, "dev-baseline")
COMICS_NAME = "comics"


def main():
    if not os.path.isfile(CONFIG):
        print("Missing", CONFIG, file=sys.stderr)
        return 1
    if not os.path.isfile(DB_SRC):
        print("Missing", DB_SRC, file=sys.stderr)
        return 1
    p = ConfigParser()
    p.read(CONFIG, encoding="utf-8")
    dest = (p.get("General", "destination_dir", fallback="") or "").strip()
    if not dest or str(dest).lower() == "none":
        print("No [General] destination_dir in config.ini", file=sys.stderr)
        return 1
    if not os.path.isabs(dest):
        print("destination_dir should be absolute:", dest, file=sys.stderr)
        return 1
    if not os.path.isdir(dest):
        print("Comic library path is not a directory:", dest, file=sys.stderr)
        return 1

    os.makedirs(OUT, exist_ok=True)
    com_out = os.path.join(OUT, COMICS_NAME)
    if os.path.exists(com_out):
        shutil.rmtree(com_out)
    db_out = os.path.join(OUT, "mylar.db")
    if os.path.isfile(db_out):
        os.remove(db_out)
    man_out = os.path.join(OUT, "manifest.json")

    shutil.copy2(DB_SRC, db_out)
    shutil.copytree(dest, com_out, symlinks=True)

    manifest = {
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "description": "Dev test baseline (mylar.db + comic files under destination_dir)",
        "paths": {
            "repo": ROOT,
            "source_mylar_db": DB_SRC,
            "source_comics_dir": dest,
        },
    }
    with open(man_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("[save_dev_baseline] Wrote", db_out)
    print("[save_dev_baseline] Wrote", com_out, "(from", dest, ")")
    print("[save_dev_baseline] Wrote", man_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
