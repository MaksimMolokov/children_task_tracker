"""drop chats table

Revision ID: 004
Revises: 003
Create Date: 2025-02-03

Модель Chat и таблица chats не используются (канал/чат отчётов не планируется).
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chats")


def downgrade() -> None:
    # Модель Chat удалена из кода; при необходимости таблицу воссоздать вручную
    pass

