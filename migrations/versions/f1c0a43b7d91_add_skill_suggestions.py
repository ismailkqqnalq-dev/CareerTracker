"""add skill suggestions

Revision ID: f1c0a43b7d91
Revises: 64aa267fb63d
Create Date: 2026-10-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c0a43b7d91"
down_revision: Union[str, Sequence[str], None] = "64aa267fb63d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("raw_name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_skill_suggestions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "normalized_name",
            name="uq_skill_suggestions_user_normalized_name",
        ),
    )
    op.create_index(
        "ix_skill_suggestions_id",
        "skill_suggestions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_skill_suggestions_user_id",
        "skill_suggestions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_suggestions_user_id", table_name="skill_suggestions")
    op.drop_index("ix_skill_suggestions_id", table_name="skill_suggestions")
    op.drop_table("skill_suggestions")
