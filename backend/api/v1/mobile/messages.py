"""
Mobile optimized messaging endpoints
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime

from core.database import get_db
from core.auth.dependencies import get_current_user
from core.performance import PaginationParams, PaginationHelper
from modules.users.domain.models import User
from modules.messaging.application.message_service import MessageService
from modules.messaging.domain.schemas import MessageCreate

router = APIRouter(prefix="/mobile/messages", tags=["mobile-messages"])


class MobileMessageResponse(BaseModel):
    """Mobile optimized message response"""
    id: str
    content: str
    sender_type: str  # 'model' or 'fan'
    created_at: datetime
    is_read: bool
    has_media: bool
    media_count: int = 0
    media_preview_url: Optional[str] = None
    price: Optional[float] = None
    is_paid: bool = True


class MobileConversationResponse(BaseModel):
    """Mobile conversation summary"""
    fan_id: str
    fan_username: str
    fan_avatar_url: Optional[str]
    last_message: Optional[MobileMessageResponse]
    unread_count: int
    is_online: bool
    last_seen: Optional[datetime]
    total_spent: float
    is_subscriber: bool


class MobileSendMessageRequest(BaseModel):
    """Mobile message send request"""
    content: str
    media_ids: List[str] = Field(default_factory=list)
    price: Optional[float] = None


@router.get("/conversations", response_model=List[MobileConversationResponse])
async def get_conversations(
    model_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversations list optimized for mobile
    """
    # Verify user has access to model
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get conversations with optimized query
    from sqlalchemy import select, func, and_, or_
    from modules.messaging.domain.models import Message
    from modules.fans.domain.models import Fan
    
    # Subquery for last message
    last_message_subq = (
        select(
            Message.fan_id,
            func.max(Message.created_at).label("last_message_time")
        )
        .where(Message.model_id == model_id)
        .group_by(Message.fan_id)
        .subquery()
    )
    
    # Main query
    query = (
        select(
            Fan.id,
            Fan.username,
            Fan.avatar_url,
            Fan.last_activity,
            Fan.total_spent,
            Fan.subscription_status,
            func.count(Message.id).filter(
                and_(
                    Message.is_read == False,
                    Message.sender == "fan"
                )
            ).label("unread_count"),
            func.max(Message.created_at).label("last_message_time")
        )
        .join(Message, Message.fan_id == Fan.id)
        .join(
            last_message_subq,
            Fan.id == last_message_subq.c.fan_id
        )
        .where(Message.model_id == model_id)
        .group_by(Fan.id)
        .order_by(func.max(Message.created_at).desc())
    )
    
    if unread_only:
        query = query.having(
            func.count(Message.id).filter(
                and_(
                    Message.is_read == False,
                    Message.sender == "fan"
                )
            ) > 0
        )
    
    # Apply pagination
    params = PaginationParams(page=page, per_page=per_page)
    paginated = await PaginationHelper.paginate(db, query, params)
    
    # Format response
    conversations = []
    for row in paginated.items:
        # Get last message
        last_msg_query = (
            select(Message)
            .where(
                and_(
                    Message.model_id == model_id,
                    Message.fan_id == row.id
                )
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg_result = await db.execute(last_msg_query)
        last_message = last_msg_result.scalar_one_or_none()
        
        conversations.append(MobileConversationResponse(
            fan_id=str(row.id),
            fan_username=row.username,
            fan_avatar_url=row.avatar_url,
            last_message=MobileMessageResponse(
                id=str(last_message.id),
                content=last_message.content[:100] + "..." if len(last_message.content) > 100 else last_message.content,
                sender_type=last_message.sender,
                created_at=last_message.created_at,
                is_read=last_message.is_read,
                has_media=bool(last_message.media_urls),
                media_count=len(last_message.media_urls) if last_message.media_urls else 0,
                media_preview_url=last_message.media_urls[0] if last_message.media_urls else None,
                price=float(last_message.price) if last_message.price else None,
                is_paid=last_message.is_paid
            ) if last_message else None,
            unread_count=row.unread_count,
            is_online=_is_user_online(row.last_activity),
            last_seen=row.last_activity,
            total_spent=float(row.total_spent),
            is_subscriber=row.subscription_status == "active"
        ))
    
    return conversations


@router.get("/conversation/{fan_id}", response_model=List[MobileMessageResponse])
async def get_conversation_messages(
    model_id: UUID,
    fan_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    before_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages in a conversation (infinite scroll support)
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    message_service = MessageService()
    
    # Build query with cursor pagination for better mobile performance
    from sqlalchemy import select, and_
    from modules.messaging.domain.models import Message
    
    query = (
        select(Message)
        .where(
            and_(
                Message.model_id == model_id,
                Message.fan_id == fan_id
            )
        )
        .order_by(Message.created_at.desc())
    )
    
    # Apply cursor pagination if before_id provided
    if before_id:
        before_msg = await db.get(Message, before_id)
        if before_msg:
            query = query.where(Message.created_at < before_msg.created_at)
    
    query = query.limit(per_page)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Mark messages as read
    unread_ids = [
        msg.id for msg in messages 
        if not msg.is_read and msg.sender == "fan"
    ]
    if unread_ids:
        await message_service.mark_messages_as_read(unread_ids, db)
    
    # Format for mobile
    return [
        MobileMessageResponse(
            id=str(msg.id),
            content=msg.content,
            sender_type=msg.sender,
            created_at=msg.created_at,
            is_read=msg.is_read,
            has_media=bool(msg.media_urls),
            media_count=len(msg.media_urls) if msg.media_urls else 0,
            media_preview_url=msg.media_urls[0] if msg.media_urls else None,
            price=float(msg.price) if msg.price else None,
            is_paid=msg.is_paid
        )
        for msg in reversed(messages)  # Return in chronological order
    ]


@router.post("/send")
async def send_message(
    model_id: UUID,
    fan_id: UUID,
    message: MobileSendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message from mobile
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    message_service = MessageService()
    
    # Create message
    message_data = MessageCreate(
        model_id=model_id,
        fan_id=fan_id,
        content=message.content,
        sender="model",
        media_urls=message.media_ids,  # These would be pre-uploaded media IDs
        price=message.price
    )
    
    created_message = await message_service.create_message(message_data, db)
    
    # Return mobile-optimized response
    return MobileMessageResponse(
        id=str(created_message.id),
        content=created_message.content,
        sender_type=created_message.sender,
        created_at=created_message.created_at,
        is_read=created_message.is_read,
        has_media=bool(created_message.media_urls),
        media_count=len(created_message.media_urls) if created_message.media_urls else 0,
        media_preview_url=created_message.media_urls[0] if created_message.media_urls else None,
        price=float(created_message.price) if created_message.price else None,
        is_paid=created_message.is_paid
    )


@router.websocket("/ws/{model_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    model_id: UUID,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket for real-time messaging
    """
    # Verify token and get user
    from core.security import decode_token
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        # Verify user has access to model
        # ... verification logic ...
        
        await websocket.accept()
        
        # Add to connection pool
        # ... connection management ...
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                # Handle different message types
                if data["type"] == "message":
                    # Process and broadcast message
                    pass
                elif data["type"] == "typing":
                    # Broadcast typing indicator
                    pass
                elif data["type"] == "read":
                    # Mark messages as read
                    pass
                    
        except WebSocketDisconnect:
            # Remove from connection pool
            pass
            
    except Exception as e:
        await websocket.close(code=1008, reason="Authentication failed")


@router.post("/mark-read")
async def mark_messages_read(
    message_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Mark multiple messages as read
    """
    message_service = MessageService()
    
    # Verify user has access to messages
    # ... verification logic ...
    
    await message_service.mark_messages_as_read(message_ids, db)
    
    return {"message": "Messages marked as read"}


@router.get("/unread-count")
async def get_unread_count(
    model_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get total unread message count
    """
    if not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
    
    from sqlalchemy import select, func, and_
    from modules.messaging.domain.models import Message
    
    count_query = (
        select(func.count(Message.id))
        .where(
            and_(
                Message.model_id == model_id,
                Message.is_read == False,
                Message.sender == "fan"
            )
        )
    )
    
    unread_count = await db.scalar(count_query)
    
    return {"unread_count": unread_count}


def _is_user_online(last_activity: Optional[datetime]) -> bool:
    """Check if user is considered online"""
    if not last_activity:
        return False
    
    # Consider online if active in last 5 minutes
    from datetime import timedelta
    return (datetime.utcnow() - last_activity) < timedelta(minutes=5)


async def _user_has_model_access(
    user: User,
    model_id: UUID,
    db: AsyncSession
) -> bool:
    """Check if user has access to model"""
    from modules.models.domain.models import Model
    
    model = await db.get(Model, model_id)
    if not model:
        return False
    
    # Check if user is agency owner/staff or the model itself
    return (
        user.agency_id == model.agency_id or
        user.id == model.user_id
    )