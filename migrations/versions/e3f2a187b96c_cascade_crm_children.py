"""cascade CRM children when their parent is deleted

Revision ID: e3f2a187b96c
Revises: a91e73c208bf
Create Date: 2026-10-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e3f2a187b96c"
down_revision = "a91e73c208bf"
branch_labels = None
depends_on = None


_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _replace_foreign_key(
    table: str,
    local_column: str,
    referred_table: str,
    *,
    ondelete: str | None,
) -> None:
    bind = op.get_bind()
    foreign_key = next(
        fk
        for fk in sa.inspect(bind).get_foreign_keys(table)
        if fk["constrained_columns"] == [local_column]
        and fk["referred_table"] == referred_table
    )
    constraint_name = foreign_key["name"] or (
        f"fk_{table}_{local_column}_{referred_table}"
    )
    with op.batch_alter_table(
        table,
        naming_convention=_NAMING_CONVENTION,
    ) as batch:
        batch.drop_constraint(constraint_name, type_="foreignkey")
        batch.create_foreign_key(
            constraint_name,
            referred_table,
            [local_column],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _replace_foreign_key(
        "contacts", "opportunity_id", "opportunities", ondelete="CASCADE"
    )
    _replace_foreign_key(
        "activities", "opportunity_id", "opportunities", ondelete="CASCADE"
    )
    _replace_foreign_key(
        "activities", "contact_id", "contacts", ondelete="SET NULL"
    )
    _replace_foreign_key(
        "tasks", "opportunity_id", "opportunities", ondelete="CASCADE"
    )


def downgrade() -> None:
    _replace_foreign_key(
        "tasks", "opportunity_id", "opportunities", ondelete=None
    )
    _replace_foreign_key(
        "activities", "contact_id", "contacts", ondelete=None
    )
    _replace_foreign_key(
        "activities", "opportunity_id", "opportunities", ondelete=None
    )
    _replace_foreign_key(
        "contacts", "opportunity_id", "opportunities", ondelete=None
    )
