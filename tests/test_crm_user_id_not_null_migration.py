"""Migration regression tests for making CRM ownership mandatory.

All Alembic commands in this module point at disposable SQLite databases. The
development database and its environment configuration are never consulted.
"""

import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
PRE_OWNERSHIP_CONSTRAINT_HEAD = "e3f2a187b96c"
CRM_TABLES = ("opportunities", "contacts", "tasks", "activities")


def _alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["PYTHON_DOTENV_DISABLED"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _run_alembic(database_url: str, *args: str) -> None:
    result = _alembic(database_url, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def _crm_snapshot(connection) -> dict[str, list[tuple]]:
    return {
        table: [
            tuple(row)
            for row in connection.execute(
                text(f"SELECT * FROM {table} ORDER BY id")
            )
        ]
        for table in CRM_TABLES
    }


def _foreign_keys(connection, table: str) -> dict[str, tuple[str, str]]:
    rows = connection.exec_driver_sql(
        f'PRAGMA foreign_key_list("{table}")'
    )
    return {
        row[3]: (row[2], row[6].upper())
        for row in rows
    }


def _indexes(connection, table: str) -> set[tuple]:
    rows = connection.exec_driver_sql(f'PRAGMA index_list("{table}")')
    return {
        (row[1], row[2], row[3], row[4])
        for row in rows
    }


def _insert_owned_crm_rows(connection) -> None:
    connection.execute(
        text(
            "INSERT INTO users (id, email, hashed_password, is_active) "
            "VALUES (1, 'migration-owner@example.com', 'unused', 1)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO opportunities (id, user_id, company) "
            "VALUES (1, 1, 'Migration Company')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO contacts (id, user_id, name, opportunity_id) "
            "VALUES (1, 1, 'Migration Contact', 1)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO tasks "
            "(id, user_id, opportunity_id, description) "
            "VALUES (1, 1, 1, 'Migration Task')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO activities "
            "(id, user_id, opportunity_id, contact_id, activity_type) "
            "VALUES (1, 1, 1, 1, 'Migration Activity')"
        )
    )


def _ownership_schema_snapshot(connection) -> tuple[dict, dict]:
    foreign_keys = {
        table: _foreign_keys(connection, table)
        for table in CRM_TABLES
    }
    indexes = {
        table: _indexes(connection, table)
        for table in CRM_TABLES
    }
    return foreign_keys, indexes


def _assert_required_foreign_keys(foreign_keys: dict) -> None:
    assert foreign_keys["opportunities"]["user_id"] == (
        "users",
        "CASCADE",
    )
    assert foreign_keys["contacts"]["user_id"] == ("users", "CASCADE")
    assert foreign_keys["contacts"]["opportunity_id"] == (
        "opportunities",
        "CASCADE",
    )
    assert foreign_keys["tasks"]["user_id"] == ("users", "CASCADE")
    assert foreign_keys["tasks"]["opportunity_id"] == (
        "opportunities",
        "CASCADE",
    )
    assert foreign_keys["activities"]["user_id"] == ("users", "CASCADE")
    assert foreign_keys["activities"]["opportunity_id"] == (
        "opportunities",
        "CASCADE",
    )
    assert foreign_keys["activities"]["contact_id"] == (
        "contacts",
        "SET NULL",
    )


def test_crm_ownership_not_null_migration_preserves_data_foreign_keys_and_indexes(
    tmp_path,
):
    database_url = "sqlite:///" + (tmp_path / "ownership-migration.db").as_posix()
    engine = create_engine(database_url)
    try:
        _run_alembic(database_url, "upgrade", PRE_OWNERSHIP_CONSTRAINT_HEAD)
        with engine.begin() as connection:
            _insert_owned_crm_rows(connection)
            original_rows = _crm_snapshot(connection)
            original_foreign_keys, original_indexes = (
                _ownership_schema_snapshot(connection)
            )
            assert all(len(original_rows[table]) == 1 for table in CRM_TABLES)

        _run_alembic(database_url, "upgrade", "head")

        with engine.begin() as connection:
            migrated_rows = _crm_snapshot(connection)
            migrated_foreign_keys, migrated_indexes = (
                _ownership_schema_snapshot(connection)
            )
            assert migrated_rows == original_rows
            assert migrated_foreign_keys == original_foreign_keys
            assert migrated_indexes == original_indexes
            _assert_required_foreign_keys(migrated_foreign_keys)
            for table in CRM_TABLES:
                columns = {
                    column["name"]: column
                    for column in connection.exec_driver_sql(
                        f'PRAGMA table_info("{table}")'
                    ).mappings()
                }
                assert columns["user_id"]["notnull"] == 1

        _run_alembic(database_url, "downgrade", PRE_OWNERSHIP_CONSTRAINT_HEAD)

        with engine.begin() as connection:
            downgraded_rows = _crm_snapshot(connection)
            downgraded_foreign_keys, downgraded_indexes = (
                _ownership_schema_snapshot(connection)
            )
            assert downgraded_rows == original_rows
            assert downgraded_foreign_keys == original_foreign_keys
            assert downgraded_indexes == original_indexes
            _assert_required_foreign_keys(downgraded_foreign_keys)
            for table in CRM_TABLES:
                columns = {
                    column["name"]: column
                    for column in connection.exec_driver_sql(
                        f'PRAGMA table_info("{table}")'
                    ).mappings()
                }
                assert columns["user_id"]["notnull"] == 0
    finally:
        engine.dispose()


def test_crm_ownership_migration_rejects_orphans_without_partial_changes(
    tmp_path,
):
    database_url = "sqlite:///" + (tmp_path / "orphan-migration.db").as_posix()
    engine = create_engine(database_url)
    try:
        _run_alembic(database_url, "upgrade", PRE_OWNERSHIP_CONSTRAINT_HEAD)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO opportunities (id, user_id, company) "
                    "VALUES (1, NULL, 'Orphan Company')"
                )
            )
            before_rows = _crm_snapshot(connection)
            before_foreign_keys, before_indexes = _ownership_schema_snapshot(
                connection
            )

        result = _alembic(database_url, "upgrade", "head")

        assert result.returncode != 0, result.stdout + result.stderr
        output = result.stdout + result.stderr
        script_instruction = output.find("claim_orphan_records.py")
        migration_instruction = output.find("alembic upgrade head")
        assert script_instruction >= 0, output
        assert migration_instruction > script_instruction, output

        with engine.begin() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == PRE_OWNERSHIP_CONSTRAINT_HEAD
            assert _crm_snapshot(connection) == before_rows
            foreign_keys, indexes = _ownership_schema_snapshot(connection)
            assert foreign_keys == before_foreign_keys
            assert indexes == before_indexes
            for table in CRM_TABLES:
                columns = {
                    column["name"]: column
                    for column in connection.exec_driver_sql(
                        f'PRAGMA table_info("{table}")'
                    ).mappings()
                }
                assert columns["user_id"]["notnull"] == 0
    finally:
        engine.dispose()
