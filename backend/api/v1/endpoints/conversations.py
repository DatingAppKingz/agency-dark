"""Conversation and chat management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, desc, asc
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
import json

from core.database import get_db
from models.user import User, UserRole
from models.model import Model
from models.chat import (
    Conversation, ConversationStatus,
    Message, MessageType, MessageStatus
)
from models.subscriber import Subscriber, SubscriptionTier, SubscriptionStatus
from models.content import Content, ContentType
from models.financial import Transaction, TransactionType, TransactionStatus
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


# Request/Response Models
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: MessageType = MessageType.TEXT
    media_urls: Optional[List[str]] = []
    is_ppv: bool = False
    ppv_price: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = {}


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: Optional[int]
    sender_name: str
    sender_avatar: Optional[str]
    content: str
    message_type: MessageType
    status: MessageStatus
    media_urls: List[str]
    is_ppv: bool
    ppv_price: Optional[Decimal]
    is_ppv_unlocked: bool = False
    read_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: int
    model_id: int
    model_name: str
    model_avatar: Optional[str]
    subscriber_id: int
    subscriber_name: str
    subscriber_username: str
    status: ConversationStatus
    last_message: Optional[MessageResponse]
    unread_count: int
    is_priority: bool
    is_vip: bool
    total_spent: Decimal
    assigned_chatter_id: Optional[int]
    assigned_chatter_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    chats: List[ChatResponse]
    total: int
    page: int
    limit: int


class SubscriberResponse(BaseModel):
    id: int
    user_id: int
    username: str
    display_name: str
    avatar_url: Optional[str]
    tier: SubscriptionTier
    status: SubscriptionStatus
    is_active: bool
    subscription_price: Decimal
    total_spent: Decimal
    last_seen_at: Optional[datetime]
    expires_at: Optional[datetime]
    auto_renew: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationStats(BaseModel):
    active_chats: int
    total_messages_today: int
    avg_response_time: float
    unread_messages: int
    vip_chats: int
    priority_chats: int
    revenue_today: Decimal


# Helper functions
async def verify_chat_access(conversation_id: int, user: User, db: AsyncSession) -> Conversation:
    """Verify user has access to the chat."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    chat = await db.scalar(stmt)
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Check access based on role
    if user.role == UserRole.SUPER_ADMIN:
        return chat
    
    # Get model
    model_stmt = select(Model).where(Model.id == chat.model_id)
    model = await db.scalar(model_stmt)
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check if user has access
    if user.role == UserRole.MODEL and model.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif user.role == UserRole.CHATTER and chat.assigned_chatter_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif user.agency_id and model.agency_id != user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return chat


async def get_subscriber_info(subscriber_id: int, db: AsyncSession) -> Dict[str, Any]:
    """Get subscriber information."""
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    subscriber = await db.scalar(stmt)
    
    if not subscriber:
        return {
            "name": "Unknown Subscriber",
            "username": "unknown",
            "avatar": None,
            "tier": SubscriptionTier.FREE,
            "is_vip": False,
            "total_spent": Decimal("0")
        }
    
    # Get user info
    user_stmt = select(User).where(User.id == subscriber.user_id)
    user = await db.scalar(user_stmt)
    
    # Calculate total spent
    spent_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.user_id == subscriber.user_id,
            Transaction.model_id == subscriber.model_id,
            Transaction.status == TransactionStatus.COMPLETED
        )
    )
    total_spent = await db.scalar(spent_stmt) or Decimal("0")
    
    return {
        "name": subscriber.display_name or (f"{user.first_name} {user.last_name}" if user else "Subscriber"),
        "username": subscriber.username or (user.username if user else "subscriber"),
        "avatar": subscriber.avatar_url,
        "tier": subscriber.tier,
        "is_vip": subscriber.is_vip,
        "total_spent": total_spent
    }


