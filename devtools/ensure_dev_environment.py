# -*- coding: utf-8 -*-
"""
One-step local dev environment for Mylar3:

  1) Create .venv in the repo (if missing) and re-run with that interpreter
  2) pip install -r requirements.txt
  3) devtools/patch_local_config.py (if config exists)
  4) devtools/bootstrap_local_db.py

  By default this does *not* import series or create dummy .cbz files. Add
  series through the web UI (same as production) so the DB and URLs match
  a real use case. Optional scripted sample data: use --with-sample-library.

  --rebaseline: stop any local Mylar on this datadir, delete
  local-dev-data/mylar.db, clear the dev destination_dir under
  local-dev-data/, then venv + pip + bootstrap + patch (no sample import
  unless you also pass --with-sample-library).

Run from repository root:  python devtools/ensure_dev_environment.py

From Cursor/VS Code: use the task "Mylar: Full dev setup" (no manual CLI).
"""
from __future__ import print_function

import argparse
import os
import shutil
import subprocess
import sys
import time

from configparser import ConfigParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV = os.path.join(ROOT, ".venv")

IS_WIN = os.name == "nt"


def _venv_python():
    if IS_WIN:
        p = os.path.join(VENV, "Scripts", "python.exe")
    else:
        p = os.path.join(VENV, "bin", "python3")
        if not os.path.isfile(p):
            p = os.path.join(VENV, "bin", "python")
    return p


def _in_expected_venv():
    exe = os.path.normcase(os.path.abspath(sys.executable))
    vpy = _venv_python()
    if not os.path.isfile(vpy):
        return False
    return os.path.normcase(exe) == os.path.normcase(
        os.path.abspath(vpy)
    )


def _create_venv():
    print(
        "[ensure_dev_environment] Creating virtualenv at .venv (using %s)…"
        % sys.executable
    )
    rc = subprocess.call(
        [sys.executable, "-m", "venv", VENV], cwd=ROOT
    )
    if rc != 0:
        print(
            "[ensure_dev_environment] venv failed; is Python 3.8+ available?",
            file=sys.stderr,
        )
        return False
    return True


