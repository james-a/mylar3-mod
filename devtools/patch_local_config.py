# -*- coding: utf-8 -*-
"""
Normalize local paths in local-dev-data/config.ini (destination_dir, log_dir, cache_dir).
Intended to run after bootstrap_local_db; leaves unrelated lines untouched.
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATADIR = os.path.join(ROOT, "local-dev-data")
CONFIG_PATH = os.path.join(DATADIR, "config.ini")
COMICS = os.path.normpath(os.path.join(DATADIR, "comics"))
LOGS = os.path.normpath(os.path.join(DATADIR, "logs"))
CACHE = os.path.normpath(os.path.join(DATADIR, "cache"))


def _sub(text, key, value):
    return re.sub(
        r"(?m)^(\s*"
        + re.escape(key)
        + r"\s*=\s*).+$",
        lambda m: m.group(1) + value,
        text,
    )


def main():
    if not os.path.isfile(CONFIG_PATH):
        print(
            "[patch_local_config] No %s — run devtools/bootstrap_local_db.py first."
            % CONFIG_PATH,
            file=sys.stderr,
        )
        return 0

    for d in (COMICS, LOGS, CACHE):
        os.makedirs(d, exist_ok=True)

    with open(CONFIG_PATH, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    orig = text

    text = _sub(text, "destination_dir", COMICS)
    if re.search(r"(?m)^\s*log_dir\s*=", text):
        text = _sub(text, "log_dir", LOGS)
    if re.search(
        r"(?m)^\s*cache_dir\s*=\s*(None)\s*$",
        text,
        re.IGNORECASE,
    ) or re.search(
        r"(?m)^\s*cache_dir\s*=\s*/",
        text,
    ):
        text = _sub(text, "cache_dir", CACHE)

    if text != orig:
        with open(CONFIG_PATH, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(
            "[patch_local_config] Updated paths under %s" % DATADIR
        )
    else:
        print("[patch_local_config] No changes (paths already match or keys missing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