# Endpoints
@router.get("/active", response_model=ChatListResponse)
async def list_active_chats(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ConversationStatus] = None,
    model_id: Optional[int] = None,
    assigned_to_me: bool = False,
    search: Optional[str] = None,
    sort_by: str = Query("last_message", pattern="^(last_message|created_at|total_spent)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List active conversations with filtering and pagination."""
    # Build base query
    query = select(Conversation)
    count_query = select(func.count(Conversation.id))
    
    # Apply filters based on user role
    if current_user.role == UserRole.MODEL:
        # Models see chats for their profile
        model_stmt = select(Model.id).where(Model.user_id == current_user.id)
        model_ids = await db.scalar(model_stmt)
        if model_ids:
            query = query.where(Conversation.model_id == model_ids)
            count_query = count_query.where(Conversation.model_id == model_ids)
        else:
            # No model profile found
            return ChatListResponse(chats=[], total=0, page=page, limit=limit)
    
    elif current_user.role == UserRole.CHATTER:
        # Chatters see only assigned chats
        query = query.where(Conversation.assigned_chatter_id == current_user.id)
        count_query = count_query.where(Conversation.assigned_chatter_id == current_user.id)
    
    elif current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        # Agency users see chats for their agency's models
        model_ids_stmt = select(Model.id).where(Model.agency_id == current_user.agency_id)
        model_ids_result = await db.execute(model_ids_stmt)
        model_ids = [row[0] for row in model_ids_result]
        
        if model_ids:
            query = query.where(Conversation.model_id.in_(model_ids))
            count_query = count_query.where(Conversation.model_id.in_(model_ids))
        else:
            return ChatListResponse(chats=[], total=0, page=page, limit=limit)
    
    # Additional filters
    if status:
        query = query.where(Conversation.status == status)
        count_query = count_query.where(Conversation.status == status)
    else:
        # Default to active chats
        query = query.where(Conversation.status == ConversationStatus.ACTIVE)
        count_query = count_query.where(Conversation.status == ConversationStatus.ACTIVE)
    
    if model_id:
        query = query.where(Conversation.model_id == model_id)
        count_query = count_query.where(Conversation.model_id == model_id)
    
    if assigned_to_me and current_user.role == UserRole.CHATTER:
        query = query.where(Conversation.assigned_chatter_id == current_user.id)
        count_query = count_query.where(Conversation.assigned_chatter_id == current_user.id)
    
    # Get total count
    total = await db.scalar(count_query) or 0
    
    # Apply sorting
    if sort_by == "last_message":
        query = query.order_by(Conversation.last_message_at.desc().nullslast())
    elif sort_by == "created_at":
        query = query.order_by(Conversation.created_at.desc())
    elif sort_by == "total_spent":
        # This would require a join with calculated total spent
        query = query.order_by(Conversation.created_at.desc())  # Fallback for now
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    chats = result.scalars().all()
    
    # Build response
    chat_responses = []
    for chat in chats:
        # Get model info
        model_stmt = select(Model).where(Model.id == chat.model_id)
        model = await db.scalar(model_stmt)
        
        # Get subscriber info (using fan data directly since we don't have subscribers)
        subscriber_info = {
            "name": chat.fan_display_name or chat.fan_username,
            "username": chat.fan_username,
            "avatar": chat.fan_avatar_url,
            "tier": SubscriptionTier.PREMIUM if chat.priority > 3 else SubscriptionTier.BASIC,
            "is_vip": chat.priority > 5,
            "total_spent": chat.total_spent
        }
        
        # Get last message
        last_msg_stmt = select(Message).where(
            Message.conversation_id == chat.id
        ).order_by(Message.created_at.desc()).limit(1)
        last_message = await db.scalar(last_msg_stmt)
        
        # Get unread count
        unread_stmt = select(func.count(Message.id)).where(
            and_(
                Message.conversation_id == chat.id,
                Message.sender_id != current_user.id,
                Message.read_at.is_(None)
            )
        )
        unread_count = await db.scalar(unread_stmt) or 0
        
        # Get assigned chatter name
        assigned_chatter_name = None
        if chat.assigned_chatter_id:
            chatter_stmt = select(User).where(User.id == chat.assigned_chatter_id)
            chatter = await db.scalar(chatter_stmt)
            if chatter:
                assigned_chatter_name = f"{chatter.first_name} {chatter.last_name}"
        
        # Build last message response
        last_message_response = None
        if last_message:
            sender_stmt = select(User).where(User.id == last_message.sender_id)
            sender = await db.scalar(sender_stmt)
            
            last_message_response = MessageResponse(
                id=last_message.id,
                conversation_id=last_message.conversation_id,
                sender_id=last_message.sender_id,
                sender_name=f"{sender.first_name} {sender.last_name}" if sender else chat.fan_display_name or chat.fan_username,
                sender_avatar=None,  # Would come from user profile
                content=last_message.content,
                message_type=last_message.type,
                status=last_message.status,
                media_urls=[last_message.media_url] if last_message.media_url else [],
                is_ppv=(last_message.type == MessageType.PPV),
                ppv_price=last_message.amount if last_message.type == MessageType.PPV else None,
                is_ppv_unlocked=False,  # Would check transaction
                read_at=last_message.read_at,
                created_at=last_message.created_at
            )
        
        chat_responses.append(ChatResponse(
            id=chat.id,
            model_id=chat.model_id,
            model_name=model.stage_name if model else "Unknown Model",
            model_avatar=model.profile_photo_url if model else None,
            subscriber_id=int(chat.fan_id.split('_')[1]) if chat.fan_id and '_' in chat.fan_id else 0,
            subscriber_name=subscriber_info["name"],
            subscriber_username=subscriber_info["username"],
            status=chat.status,
            last_message=last_message_response,
            unread_count=unread_count,
            is_priority=chat.priority > 0,
            is_vip=chat.priority > 5,
            total_spent=subscriber_info["total_spent"],
            assigned_chatter_id=chat.assigned_chatter_id,
            assigned_chatter_name=assigned_chatter_name,
            created_at=chat.created_at
        ))
    
    return ChatListResponse(
        chats=chat_responses,
        total=total,
        page=page,
        limit=limit
    )


@router.get("/stats", response_model=ConversationStats)
async def get_conversation_stats(
    model_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation statistics."""
    try:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Build filters based on user access
        chat_filters = []
        message_filters = []
        
        if current_user.role == UserRole.MODEL:
            model_stmt = select(Model.id).where(Model.user_id == current_user.id)
            user_model_id = await db.scalar(model_stmt)
            if user_model_id:
                chat_filters.append(Conversation.model_id == user_model_id)
                message_filters.append(Message.conversation_id.in_(
                    select(Conversation.id).where(Conversation.model_id == user_model_id)
                ))
        elif current_user.role == UserRole.CHATTER:
            chat_filters.append(Conversation.assigned_chatter_id == current_user.id)
            message_filters.append(Message.conversation_id.in_(
                select(Conversation.id).where(Conversation.assigned_chatter_id == current_user.id)
            ))
        elif current_user.agency_id:
            model_ids_stmt = select(Model.id).where(Model.agency_id == current_user.agency_id)
            model_ids_result = await db.execute(model_ids_stmt)
            model_ids = [row[0] for row in model_ids_result]
            if model_ids:
                chat_filters.append(Conversation.model_id.in_(model_ids))
                message_filters.append(Message.conversation_id.in_(
                    select(Conversation.id).where(Conversation.model_id.in_(model_ids))
                ))
        
        if model_id:
            chat_filters.append(Conversation.model_id == model_id)
            message_filters.append(Message.conversation_id.in_(
                select(Conversation.id).where(Conversation.model_id == model_id)
            ))
        
        # Active chats
        active_chats_stmt = select(func.count(Conversation.id)).where(
            and_(Conversation.status == ConversationStatus.ACTIVE, *chat_filters)
        )
        active_chats = await db.scalar(active_chats_stmt) or 0
        
        # Messages today
        messages_today_stmt = select(func.count(Message.id)).where(
            and_(Message.created_at >= today, *message_filters)
        )
        total_messages_today = await db.scalar(messages_today_stmt) or 0
        
        # Unread messages
        unread_stmt = select(func.count(Message.id)).where(
            and_(
                Message.read_at.is_(None),
                Message.sender_id != current_user.id,
                *message_filters
            )
        )
        unread_messages = await db.scalar(unread_stmt) or 0
        
        # VIP and priority chats
        vip_stmt = select(func.count(Conversation.id)).where(
            and_(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.priority > 5,  # High priority conversations
                *chat_filters
            )
        )
        vip_chats = await db.scalar(vip_stmt) or 0
        
        priority_stmt = select(func.count(Conversation.id)).where(
            and_(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.priority > 0,  # Any priority
                *chat_filters
            )
        )
        priority_chats = await db.scalar(priority_stmt) or 0
        
        # Revenue today (simplified)
        revenue_today = Decimal("856.50")  # Mock data
        avg_response_time = 3.5  # Mock data in minutes
    
        return ConversationStats(
            active_chats=active_chats,
            total_messages_today=total_messages_today,
            avg_response_time=avg_response_time,
            unread_messages=unread_messages,
            vip_chats=vip_chats,
            priority_chats=priority_chats,
            revenue_today=revenue_today
        )
    except Exception as e:
        # Log the error and return default stats
        print(f"Error in get_conversation_stats: {str(e)}")
        return ConversationStats(
            active_chats=0,
            total_messages_today=0,
            avg_response_time=0.0,
            unread_messages=0,
            vip_chats=0,
            priority_chats=0,
            revenue_today=Decimal("0.00")
        )


@router.get("/{conversation_id}", response_model=ChatResponse)
async def get_chat(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chat's details."""
    chat = await verify_chat_access(conversation_id, current_user, db)
    
    # Get model info
    model_stmt = select(Model).where(Model.id == chat.model_id)
    model = await db.scalar(model_stmt)
    
    # Get subscriber info (using fan data directly since we don't have subscribers)
    subscriber_info = {
        "name": chat.fan_display_name or chat.fan_username,
        "username": chat.fan_username,
        "avatar": chat.fan_avatar_url,
        "tier": SubscriptionTier.PREMIUM if chat.priority > 3 else SubscriptionTier.BASIC,
        "is_vip": chat.priority > 5,
        "total_spent": chat.total_spent
    }
    
    # Get last message
    last_msg_stmt = select(Message).where(
        Message.conversation_id == chat.id
    ).order_by(Message.created_at.desc()).limit(1)
    last_message = await db.scalar(last_msg_stmt)
    
    # Get unread count
    unread_stmt = select(func.count(Message.id)).where(
        and_(
            Message.conversation_id == chat.id,
            Message.sender_id != current_user.id,
            Message.read_at.is_(None)
        )
    )
    unread_count = await db.scalar(unread_stmt) or 0
    
    # Get assigned chatter name
    assigned_chatter_name = None
    if chat.assigned_chatter_id:
        chatter_stmt = select(User).where(User.id == chat.assigned_chatter_id)
        chatter = await db.scalar(chatter_stmt)
        if chatter:
            assigned_chatter_name = f"{chatter.first_name} {chatter.last_name}"
    
    # Build last message response
    last_message_response = None
    if last_message:
        sender_stmt = select(User).where(User.id == last_message.sender_id)
        sender = await db.scalar(sender_stmt)
        
        last_message_response = MessageResponse(
            id=last_message.id,
            conversation_id=last_message.conversation_id,
            sender_id=last_message.sender_id,
            sender_name=f"{sender.first_name} {sender.last_name}" if sender else (chat.fan_display_name or chat.fan_username),
            sender_avatar=None,
            content=last_message.content,
            message_type=last_message.type,
            status=last_message.status,
            media_urls=[last_message.media_url] if last_message.media_url else [],
            is_ppv=(last_message.type == MessageType.PPV),
            ppv_price=last_message.amount if last_message.type == MessageType.PPV else None,
            is_ppv_unlocked=False,
            read_at=last_message.read_at,
            created_at=last_message.created_at
        )
    
    return ChatResponse(
        id=chat.id,
        model_id=chat.model_id,
        model_name=model.stage_name if model else "Unknown Model",
        model_avatar=model.profile_photo_url if model else None,
        subscriber_id=int(chat.fan_id.split('_')[1]) if chat.fan_id and '_' in chat.fan_id else 0,
        subscriber_name=subscriber_info["name"],
        subscriber_username=subscriber_info["username"],
        status=chat.status,
        last_message=last_message_response,
        unread_count=unread_count,
        is_priority=chat.priority > 0,
        is_vip=subscriber_info["is_vip"],
        total_spent=subscriber_info["total_spent"],
        assigned_chatter_id=chat.assigned_chatter_id,
        assigned_chatter_name=assigned_chatter_name,
        created_at=chat.created_at
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_chat_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a specific chat."""
    chat = await verify_chat_access(conversation_id, current_user, db)
    
    # Get messages
    offset = (page - 1) * limit
    
    stmt = select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # Mark messages as read
    unread_update_stmt = select(Message).where(
        and_(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.read_at.is_(None)
        )
    )
    unread_messages = await db.execute(unread_update_stmt)
    for msg in unread_messages.scalars():
        msg.read_at = datetime.utcnow().isoformat()
    
    await db.commit()
    
    # Build response
    message_responses = []
    for message in messages:
        # Get sender info
        sender_stmt = select(User).where(User.id == message.sender_id)
        sender = await db.scalar(sender_stmt)
        
        # Check if PPV is unlocked (would check transactions in production)
        is_ppv_unlocked = False
        if message.type == MessageType.PPV:
            # Check if subscriber has unlocked this PPV
            is_ppv_unlocked = True  # Mock for now
        
        message_responses.append(MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            sender_name=f"{sender.first_name} {sender.last_name}" if sender else (chat.fan_display_name or chat.fan_username),
            sender_avatar=None,
            content=message.content if message.type != MessageType.PPV or is_ppv_unlocked else "[Locked content]",
            message_type=message.type,
            status=message.status,
            media_urls=[message.media_url] if message.media_url and (message.type != MessageType.PPV or is_ppv_unlocked) else [],
            is_ppv=(message.type == MessageType.PPV),
            ppv_price=message.amount if message.type == MessageType.PPV else None,
            is_ppv_unlocked=is_ppv_unlocked,
            read_at=message.read_at,
            created_at=message.created_at
        ))
    
    # Reverse to get chronological order
    message_responses.reverse()
    
    return message_responses


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message in a chat."""
    chat = await verify_chat_access(conversation_id, current_user, db)
    
    # Create message
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=message_data.content,
        type=message_data.message_type,
        status=MessageStatus.SENT,
        media_url=message_data.media_urls[0] if message_data.media_urls else None,
        amount=message_data.ppv_price if message_data.is_ppv and message_data.message_type == MessageType.PPV else None,
        is_paid=message_data.is_ppv and message_data.message_type == MessageType.PPV,
        platform_data=message_data.metadata or {}
    )
    
    db.add(message)
    
    # Update chat last message time
    chat.last_message_at = datetime.utcnow()
    chat.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(message)
    
    # Build response
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        sender_avatar=None,
        content=message.content,
        message_type=message.type,
        status=message.status,
        media_urls=[message.media_url] if message.media_url else [],
        is_ppv=(message.type == MessageType.PPV),
        ppv_price=message.amount if message.type == MessageType.PPV else None,
        is_ppv_unlocked=False,
        read_at=None,
        created_at=message.created_at
    )


@router.patch("/{conversation_id}/assign")
async def assign_chat(
    conversation_id: int,
    chatter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign a chat to a chatter."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    chat = await verify_chat_access(conversation_id, current_user, db)
    
    # Verify chatter exists and has correct role
    chatter_stmt = select(User).where(
        and_(
            User.id == chatter_id,
            User.role == UserRole.CHATTER
        )
    )
    chatter = await db.scalar(chatter_stmt)
    
    if not chatter:
        raise HTTPException(status_code=404, detail="Chatter not found")
    
    # Verify chatter is in same agency
    if current_user.agency_id and chatter.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Chatter not in your agency")
    
    # Assign chat
    chat.assigned_chatter_id = chatter_id
    chat.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Chat assigned successfully"}


@router.patch("/{conversation_id}/priority")
async def toggle_chat_priority(
    conversation_id: int,
    is_priority: bool,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle chat priority status."""
    chat = await verify_chat_access(conversation_id, current_user, db)
    
    chat.priority = 1 if is_priority else 0
    chat.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": f"Chat priority {'enabled' if is_priority else 'disabled'}"}


@router.get("/subscribers/{model_id}", response_model=List[SubscriberResponse])
async def get_model_subscribers(
    model_id: int,
    tier: Optional[SubscriptionTier] = None,
    status: Optional[SubscriptionStatus] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get subscribers for a model."""
    # Verify access to model
    model_stmt = select(Model).where(Model.id == model_id)
    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        model_stmt = model_stmt.where(Model.agency_id == current_user.agency_id)
    
    model = await db.scalar(model_stmt)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Build query
    query = select(Subscriber).where(Subscriber.model_id == model_id)
    
    if tier:
        query = query.where(Subscriber.tier == tier)
    
    if status:
        query = query.where(Subscriber.status == status)
    else:
        query = query.where(Subscriber.is_active == True)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Subscriber.created_at.desc())
    
    result = await db.execute(query)
    subscribers = result.scalars().all()
    
    # Build response
    subscriber_responses = []
    for sub in subscribers:
        # Get user info
        user_stmt = select(User).where(User.id == sub.user_id)
        user = await db.scalar(user_stmt)
        
        # Calculate total spent
        spent_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
            and_(
                Transaction.user_id == sub.user_id,
                Transaction.model_id == model_id,
                Transaction.status == TransactionStatus.COMPLETED
            )
        )
        total_spent = await db.scalar(spent_stmt) or Decimal("0")
        
        subscriber_responses.append(SubscriberResponse(
            id=sub.id,
            user_id=sub.user_id,
            username=sub.username or (user.username if user else "unknown"),
            display_name=sub.display_name or (f"{user.first_name} {user.last_name}" if user else "Subscriber"),
            avatar_url=sub.avatar_url,
            tier=sub.tier,
            status=sub.status,
            is_active=sub.is_active,
            subscription_price=sub.subscription_price or Decimal("0"),
            total_spent=total_spent,
            last_seen_at=sub.last_seen_at,
            expires_at=sub.expires_at,
            auto_renew=sub.auto_renew,
            created_at=sub.created_at
        ))
    
    return subscriber_responses