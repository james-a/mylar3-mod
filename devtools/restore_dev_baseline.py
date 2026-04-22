# -*- coding: utf-8 -*-
"""
Restore from dev-baseline/ created by save_dev_baseline.py. Overwrites
local-dev-data/mylar.db and the configured destination_dir (comic library).

Stop the Mylar process first or SQLite may be busy on Windows.

  python devtools/restore_dev_baseline.py
"""
from __future__ import print_function

import os
import shutil
import sys
from configparser import ConfigParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "local-dev-data")
DB_DST = os.path.join(DATA, "mylar.db")
CONFIG = os.path.join(DATA, "config.ini")
BASE = os.path.join(ROOT, "dev-baseline")
DB_BAK = os.path.join(BASE, "mylar.db")
COM_BAK = os.path.join(BASE, "comics")
MAN = os.path.join(BASE, "manifest.json")


def main():
    if not os.path.isfile(DB_BAK) or not os.path.isdir(COM_BAK):
        print(
            "No baseline found. Run devtools/save_dev_baseline.py first. Expected:"
            f"\n  {DB_BAK}\n  {COM_BAK}",
            file=sys.stderr,
        )
        return 1
    if not os.path.isfile(CONFIG):
        print("Missing", CONFIG, file=sys.stderr)
        return 1
    p = ConfigParser()
    p.read(CONFIG, encoding="utf-8")
    dest = (p.get("General", "destination_dir", fallback="") or "").strip()
    if not dest or not os.path.isabs(dest):
        print("Invalid [General] destination_dir in config.ini", file=sys.stderr)
        return 1
    safe_root = os.path.normcase(
        os.path.abspath(os.path.join(ROOT, "local-dev-data")) + os.sep
    )
    if not os.path.normcase(os.path.abspath(dest) + os.sep).startswith(safe_root):
        print(
            "Refusing: destination_dir must be under local-dev-data/ for this script.",
            dest,
            file=sys.stderr,
        )
        return 1
    if os.path.isfile(DB_DST):
        try:
            os.remove(DB_DST)
        except OSError as e:
            print("Could not remove mylar.db (is Mylar running?):", e, file=sys.stderr)
            return 1
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    shutil.copy2(DB_BAK, DB_DST)
    shutil.copytree(COM_BAK, dest, symlinks=True)
    print("[restore_dev_baseline] Restored", DB_DST)
    print("[restore_dev_baseline] Restored", dest, "from", COM_BAK)
    if os.path.isfile(MAN):
        print("[restore_dev_baseline] manifest:", MAN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
