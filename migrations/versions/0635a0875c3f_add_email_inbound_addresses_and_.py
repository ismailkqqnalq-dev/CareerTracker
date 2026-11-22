"""add email inbound addresses and suggestions

Revision ID: 0635a0875c3f
Revises: 713efa9f736b
Create Date: 2026-11-22 21:46:57.812552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0635a0875c3f'
down_revision: Union[str, Sequence[str], None] = '713efa9f736b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Kullanıcı başına yönlendirme adresi ve gelen e-postalardan çıkan bekleyen öneriler."""
    op.create_table('inbound_addresses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('local_part', sa.String(length=64), nullable=False),
    # sa.func.now() hem SQLite hem PostgreSQL'de geçerli varsayılanı üretir.
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('verification_code', sa.String(length=32), nullable=True),
    sa.Column('verification_received_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('local_part'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('email_suggestions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('opportunity_id', sa.Integer(), nullable=False),
    sa.Column('email_type', sa.String(length=32), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('sender', sa.String(length=320), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('suggested_status', sa.String(length=50), nullable=True),
    sa.Column('suggested_last_contact_date', sa.Date(), nullable=True),
    sa.Column('suggested_task_description', sa.String(length=2000), nullable=True),
    sa.Column('suggested_task_due_date', sa.Date(), nullable=True),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_suggestions_opportunity_id'), 'email_suggestions', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_email_suggestions_state'), 'email_suggestions', ['state'], unique=False)
    op.create_index(op.f('ix_email_suggestions_user_id'), 'email_suggestions', ['user_id'], unique=False)


def downgrade() -> None:
    """Tabloları kaldırır; yönlendirme adresleri ve bekleyen öneriler kaybolur."""
    op.drop_index(op.f('ix_email_suggestions_user_id'), table_name='email_suggestions')
    op.drop_index(op.f('ix_email_suggestions_state'), table_name='email_suggestions')
    op.drop_index(op.f('ix_email_suggestions_opportunity_id'), table_name='email_suggestions')
    op.drop_table('email_suggestions')
    op.drop_table('inbound_addresses')
