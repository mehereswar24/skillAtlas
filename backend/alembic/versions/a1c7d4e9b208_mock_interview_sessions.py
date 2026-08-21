"""Mock interview sessions and turns

A session draws its questions from ``company_questions`` — the same
source-cited bank the company profile shows — and grades the answers against
the rubric that company has published.

Both tables denormalise deliberately. The seeder rebuilds ``companies``,
``company_roles`` and ``company_questions`` wholesale on every run, so the
company/role labels and the question text and reference answer are copied onto
the rows. A past attempt is a record of what the learner was asked and how they
answered; it has to stay readable after a re-seed. The foreign keys are kept
alongside with ON DELETE SET NULL purely so a live session can still link back
to the profile it came from.

``recommendations_json`` holds the concepts the debrief sent the learner back
to. Stored as a snapshot rather than a join table: it is advice given at a
point in time, and re-opening a finished session must not re-run retrieval and
quietly give different advice than the one the learner acted on.

Revision ID: a1c7d4e9b208
Revises: 67f9929f8b35
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c7d4e9b208'
down_revision: Union[str, None] = '67f9929f8b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'interview_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_role_id', sa.Integer(), nullable=True),
        sa.Column('company_slug', sa.String(length=80), nullable=False),
        sa.Column('company_name', sa.String(length=160), nullable=False),
        sa.Column('role_slug', sa.String(length=80), nullable=False),
        sa.Column('role_title', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('summary_md', sa.Text(), nullable=True),
        sa.Column('recommendations_json', sa.Text(), nullable=True),
        sa.Column('was_degraded', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['company_role_id'], ['company_roles.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_interview_sessions_id'), 'interview_sessions', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_interview_sessions_user_id'),
        'interview_sessions',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_sessions_company_role_id'),
        'interview_sessions',
        ['company_role_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_sessions_company_slug'),
        'interview_sessions',
        ['company_slug'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_sessions_role_slug'),
        'interview_sessions',
        ['role_slug'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_sessions_status'),
        'interview_sessions',
        ['status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_sessions_created_at'),
        'interview_sessions',
        ['created_at'],
        unique=False,
    )

    op.create_table(
        'interview_turns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('company_question_id', sa.Integer(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('round', sa.String(length=24), nullable=False),
        sa.Column('topic', sa.String(length=120), nullable=True),
        sa.Column('difficulty', sa.String(length=20), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('reference_answer_md', sa.Text(), nullable=True),
        sa.Column('source_name', sa.String(length=160), nullable=True),
        sa.Column('source_url', sa.String(length=600), nullable=True),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('verdict', sa.String(length=20), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('feedback_md', sa.Text(), nullable=True),
        sa.Column('missed_points', sa.Text(), nullable=True),
        sa.Column('injection_flagged', sa.Boolean(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['company_question_id'], ['company_questions.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], ['interview_sessions.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'session_id', 'position', name='uq_interview_turn_position'
        ),
    )
    op.create_index(
        op.f('ix_interview_turns_id'), 'interview_turns', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_interview_turns_session_id'),
        'interview_turns',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_turns_company_question_id'),
        'interview_turns',
        ['company_question_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_interview_turns_round'), 'interview_turns', ['round'], unique=False
    )
    op.create_index(
        op.f('ix_interview_turns_verdict'), 'interview_turns', ['verdict'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_turns_verdict'), table_name='interview_turns')
    op.drop_index(op.f('ix_interview_turns_round'), table_name='interview_turns')
    op.drop_index(
        op.f('ix_interview_turns_company_question_id'), table_name='interview_turns'
    )
    op.drop_index(op.f('ix_interview_turns_session_id'), table_name='interview_turns')
    op.drop_index(op.f('ix_interview_turns_id'), table_name='interview_turns')
    op.drop_table('interview_turns')

    op.drop_index(
        op.f('ix_interview_sessions_created_at'), table_name='interview_sessions'
    )
    op.drop_index(op.f('ix_interview_sessions_status'), table_name='interview_sessions')
    op.drop_index(
        op.f('ix_interview_sessions_role_slug'), table_name='interview_sessions'
    )
    op.drop_index(
        op.f('ix_interview_sessions_company_slug'), table_name='interview_sessions'
    )
    op.drop_index(
        op.f('ix_interview_sessions_company_role_id'), table_name='interview_sessions'
    )
    op.drop_index(
        op.f('ix_interview_sessions_user_id'), table_name='interview_sessions'
    )
    op.drop_index(op.f('ix_interview_sessions_id'), table_name='interview_sessions')
    op.drop_table('interview_sessions')
