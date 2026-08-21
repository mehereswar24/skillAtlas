"""portfolio profiles

The two tables behind the public learner page at /u/{handle}. They store
consent, not achievements: the projects, concepts, points and badges shown
already live in project_submissions, user_progress and points_events, and are
read through these switches rather than copied.

`is_published` defaults to false, so creating a row publishes nothing.
`handle_ci` carries the unique index (lowercase) while `handle` keeps the
learner's capitalisation, which is what makes `Alice` and `alice` the same
handle.

Revision ID: 5c2ab5ee3046
Revises: e816317eb75b
Create Date: 2026-08-21 18:34:43.227126
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c2ab5ee3046'
down_revision: Union[str, None] = 'e816317eb75b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('portfolio_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('handle', sa.String(length=30), nullable=False),
    sa.Column('handle_ci', sa.String(length=30), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('headline', sa.String(length=200), nullable=False),
    sa.Column('bio', sa.Text(), nullable=False),
    sa.Column('location', sa.String(length=120), nullable=False),
    sa.Column('github_url', sa.String(length=300), nullable=True),
    sa.Column('linkedin_url', sa.String(length=300), nullable=True),
    sa.Column('website_url', sa.String(length=300), nullable=True),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('show_projects', sa.Boolean(), nullable=False),
    sa.Column('show_concepts', sa.Boolean(), nullable=False),
    sa.Column('show_points', sa.Boolean(), nullable=False),
    sa.Column('show_badges', sa.Boolean(), nullable=False),
    sa.Column('show_readiness', sa.Boolean(), nullable=False),
    sa.Column('show_project_code', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('portfolio_profiles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_profiles_handle_ci'), ['handle_ci'], unique=True)
        batch_op.create_index(batch_op.f('ix_portfolio_profiles_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_portfolio_profiles_is_published'), ['is_published'], unique=False)
        batch_op.create_index(batch_op.f('ix_portfolio_profiles_user_id'), ['user_id'], unique=True)

    op.create_table('portfolio_projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('profile_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('is_visible', sa.Boolean(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['profile_id'], ['portfolio_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id', 'project_id', name='uq_portfolio_project')
    )
    with op.batch_alter_table('portfolio_projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_portfolio_projects_profile_id'), ['profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_portfolio_projects_project_id'), ['project_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('portfolio_projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_projects_project_id'))
        batch_op.drop_index(batch_op.f('ix_portfolio_projects_profile_id'))

    op.drop_table('portfolio_projects')
    with op.batch_alter_table('portfolio_profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_portfolio_profiles_user_id'))
        batch_op.drop_index(batch_op.f('ix_portfolio_profiles_is_published'))
        batch_op.drop_index(batch_op.f('ix_portfolio_profiles_id'))
        batch_op.drop_index(batch_op.f('ix_portfolio_profiles_handle_ci'))

    op.drop_table('portfolio_profiles')
