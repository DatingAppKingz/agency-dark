"""Simple conversation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.chat import Conversation, Message, MessageType, MessageStatus
from models.user import User
from models.model import Model
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


class ConversationCreate(BaseModel):
    model_id: int
    fan_username: str
    fan_display_name: str


class ConversationResponse(BaseModel):
    id: int
    model_id: int
    fan_id: int
    fan_username: str
    fan_display_name: Optional[str]
    status: str
    last_message_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


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


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    conversation: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new conversation."""
    # Verify model exists
    stmt = select(Model).where(Model.id == conversation.model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Create conversation
    new_conversation = Conversation(
        model_id=conversation.model_id,
        fan_id=1,  # Dummy fan ID
        fan_username=conversation.fan_username,
        fan_display_name=conversation.fan_display_name,
        status="ACTIVE"
    )
    
    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)
    
    return new_conversation


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of conversations."""
    stmt = select(Conversation)
    
    if model_id:
        stmt = stmt.where(Conversation.model_id == model_id)
    
    stmt = stmt.offset(skip).limit(limit).order_by(Conversation.created_at.desc())
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get conversation by ID."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get messages for a conversation."""
    # Verify conversation exists
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages
    stmt = select(Message).where(
        Message.conversation_id == conversation_id
    ).offset(skip).limit(limit).order_by(Message.created_at.desc())
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return messages