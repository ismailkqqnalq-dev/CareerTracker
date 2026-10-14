"""add user ownership to crm records

Revision ID: 64aa267fb63d
Revises: d715ca26c5e0
Create Date: 2026-10-13 21:24:35.568437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64aa267fb63d'
down_revision: Union[str, Sequence[str], None] = 'd715ca26c5e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("activities", "contacts", "opportunities", "tasks"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table}_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )
            batch_op.create_index(f"ix_{table}_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    for table in ("tasks", "opportunities", "contacts", "activities"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_user_id")
            batch_op.drop_constraint(
                f"fk_{table}_user_id_users",
                type_="foreignkey",
            )
            batch_op.drop_column("user_id")