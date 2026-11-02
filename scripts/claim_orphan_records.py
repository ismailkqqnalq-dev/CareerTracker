"""Assign legacy CRM rows without an owner to one existing user.

The database URL must be supplied explicitly. By default this command only
reports the rows it would claim; writes require ``--apply``.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


CRM_TABLES = ("opportunities", "contacts", "tasks", "activities")

# Fixed identifiers and relationships; values in these statements always come
# from this module, while user-provided values are passed as bound parameters.
_OWNERSHIP_LINKS = (
    ("contacts", "opportunity_id", "opportunities"),
    ("tasks", "opportunity_id", "opportunities"),
    ("activities", "opportunity_id", "opportunities"),
    ("activities", "contact_id", "contacts"),
)


class OwnershipLinkInconsistency(RuntimeError):
    """Raised when claiming null owners would create cross-user links."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report legacy CRM records without an owner, or assign them to "
            "one existing user. Dry-run is the default."
        )
    )
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--database-url", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only; this is the default.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Back up the database and assign only rows whose user_id is NULL.",
    )
    parser.add_argument(
        "--backup-path",
        help="Optional SQLite backup path; the default is beside the database.",
    )
    parser.add_argument(
        "--i-have-a-backup",
        action="store_true",
        help="Confirm a manual pg_dump backup before applying changes to PostgreSQL.",
    )
    return parser


def _sqlite_path(database_url: str) -> Path:
    url = make_url(database_url)
    database = url.database
    if not database or database == ":memory:":
        raise RuntimeError(
            "SQLite --apply requires a file-backed database so a backup can be made."
        )
    return Path(database)


def _backup_sqlite_database(database_url: str, requested_path: str | None) -> Path:
    database_path = _sqlite_path(database_url)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = (
        Path(requested_path)
        if requested_path
        else Path(f"{database_path}.bak-claim-{timestamp}")
    )
    if backup_path.resolve() == database_path.resolve():
        raise RuntimeError("Backup path must not point to the database itself.")
    if backup_path.exists():
        raise RuntimeError(f"Backup path already exists; refusing to overwrite: {backup_path}")

    source = None
    destination = None
    try:
        source = sqlite3.connect(str(database_path))
        destination = sqlite3.connect(str(backup_path))
        source.backup(destination)
        destination.commit()
    except Exception as error:
        if destination is not None:
            destination.close()
            destination = None
        try:
            backup_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"SQLite backup failed; database was not changed: {error}") from error
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
    return backup_path


