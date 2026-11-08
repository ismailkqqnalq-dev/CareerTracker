import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'sqlite_snapshot.py'


def run(source, target):
    return subprocess.run([sys.executable, str(SCRIPT), '--source', str(source), '--destination', str(target)], capture_output=True, text=True)


def test_backup_and_restore_preserve_data(tmp_path):
    source = tmp_path / 'source.db'
    with sqlite3.connect(source) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
        db.execute('INSERT INTO sample VALUES (1, ?)', ('Türkçe kayıt',))
        db.commit()
        backup = tmp_path / 'backup.db'
        assert run(source, backup).returncode == 0
    restored = tmp_path / 'restored.db'
    assert run(backup, restored).returncode == 0
    with sqlite3.connect(restored) as db:
        assert db.execute('SELECT * FROM sample').fetchall() == [(1, 'Türkçe kayıt')]
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)


def test_existing_destination_is_never_overwritten(tmp_path):
    source = tmp_path / 'source.db'
    sqlite3.connect(source).close()
    target = tmp_path / 'keep.db'
    target.write_bytes(b'keep')
    assert run(source, target).returncode == 1
    assert target.read_bytes() == b'keep'


def test_missing_source_does_not_create_database(tmp_path):
    source, target = tmp_path / 'missing.db', tmp_path / 'target.db'
    assert run(source, target).returncode == 1
    assert not source.exists()
    assert not target.exists()


def test_corrupt_source_leaves_no_output(tmp_path):
    source, target = tmp_path / 'bad.db', tmp_path / 'target.db'
    source.write_bytes(b'not a database')
    assert run(source, target).returncode == 1
    assert not target.exists()



def test_inconsistent_foreign_keys_reject_snapshot(tmp_path):
    source, target = tmp_path / 'bad-links.db', tmp_path / 'target.db'
    with sqlite3.connect(source) as db:
        db.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(parent_id INTEGER REFERENCES parent(id)); INSERT INTO child VALUES(7);')
    assert run(source, target).returncode == 1
    assert not target.exists()
    assert not list(tmp_path.glob('.snapshot-*'))
