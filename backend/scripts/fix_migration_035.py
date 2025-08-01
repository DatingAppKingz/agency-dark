#!/usr/bin/env python3
"""
Fix migration 035 - handle existing chat_conversations table.
"""
from pathlib import Path

def fix_migration_035():
    """Fix migration 035 to check if conversations/chat_conversations table exists."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '035_create_chat_system_simple.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the table creation with a check
    content = content.replace(
        """    # Create conversations table
    op.create_table('conversations',""",
        """    # Create conversations table (check if it exists as conversations or chat_conversations)
    conn = op.get_bind()
    
    # Check if chat_conversations exists (from migration 021)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_conversations')"
    ))
    chat_conversations_exists = result.scalar()
    
    # Check if conversations exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversations')"
    ))
    conversations_exists = result.scalar()
    
    if chat_conversations_exists and not conversations_exists:
        # Rename chat_conversations to conversations
        op.rename_table('chat_conversations', 'conversations')
    elif not conversations_exists:
        # Create new table
        op.create_table('conversations',"""
    )
    
    # Also fix the messages table creation
    content = content.replace(
        """    # Create messages table
    op.create_table('messages',""",
        """    # Create messages table (check if it exists as messages or chat_messages)
    # Check if chat_messages exists (from migration 021)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages')"
    ))
    chat_messages_exists = result.scalar()
    
    # Check if messages exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages')"
    ))
    messages_exists = result.scalar()
    
    if chat_messages_exists and not messages_exists:
        # Rename chat_messages to messages
        op.rename_table('chat_messages', 'messages')
    elif not messages_exists:
        # Create new table
        op.create_table('messages',"""
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 035 to handle existing chat tables")

if __name__ == '__main__':
    fix_migration_035()