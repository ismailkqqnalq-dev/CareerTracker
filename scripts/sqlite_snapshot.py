"""Consistent SQLite backup or restore into a NEW file; never load .env."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time


def snapshot(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must not exist; restore into a new file.')
    if not source.is_file():
        raise ValueError('Source must be a database file.')
    deadline = time.monotonic() + 60

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError('Snapshot exceeded 60 seconds.')

    fd, temporary = tempfile.mkstemp(prefix='.snapshot-', dir=destination.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(temporary)) as dst:
                src.backup(dst, pages=256, progress=progress)
                if dst.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('Snapshot failed integrity validation.')
                if dst.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise ValueError('Snapshot contains inconsistent foreign keys.')
        with open(temporary, 'r+b') as stream:
            os.fsync(stream.fileno())
        # Atomic publication without overwriting any existing destination.
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    try:
        snapshot(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error, TimeoutError):
        parser.exit(1, 'Snapshot failed: check paths, permissions, database integrity and available space. Destination must be new.\n')
    print('Snapshot created and integrity/foreign-key checks passed. Store it encrypted off-host.')


if __name__ == '__main__':
    main()

