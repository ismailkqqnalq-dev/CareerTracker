"""initial migration

Revision ID: d0fe616da34f
Revises: 
Create Date: 2026-09-21 08:33:08.018584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0fe616da34f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Bootstrap the original CRM tables before the skill migration references them.
    # Databases already stamped at this revision or later do not rerun this step.
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company", sa.String()),
        sa.Column("position", sa.String()),
        sa.Column("type", sa.String()),
        sa.Column("application_date", sa.DateTime()),
        sa.Column("job_link", sa.String()),
        sa.Column("salary", sa.Integer()),
        sa.Column("location", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("notes", sa.String()),
        sa.Column("next_action", sa.String()),
        sa.Column("last_contact_date", sa.DateTime()),
    )
    op.create_index("ix_opportunities_id", "opportunities", ["id"])
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String()),
        sa.Column("role", sa.String()),
        sa.Column("email", sa.String()),
        sa.Column("linkedin", sa.String()),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id")),
    )
    op.create_index("ix_contacts_id", "contacts", ["id"])
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id")),
        sa.Column("activity_type", sa.String()),
        sa.Column("dates", sa.DateTime()),
        sa.Column("notes", sa.String()),
    )
    op.create_index("ix_activities_id", "activities", ["id"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("description", sa.String()),
        sa.Column("due_date", sa.DateTime()),
        sa.Column("is_completed", sa.Boolean()),
    )
    op.create_index("ix_tasks_id", "tasks", ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    for table in ("tasks", "activities", "contacts", "opportunities"):
        op.drop_index(f"ix_{table}_id", table_name=table)
        op.drop_table(table)