def _run(py, args, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    cmd = [py] + args
    print("[ensure_dev_environment] " + " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT, env=e)


def _rebaseline_local_state():
    """
    Wipe the dev SQLite DB and on-disk files under the repo's local dev library
    path only (never an arbitrary user directory).

    Returns:
        bool: True if rebaseline step completed; False if mylar.db could not be
        removed (e.g. locked) so the caller should abort.
    """
    if IS_WIN:
        pss = os.path.join(ROOT, "devtools", "stop_mylar_dev_instance.ps1")
        if os.path.isfile(pss):
            subprocess.call(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    pss,
                ],
                cwd=ROOT,
            )
            time.sleep(0.4)

    local_data = os.path.join(ROOT, "local-dev-data")
    local_data_nc = os.path.normcase(os.path.abspath(local_data))
    db = os.path.join(local_data, "mylar.db")
    if os.path.isfile(db):
        try:
            os.remove(db)
        except OSError as e:
            in_use = getattr(e, "winerror", None) == 32
            if not in_use and hasattr(e, "errno") and e.errno is not None:
                in_use = e.errno in (11, 16)  # EAGAIN, EBUSY
            if in_use or isinstance(e, PermissionError):
                print(
                    "[ensure_dev_environment] Cannot delete mylar.db — file is in use. "
                    "Stop the Mylar dev server (and any other app using the DB), then "
                    "run this task again.",
                    file=sys.stderr,
                )
            else:
                print(
                    "[ensure_dev_environment] Cannot remove %s: %s" % (db, e),
                    file=sys.stderr,
                )
            return False
        print(
            "[ensure_dev_environment] Rebaseline: removed %s" % db,
            file=sys.stderr,
        )

    cfg_path = os.path.join(local_data, "config.ini")
    if not os.path.isfile(cfg_path):
        print(
            "[ensure_dev_environment] Rebaseline: no %s — bootstrap will create defaults."
            % cfg_path
        )
        return True
    p = ConfigParser()
    p.read(cfg_path, encoding="utf-8")
    if not p.has_section("General"):
        return True
    dest = (p.get("General", "destination_dir", fallback="") or "").strip()
    if not dest or str(dest).lower() == "none":
        return True
    dest = os.path.normpath(dest)
    if not os.path.isabs(dest) or not os.path.isdir(dest):
        return True
    dest_nc = os.path.normcase(os.path.abspath(dest))
    if not dest_nc.startswith(local_data_nc + os.sep):
        print(
            "[ensure_dev_environment] Rebaseline: skip clearing destination_dir "
            "(not under local-dev-data): %s" % dest,
            file=sys.stderr,
        )
        return True
    n = 0
    for name in os.listdir(dest):
        fp = os.path.join(dest, name)
        try:
            if os.path.isdir(fp):
                shutil.rmtree(fp)
            else:
                os.remove(fp)
            n += 1
        except OSError as e:
            print(
                "[ensure_dev_environment] Rebaseline: could not remove %r: %s"
                % (fp, e),
                file=sys.stderr,
            )
    print(
        "[ensure_dev_environment] Rebaseline: cleared %d top-level item(s) in %s"
        % (n, dest),
    )
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rebaseline",
        action="store_true",
        help="Wipe local-dev mylar.db + dev library folder, then full setup.",
    )
    ap.add_argument(
        "--with-sample-library",
        action="store_true",
        help="Run setup_local_dev_library.py (CV import + dummy CBZ). Default is off; prefer adding series in the UI.",
    )
    ap.add_argument(
        "--no-venv",
        action="store_true",
        help="Do not create/use .venv; use the current python (CI/containers).",
    )
    args, _ = ap.parse_known_args()

    # Re-run with venv python (Windows-safe; avoid os.exec* differences)
    if not args.no_venv and not _in_expected_venv():
        if not os.path.isfile(_venv_python()):
            if not _create_venv():
                return 1
        vpy = _venv_python()
        rc = subprocess.call(
            [vpy, os.path.abspath(__file__)] + sys.argv[1:],
            cwd=ROOT,
            env=os.environ,
        )
        return rc

    py = sys.executable

    if args.rebaseline and not _rebaseline_local_state():
        return 1

    if _run(py, ["-m", "pip", "install", "-U", "pip", "setuptools", "wheel"]) != 0:
        return 1
    if _run(py, ["-m", "pip", "install", "-r", "requirements.txt"]) != 0:
        return 1

    # Bootstrap DB + default config
    if _run(py, [os.path.join(ROOT, "devtools", "bootstrap_local_db.py")]) != 0:
        return 1

    # Paths under local-dev-data
    p_patch = os.path.join(ROOT, "devtools", "patch_local_config.py")
    if os.path.isfile(
        os.path.join(ROOT, "local-dev-data", "config.ini")
    ):
        if _run(py, [p_patch]) != 0:
            return 1

    if args.with_sample_library:
        if _run(
            py,
            [os.path.join(ROOT, "devtools", "setup_local_dev_library.py")],
            env={**os.environ, "MYLAR_CONFIG_FILE": os.path.join(ROOT, "local-dev-data", "config.ini")},
        ) != 0:
            print(
                "[ensure_dev_environment] setup_local_dev_library failed — "
                "see output above (Comic Vine, network, or import).",
                file=sys.stderr,
            )
            return 1

    print("")
    print("=" * 60)
    print(
        "[ensure_dev_environment] Done. Open this repo in Cursor/VS Code, then:"
    )
    if not args.with_sample_library:
        print(
            "  Add a series via the Mylar web UI (search by name or volume id) — "
            "that matches a normal install; do not use --with-sample-library unless you need scripted test files."
        )
    print(
        "  Run and Debug: \"Mylar: Run (local dev UI)\"  — or task: \"Mylar: Start server\""
    )
    print(
        "  Shell:  %s Mylar.py --datadir %s --nolaunch"
        % (py, os.path.join(ROOT, "local-dev-data"))
    )
    print(
        "  Browser: http://127.0.0.1:8090 (or [Web] http_port in local-dev-data/config.ini)"
    )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
