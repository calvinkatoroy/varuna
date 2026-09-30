"""Consistent SQLite backup (safe while the API is running) with simple retention.

Usage (inside a controlplane container, so paths/env match):
  docker compose exec api-public python /app/controlplane/backup_db.py            # -> /data/backups
  docker compose exec api-public python /app/controlplane/backup_db.py /data/backups 14
Copy the resulting files off the host (the named volume is the only other copy). Generated
report files live in REPORTS_DIR (/data/reports): back that directory up with the same job.
Uses sqlite3's online backup API, not a file copy, so a WAL-mode database is captured consistently.
"""
import datetime
import glob
import os
import sqlite3
import sys

DB = os.environ.get("VARUNA_DB", "/data/varuna.db")


def backup(dest_dir: str, keep: int) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, f"varuna-{datetime.datetime.now():%Y%m%d-%H%M%S-%f}.db")
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(out)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    for old in sorted(glob.glob(os.path.join(dest_dir, "varuna-*.db")))[:-keep]:
        os.remove(old)
    return out


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(DB), "backups")
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    print("backup written:", backup(dest, keep))
