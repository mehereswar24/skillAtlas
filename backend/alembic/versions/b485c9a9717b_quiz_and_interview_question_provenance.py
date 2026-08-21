"""Quiz and interview question provenance

Adds ``generated_by`` and ``verified_at`` to both question tables.

Almost every question in the bank was written by a local model against the
concept's own ``content_md`` and then re-checked against that same body
(``scripts/generate_quizzes.py``). Without these two columns there is no way to
tell machine output from hand-authored material once it is in the database, and
the product would be quietly presenting one as the other. NULL in both columns
means "a human wrote this", which is the honest default for the rows that
already exist.

Revision ID: b485c9a9717b
Revises: 3a725c2a4a4e
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b485c9a9717b'
down_revision: Union[str, None] = '3a725c2a4a4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('quiz_questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('generated_by', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('interview_questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('generated_by', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('interview_questions', schema=None) as batch_op:
        batch_op.drop_column('verified_at')
        batch_op.drop_column('generated_by')

    with op.batch_alter_table('quiz_questions', schema=None) as batch_op:
        batch_op.drop_column('verified_at')
        batch_op.drop_column('generated_by')
