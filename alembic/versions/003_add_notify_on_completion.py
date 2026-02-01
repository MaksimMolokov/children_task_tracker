"""add notify_on_completion to task_types

Revision ID: 003
Revises: 002
Create Date: 2025-02-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'task_types',
        sa.Column('notify_on_completion', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('task_types', 'notify_on_completion')
