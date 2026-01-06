"""add cascade delete to chat messages

Revision ID: 9f03cceaa492
Revises: 34aaf324bd00
Create Date: 2026-01-06 22:57:13.810344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '9f03cceaa492'
down_revision: Union[str, Sequence[str], None] = '34aaf324bd00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL'de constraint'i direkt değiştirmek için
    op.execute("""
        ALTER TABLE chat_messages 
        DROP CONSTRAINT IF EXISTS chat_messages_session_id_fkey;
    """)
    
    op.execute("""
        ALTER TABLE chat_messages 
        ADD CONSTRAINT chat_messages_session_id_fkey 
        FOREIGN KEY (session_id) 
        REFERENCES chat_sessions(id) 
        ON DELETE CASCADE;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE chat_messages 
        DROP CONSTRAINT IF EXISTS chat_messages_session_id_fkey;
    """)
    
    op.execute("""
        ALTER TABLE chat_messages 
        ADD CONSTRAINT chat_messages_session_id_fkey 
        FOREIGN KEY (session_id) 
        REFERENCES chat_sessions(id);
    """)