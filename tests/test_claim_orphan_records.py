"""Tests for claiming pre-authentication CRM rows using disposable SQLite DBs."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claim_orphan_records.py"
PRE_OWNERSHIP_CONSTRAINT_HEAD = "e3f2a187b96c"
TABLES = ("opportunities", "contacts", "tasks", "activities")


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["PYTHON_DOTENV_DISABLED"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def crm_database(tmp_path):
    database_path = tmp_path / "claim-test.db"
    database_url = "sqlite:///" + database_path.as_posix()
    engine = create_engine(database_url)
    _run_alembic(database_url, "upgrade", PRE_OWNERSHIP_CONSTRAINT_HEAD)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, is_active) "
                "VALUES (1, 'target@example.com', 'unused', 1), "
                "(2, 'other@example.com', 'unused', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO opportunities (id, user_id, company) VALUES "
                "(1, NULL, 'Orphan Opportunity'), "
                "(2, 2, 'Other User Opportunity')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO contacts (id, user_id, name, opportunity_id) VALUES "
                "(1, NULL, 'Orphan Contact', 1), "
                "(2, 2, 'Other User Contact', 2)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(id, user_id, opportunity_id, description) VALUES "
                "(1, NULL, 1, 'Orphan Task'), "
                "(2, 2, 2, 'Other User Task')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO activities "
                "(id, user_id, opportunity_id, contact_id, activity_type) VALUES "
                "(1, NULL, 1, 1, 'Orphan Activity'), "
                "(2, 2, 2, 2, 'Other User Activity')"
            )
        )
    yield database_path, database_url, engine
    engine.dispose()


def _add_relationship_mismatches(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO opportunities (id, user_id, company) "
                "VALUES (3, 2, 'Foreign Link Opportunity')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO contacts (id, user_id, name, opportunity_id) "
                "VALUES (3, NULL, 'Foreign Link Contact', 3)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(id, user_id, opportunity_id, description) "
                "VALUES (3, 2, 1, 'Owned Task With Orphan Opportunity')"
            )
        )


def _run_script(database_url: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHON_DOTENV_DISABLED"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--user-id",
            "1",
            "--database-url",
            database_url,
            *extra_args,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _user_ids(engine, table: str) -> list[tuple[int, int | None]]:
    with engine.connect() as connection:
        return [
            (row.id, row.user_id)
            for row in connection.execute(
                text(f"SELECT id, user_id FROM {table} ORDER BY id")
            )
        ]


def test_default_dry_run_reports_orphans_without_writing_or_backing_up(
    crm_database,
):
    database_path, database_url, engine = crm_database

    result = _run_script(database_url)

    assert result.returncode == 0, result.stdout + result.stderr
    for table in TABLES:
        assert f"{table}: 1" in result.stdout
        assert _user_ids(engine, table)[0][1] is None
    assert "tar" in result.stdout
    assert "target@example.com" not in result.stdout
    assert not list(database_path.parent.glob("*.bak-claim-*"))


def test_apply_creates_consistent_default_backup_and_updates_only_null_rows(
    crm_database,
):
    database_path, database_url, engine = crm_database

    result = _run_script(database_url, "--apply")

    assert result.returncode == 0, result.stdout + result.stderr
    backups = list(database_path.parent.glob("claim-test.db.bak-claim-*"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute(
            "SELECT user_id FROM opportunities WHERE id = 1"
        ).fetchone() == (None,)
    for table in TABLES:
        assert f"{table}: before=1, updated=1, after=0" in result.stdout
        assert _user_ids(engine, table) == [(1, 1), (2, 2)]


def test_second_apply_is_idempotent(crm_database):
    _, database_url, _ = crm_database
    first = _run_script(database_url, "--apply")
    assert first.returncode == 0, first.stdout + first.stderr

    second = _run_script(database_url, "--apply")

    assert second.returncode == 0, second.stdout + second.stderr
    for table in TABLES:
        assert f"{table}: before=0, updated=0, after=0" in second.stdout


def test_missing_user_fails_without_changing_rows_or_creating_backup(
    crm_database,
):
    database_path, database_url, engine = crm_database
    before = {table: _user_ids(engine, table) for table in TABLES}

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--user-id",
            "999",
            "--database-url",
            database_url,
            "--apply",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "user 999" in (result.stdout + result.stderr).lower()
    assert {table: _user_ids(engine, table) for table in TABLES} == before
    assert not list(database_path.parent.glob("*.bak-claim-*"))


def test_relationship_mismatches_are_reported_and_apply_rolls_back(
    crm_database,
):
    _, database_url, engine = crm_database
    _add_relationship_mismatches(engine)
    before = {table: _user_ids(engine, table) for table in TABLES}

    result = _run_script(database_url, "--apply")

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "contacts" in output and "3" in output
    assert "tasks" in output and "3" in output
    assert "inconsisten" in output.lower()
    assert {table: _user_ids(engine, table) for table in TABLES} == before


def test_dry_run_lists_both_directions_of_relationship_mismatch(crm_database):
    _, database_url, engine = crm_database
    _add_relationship_mismatches(engine)
    before = {table: _user_ids(engine, table) for table in TABLES}

    result = _run_script(database_url)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "contacts#3" in result.stdout
    assert "tasks#3" in result.stdout
    assert {table: _user_ids(engine, table) for table in TABLES} == before


def test_database_error_after_updates_rolls_back_the_whole_claim(crm_database):
    database_path, database_url, engine = crm_database
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TRIGGER fail_task_claim
            BEFORE UPDATE OF user_id ON tasks
            WHEN OLD.user_id IS NULL
            BEGIN
                SELECT RAISE(ABORT, 'forced claim failure');
            END;
            """
        )
    before = {table: _user_ids(engine, table) for table in TABLES}

    result = _run_script(database_url, "--apply")

    assert result.returncode != 0
    assert "database operation failed" in (result.stdout + result.stderr).lower()
    assert {table: _user_ids(engine, table) for table in TABLES} == before
    assert list(database_path.parent.glob("claim-test.db.bak-claim-*"))


def test_backup_failure_does_not_change_any_rows(crm_database, tmp_path):
    _, database_url, engine = crm_database
    before = {table: _user_ids(engine, table) for table in TABLES}
    invalid_backup_path = tmp_path / "missing-parent" / "backup.db"

    result = _run_script(
        database_url,
        "--apply",
        "--backup-path",
        str(invalid_backup_path),
    )

    assert result.returncode != 0
    assert "backup" in (result.stdout + result.stderr).lower()
    assert {table: _user_ids(engine, table) for table in TABLES} == before


def test_postgresql_apply_requires_explicit_manual_backup_confirmation():
    result = _run_script(
        "postgresql://placeholder:placeholder@127.0.0.1:1/placeholder",
        "--apply",
    )

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "pg_dump" in output
    assert "--i-have-a-backup" in output