def _user_email(connection, user_id: int) -> str | None:
    return connection.execute(
        text("SELECT email FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).scalar_one_or_none()


def _orphan_counts(connection) -> dict[str, int]:
    return {
        table: connection.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL")
        ).scalar_one()
        for table in CRM_TABLES
    }


def _link_inconsistencies(connection, target_user_id: int) -> list[str]:
    issues: list[str] = []
    for child_table, foreign_key, parent_table in _OWNERSHIP_LINKS:
        rows = connection.execute(
            text(
                f"SELECT child.id, child.user_id, parent.id, parent.user_id "
                f"FROM {child_table} AS child "
                f"JOIN {parent_table} AS parent "
                f"ON child.{foreign_key} = parent.id "
                "WHERE (child.user_id IS NULL "
                "AND parent.user_id IS NOT NULL "
                "AND parent.user_id != :target_user_id) "
                "OR (parent.user_id IS NULL "
                "AND child.user_id IS NOT NULL "
                "AND child.user_id != :target_user_id) "
                "ORDER BY child.id"
            ),
            {"target_user_id": target_user_id},
        )
        for child_id, child_owner, parent_id, parent_owner in rows:
            child_owner_label = "NULL" if child_owner is None else str(child_owner)
            parent_owner_label = "NULL" if parent_owner is None else str(parent_owner)
            issues.append(
                f"{child_table}#{child_id} (user_id={child_owner_label}) "
                f"-> {parent_table}#{parent_id} (user_id={parent_owner_label})"
            )
    return issues


def _print_report(
    *,
    user_id: int,
    email: str,
    counts: dict[str, int],
    inconsistencies: list[str],
    apply: bool,
) -> None:
    prefix = email[:3]
    mode = "APPLY" if apply else "DRY RUN (no database changes)"
    print(f"Mode: {mode}")
    print(f"Target user: id={user_id}, email prefix={prefix!r}")
    print("Unclaimed rows:")
    for table in CRM_TABLES:
        print(f"  {table}: {counts[table]}")
    print(f"Ownership link inconsistencies: {len(inconsistencies)}")
    for issue in inconsistencies:
        print(f"  {issue}")


def _validate_user_and_read_report(engine, user_id: int):
    with engine.connect() as connection:
        email = _user_email(connection, user_id)
        if email is None:
            raise RuntimeError(f"User {user_id} does not exist; no changes made.")
        counts = _orphan_counts(connection)
        inconsistencies = _link_inconsistencies(connection, user_id)
    return email, counts, inconsistencies


def _claim_rows(
    engine,
    user_id: int,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    before: dict[str, int]
    after: dict[str, int]
    updated: dict[str, int] = {}
    with engine.begin() as connection:
        if _user_email(connection, user_id) is None:
            raise RuntimeError(f"User {user_id} no longer exists; transaction rolled back.")
        before = _orphan_counts(connection)
        inconsistencies = _link_inconsistencies(connection, user_id)
        if inconsistencies:
            raise OwnershipLinkInconsistency(
                "Ownership link inconsistencies prevent applying the claim; "
                "resolve them explicitly and rerun. " + "; ".join(inconsistencies)
            )

        for table in CRM_TABLES:
            result = connection.execute(
                text(
                    f"UPDATE {table} SET user_id = :user_id "
                    "WHERE user_id IS NULL"
                ),
                {"user_id": user_id},
            )
            updated[table] = result.rowcount

        after = _orphan_counts(connection)
        remaining = {table: count for table, count in after.items() if count}
        if remaining:
            raise RuntimeError(
                "Unclaimed rows remain after the update; transaction rolled back: "
                + ", ".join(f"{table}={count}" for table, count in remaining.items())
            )
        remaining_inconsistencies = _link_inconsistencies(connection, user_id)
        if remaining_inconsistencies:
            raise OwnershipLinkInconsistency(
                "Ownership link inconsistencies remain after the update; "
                "transaction rolled back. " + "; ".join(remaining_inconsistencies)
            )
    return before, updated, after


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    url = make_url(args.database_url)
    backend = url.get_backend_name()
    if backend not in {"sqlite", "postgresql"}:
        print("Error: database URL must use SQLite or PostgreSQL.", file=sys.stderr)
        return 2

    apply = bool(args.apply)
    if apply and backend == "postgresql" and not args.i_have_a_backup:
        print(
            "PostgreSQL changes require a manually verified pg_dump backup. "
            "Create and verify that backup first, then rerun with --i-have-a-backup. "
            "No database connection or changes were made.",
            file=sys.stderr,
        )
        return 2

    try:
        engine = create_engine(url)
    except SQLAlchemyError:
        print("Error: could not initialize the database connection.", file=sys.stderr)
        return 2

    try:
        email, counts, inconsistencies = _validate_user_and_read_report(
            engine,
            args.user_id,
        )
        _print_report(
            user_id=args.user_id,
            email=email,
            counts=counts,
            inconsistencies=inconsistencies,
            apply=apply,
        )
        if not apply:
            return 0
        if inconsistencies:
            print(
                "Error: ownership link inconsistencies prevent applying the claim; "
                "no rows were changed.",
                file=sys.stderr,
            )
            return 2
        if not any(counts.values()):
            print("No unclaimed rows; nothing to update or back up.")
            for table in CRM_TABLES:
                print(f"  {table}: before=0, updated=0, after=0")
            return 0

        if backend == "sqlite":
            backup_path = _backup_sqlite_database(
                args.database_url,
                args.backup_path,
            )
            print(f"SQLite backup created: {backup_path}")
        else:
            print("PostgreSQL backup confirmation received; the script does not run pg_dump.")

        try:
            before, updated, after = _claim_rows(engine, args.user_id)
        except OwnershipLinkInconsistency as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2

        print("Apply complete:")
        for table in CRM_TABLES:
            print(
                f"  {table}: before={before[table]}, "
                f"updated={updated[table]}, after={after[table]}"
            )
        print("Validation: no unclaimed rows remain.")
        return 0
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(
            "Error: database operation failed; no uncommitted changes were saved.",
            file=sys.stderr,
        )
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
