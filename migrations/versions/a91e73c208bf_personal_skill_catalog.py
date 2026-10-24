"""Separate personal skill additions from the shared catalog.

Existing rows remain shared: historical authorship was not recorded.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a91e73c208bf'
down_revision = '6ab28fa3c91d'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # SQLite's old unnamed unique constraint needs a reflected name for batch mode.
    name_constraint = next(
        item['name'] or 'uq_skills_name'
        for item in sa.inspect(bind).get_unique_constraints('skills')
        if item['column_names'] == ['name']
    )
    with op.batch_alter_table('skills', naming_convention={'uq': 'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        batch.add_column(sa.Column('owner_user_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_skills_owner_user_id_users', 'users', ['owner_user_id'], ['id'], ondelete='CASCADE')
        batch.drop_constraint(name_constraint, type_='unique')
        batch.create_unique_constraint('uq_skills_owner_name', ['owner_user_id', 'name'])
        batch.create_index('ix_skills_owner_user_id', ['owner_user_id'])
    op.create_index('uq_skills_shared_name', 'skills', ['name'], unique=True,
                    sqlite_where=sa.text('owner_user_id IS NULL'),
                    postgresql_where=sa.text('owner_user_id IS NULL'))
    op.create_table(
        'personal_skill_aliases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alias', sa.String(), nullable=False),
        sa.Column('skill_id', sa.Integer(), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('user_id', 'alias', name='uq_personal_skill_aliases_user_alias'),
    )
    op.create_index('ix_personal_skill_aliases_user_id', 'personal_skill_aliases', ['user_id'])
    op.create_index('ix_personal_skill_aliases_skill_id', 'personal_skill_aliases', ['skill_id'])


def downgrade():
    bind = op.get_bind()
    if (bind.execute(sa.text('SELECT COUNT(*) FROM skills WHERE owner_user_id IS NOT NULL')).scalar()
            or bind.execute(sa.text('SELECT COUNT(*) FROM personal_skill_aliases')).scalar()):
        raise RuntimeError('Cannot downgrade while personal skills or aliases exist; preserve/export them first.')
    op.drop_table('personal_skill_aliases')
    op.drop_index('uq_skills_shared_name', table_name='skills')
    with op.batch_alter_table('skills') as batch:
        batch.drop_index('ix_skills_owner_user_id')
        batch.drop_constraint('uq_skills_owner_name', type_='unique')
        batch.drop_constraint('fk_skills_owner_user_id_users', type_='foreignkey')
        batch.drop_column('owner_user_id')
        batch.create_unique_constraint('uq_skills_name', ['name'])
