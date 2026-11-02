"""require an owner for every CRM record

Revision ID: f6c52d90e34a
Revises: e3f2a187b96c
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6c52d90e34a"
down_revision = "e3f2a187b96c"
branch_labels = None
depends_on = None


_CRM_TABLES = ("opportunities", "contacts", "tasks", "activities")


def upgrade() -> None:
    bind = op.get_bind()
    orphan_counts = {
        table: bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL")
        ).scalar_one()
        for table in _CRM_TABLES
    }
    remaining = {table: count for table, count in orphan_counts.items() if count}
    if remaining:
        details = ", ".join(f"{table}={count}" for table, count in remaining.items())
        raise RuntimeError(
            "Cannot require CRM record ownership while unclaimed rows remain "
            f"({details}). First run scripts/claim_orphan_records.py with the "
            "intended --user-id and --database-url (review its dry-run, then "
            "use --apply); only after it succeeds run "
            "'python -m alembic upgrade head'."
        )

    for table in _CRM_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=False,
            )


def downgrade() -> None:
    for table in _CRM_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=True,
            )
