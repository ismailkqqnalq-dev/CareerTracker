"""add resolved skill to suggestions

Revision ID: 6ab28fa3c91d
Revises: f1c0a43b7d91
Create Date: 2026-10-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6ab28fa3c91d"
down_revision: Union[str, Sequence[str], None] = "f1c0a43b7d91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("skill_suggestions") as batch_op:
        batch_op.add_column(
            sa.Column("resolved_skill_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_skill_suggestions_resolved_skill_id_skills",
            "skills",
            ["resolved_skill_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_skill_suggestions_resolved_skill_id",
            ["resolved_skill_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("skill_suggestions") as batch_op:
        batch_op.drop_index("ix_skill_suggestions_resolved_skill_id")
        batch_op.drop_constraint(
            "fk_skill_suggestions_resolved_skill_id_skills",
            type_="foreignkey",
        )
        batch_op.drop_column("resolved_skill_id")
