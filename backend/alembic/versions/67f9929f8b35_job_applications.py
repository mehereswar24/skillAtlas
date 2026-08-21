"""Job applications and their stage timeline

The learner's own application board: saved → applied → screen → onsite →
offer / rejected / withdrawn, with every move kept in ``application_events`` so
an application has a history rather than a mutable status column.

Nothing in these tables is fetched. ``job_description`` is pasted by the
learner and ``source_url`` is a bookmark for them to click — SkillAtlas does
not read job boards, which is a licence and terms-of-service problem, not a
missing feature.

``company_id`` and ``company_role_id`` are optional and ON DELETE SET NULL: an
application usually is not to one of the 30 seeded companies, and when it is,
the seeder still rebuilds ``company_roles`` wholesale on every run. The
company and role *labels* are therefore stored on the row itself and always
populated, so a card stays readable whatever happens to the seed.

Revision ID: 67f9929f8b35
Revises: c31f7ba90d42
Create Date: 2026-08-21 18:10:12.482446
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '67f9929f8b35'
down_revision: Union[str, None] = 'c31f7ba90d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STAGES = "'saved', 'applied', 'screen', 'onsite', 'offer', 'rejected', 'withdrawn'"


def upgrade() -> None:
    op.create_table(
        'job_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('company_role_id', sa.Integer(), nullable=True),
        sa.Column('company_name', sa.String(length=160), nullable=False),
        sa.Column('role_title', sa.String(length=200), nullable=False),
        sa.Column('stage', sa.String(length=24), nullable=False),
        sa.Column('location', sa.String(length=160), nullable=True),
        sa.Column('salary_note', sa.String(length=160), nullable=True),
        sa.Column('source_url', sa.String(length=600), nullable=True),
        sa.Column('job_description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('applied_on', sa.Date(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.CheckConstraint(f'stage IN ({_STAGES})', name='ck_job_application_stage'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['company_role_id'], ['company_roles.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_applications_id'), 'job_applications', ['id'])
    op.create_index(
        op.f('ix_job_applications_user_id'), 'job_applications', ['user_id']
    )
    op.create_index(
        op.f('ix_job_applications_company_id'), 'job_applications', ['company_id']
    )
    op.create_index(
        op.f('ix_job_applications_company_role_id'),
        'job_applications',
        ['company_role_id'],
    )
    op.create_index(op.f('ix_job_applications_stage'), 'job_applications', ['stage'])
    op.create_index(
        op.f('ix_job_applications_created_at'), 'job_applications', ['created_at']
    )

    op.create_table(
        'application_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('from_stage', sa.String(length=24), nullable=True),
        sa.Column('to_stage', sa.String(length=24), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column(
            'occurred_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.CheckConstraint(
            f'to_stage IN ({_STAGES})', name='ck_application_event_stage'
        ),
        sa.ForeignKeyConstraint(
            ['application_id'], ['job_applications.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_application_events_id'), 'application_events', ['id'])
    op.create_index(
        op.f('ix_application_events_application_id'),
        'application_events',
        ['application_id'],
    )
    op.create_index(
        op.f('ix_application_events_to_stage'), 'application_events', ['to_stage']
    )
    op.create_index(
        op.f('ix_application_events_occurred_at'), 'application_events', ['occurred_at']
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_application_events_occurred_at'), table_name='application_events'
    )
    op.drop_index(
        op.f('ix_application_events_to_stage'), table_name='application_events'
    )
    op.drop_index(
        op.f('ix_application_events_application_id'), table_name='application_events'
    )
    op.drop_index(op.f('ix_application_events_id'), table_name='application_events')
    op.drop_table('application_events')

    op.drop_index(op.f('ix_job_applications_created_at'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_stage'), table_name='job_applications')
    op.drop_index(
        op.f('ix_job_applications_company_role_id'), table_name='job_applications'
    )
    op.drop_index(op.f('ix_job_applications_company_id'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_user_id'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_id'), table_name='job_applications')
    op.drop_table('job_applications')
