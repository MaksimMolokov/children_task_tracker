"""add reward_amount to task_types and prompt_message_id to tasks

Revision ID: 001
Revises: 
Create Date: 2023-12-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from decimal import Decimal

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add reward_amount to task_types
    op.add_column('task_types', sa.Column('reward_amount', sa.Numeric(10, 2), server_default='0', nullable=False))
    
    # Add prompt_message_id to tasks
    op.add_column('tasks', sa.Column('prompt_message_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'prompt_message_id')
    op.drop_column('task_types', 'reward_amount')
