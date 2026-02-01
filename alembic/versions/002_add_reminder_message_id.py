"""add reminder_message_id to tasks

Revision ID: 002
Revises: 001
Create Date: 2025-02-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('reminder_message_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'reminder_message_id')
