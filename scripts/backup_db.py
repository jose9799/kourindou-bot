"""Create a consistent snapshot of the bot database.

Uses SQLite's online backup API, so it is safe to run while the bot is writing:
a plain file copy could catch a half-written WAL and produce a corrupt snapshot.

    python scripts/backup_db.py [--keep 14] [--out backups]
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Back up the Kourindou database.")
    parser.add_argument("--out", type=Path, default=config.BASE_DIR / "backups")
    parser.add_argument("--keep", type=int, default=14, help="How many snapshots to retain.")
    return parser.parse_args()


def prune(directory: Path, keep: int) -> int:
    snapshots = sorted(directory.glob("kourindou-*.db"), reverse=True)
    removed = 0
    for stale in snapshots[keep:]:
        stale.unlink()
        removed += 1
    return removed


def main() -> int:
    args = parse_args()
    if not config.DATABASE_PATH.exists():
        print(f"No database at {config.DATABASE_PATH}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = args.out / f"kourindou-{stamp}.db"

    source = sqlite3.connect(f"file:{config.DATABASE_PATH}?mode=ro", uri=True)
    target = sqlite3.connect(destination)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()

    size_mb = destination.stat().st_size / 1_048_576
    removed = prune(args.out, args.keep)
    print(f"Backup written to {destination} ({size_mb:.2f} MB)")
    if removed:
        print(f"Pruned {removed} old snapshot(s), keeping the newest {args.keep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
