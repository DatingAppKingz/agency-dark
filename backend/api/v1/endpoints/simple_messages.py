"""Simple message endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.chat import Message, MessageType, MessageStatus, Conversation
from models.user import User
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


class MessageCreate(BaseModel):
    conversation_id: int
    content: str
    sender_type: str = "CHATTER"


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_type: str
    content: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=MessageResponse)
async def create_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message in a conversation."""
    # Verify conversation exists
    stmt = select(Conversation).where(Conversation.id == message.conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Determine sender type
    try:
        sender_type = MessageType[message.sender_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid sender type")
    
    # Create message
    new_message = Message(
        conversation_id=message.conversation_id,
        sender_id=current_user.id,
        sender_type=sender_type,
        type="TEXT",
        content=message.content,
        status=MessageStatus.SENT
    )
    
    db.add(new_message)
    
    # Update conversation last message time
    conversation.last_message_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(new_message)
    
    return new_message