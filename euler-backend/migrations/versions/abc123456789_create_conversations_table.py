"""create_conversations_table

Revision ID: abc123456789
Revises: 
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123456789'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('messages', sa.JSON(), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversations_last_activity'), 'conversations', ['last_activity'], unique=False)
    op.create_index(op.f('ix_conversations_expires_at'), 'conversations', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_conversations_expires_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_last_activity'), table_name='conversations')
    op.drop_table('conversations')
