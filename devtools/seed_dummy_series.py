"""
Backward-compatible entry point. Prefer:

  python devtools/setup_local_dev_library.py

which imports real Comic Vine series, aligns folders, writes minimal CBZs with
ComicInfo.xml, and runs forceRescan.
"""
from setup_local_dev_library import main

if __name__ == "__main__":
    main()
