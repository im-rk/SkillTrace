"""one live submission per (session, question)

Revision ID: 3c1f0a7d9e42
Revises: 01d667a22ab2
Create Date: 2026-09-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c1f0a7d9e42"
down_revision: Union[str, Sequence[str], None] = "01d667a22ab2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_submission_session_question",
        "submission_queue_log",
        ["session_id", "question_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'failed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_submission_session_question", table_name="submission_queue_log")
