"""Company reviews

Member-submitted interview and workplace experiences, plus their
helpful/not-helpful votes.

Deliberately a new table rather than columns on ``companies``: everything in
the existing company tables is researched and source-cited — a
``company_questions`` row cannot exist without a ``source_url`` — and a review
is the opposite kind of claim. Keeping them apart in the schema is what stops
them being merged in a query and rendered as the same thing.

``company_role_id`` is ON DELETE SET NULL, not CASCADE: the seeder rebuilds
``company_roles`` wholesale on every run, and a learner's review must not be
deleted because a role slug was renamed. ``(company_id, user_id)`` is unique —
one review per person per company, edited rather than re-posted.

Revision ID: c31f7ba90d42
Revises: b485c9a9717b
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c31f7ba90d42'
down_revision: Union[str, None] = 'b485c9a9717b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'company_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_role_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body_md', sa.Text(), nullable=False),
        sa.Column('interview_outcome', sa.String(length=24), nullable=False),
        sa.Column('interview_year', sa.Integer(), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False),
        sa.Column('is_sample', sa.Boolean(), nullable=False),
        sa.Column('helpful_count', sa.Integer(), nullable=False),
        sa.Column('not_helpful_count', sa.Integer(), nullable=False),
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
        sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_company_review_rating'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['company_role_id'], ['company_roles.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'user_id', name='uq_company_review_author'),
    )
    op.create_index(op.f('ix_company_reviews_id'), 'company_reviews', ['id'])
    op.create_index(
        op.f('ix_company_reviews_company_id'), 'company_reviews', ['company_id']
    )
    op.create_index(op.f('ix_company_reviews_user_id'), 'company_reviews', ['user_id'])
    op.create_index(
        op.f('ix_company_reviews_company_role_id'), 'company_reviews', ['company_role_id']
    )
    op.create_index(
        op.f('ix_company_reviews_interview_outcome'),
        'company_reviews',
        ['interview_outcome'],
    )
    op.create_index(
        op.f('ix_company_reviews_created_at'), 'company_reviews', ['created_at']
    )

    op.create_table(
        'review_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['review_id'], ['company_reviews.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'user_id', name='uq_review_vote'),
    )
    op.create_index(op.f('ix_review_votes_review_id'), 'review_votes', ['review_id'])
    op.create_index(op.f('ix_review_votes_user_id'), 'review_votes', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_review_votes_user_id'), table_name='review_votes')
    op.drop_index(op.f('ix_review_votes_review_id'), table_name='review_votes')
    op.drop_table('review_votes')

    op.drop_index(op.f('ix_company_reviews_created_at'), table_name='company_reviews')
    op.drop_index(
        op.f('ix_company_reviews_interview_outcome'), table_name='company_reviews'
    )
    op.drop_index(
        op.f('ix_company_reviews_company_role_id'), table_name='company_reviews'
    )
    op.drop_index(op.f('ix_company_reviews_user_id'), table_name='company_reviews')
    op.drop_index(op.f('ix_company_reviews_company_id'), table_name='company_reviews')
    op.drop_index(op.f('ix_company_reviews_id'), table_name='company_reviews')
    op.drop_table('company_reviews')
