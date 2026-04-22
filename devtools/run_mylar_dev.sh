#!/usr/bin/env sh
# POSIX: use .venv if present
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
DATA="${ROOT}/local-dev-data"
if [ -x "${ROOT}/.venv/bin/python3" ]; then
  exec "${ROOT}/.venv/bin/python3" "${ROOT}/Mylar.py" --datadir "$DATA" --nolaunch "$@"
elif [ -x "${ROOT}/.venv/bin/python" ]; then
  exec "${ROOT}/.venv/bin/python" "${ROOT}/Mylar.py" --datadir "$DATA" --nolaunch "$@"
else
  exec python3 "${ROOT}/Mylar.py" --datadir "$DATA" --nolaunch "$@"
fi
