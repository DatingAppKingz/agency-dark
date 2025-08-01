"""Chat API endpoints for conversation and message management."""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from core.database import get_db
from core.dependencies import CurrentUser, get_current_active_user
from core.errors import NotFoundError, AuthorizationError, ValidationError as AppValidationError
from core.logger import get_logger
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model
from models.chat import (
    Conversation, ConversationStatus,
    Message, MessageType, MessageStatus,
    ChatTemplate
)
from api.v1.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    ChatTemplateCreate,
    ChatTemplateUpdate,
    ChatTemplateResponse,
    PaginatedConversations,
    PaginatedMessages,
    ConversationStats
)

logger = get_logger(__name__)
router = APIRouter()


# Helper functions
async def get_conversation_for_user(
    conversation_id: int,
    user: User,
    db: AsyncSession
) -> Conversation:
    """Get conversation with permission check."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    
    # Apply agency filter for multi-tenant access
    if user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        stmt = stmt.where(Conversation.agency_id == user.agency_id)
    
    conversation = await db.scalar(stmt)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
    
    # Check if user has access
    if user.role == UserRole.MODEL:
        # Models can only see their own conversations
        model = await db.scalar(
            select(Model).where(Model.user_id == user.id)
        )
        if not model or conversation.model_id != model.id:
            raise AuthorizationError("You don't have access to this conversation")
    elif user.role == UserRole.CHATTER:
        # Chatters can only see assigned conversations
        if conversation.assigned_chatter_id != user.id:
            raise AuthorizationError("This conversation is not assigned to you")
    
    return conversation


# Conversation endpoints
@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    model_id: Optional[int] = None,
    status: Optional[ConversationStatus] = None,
    assigned_to_me: bool = False,
    search: Optional[str] = None,
    sort_by: str = Query("last_message_at", regex="^(last_message_at|created_at|priority|total_spent)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List conversations with filtering and pagination."""
    stmt = select(Conversation)
    
    # Apply agency filter
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        stmt = stmt.where(Conversation.agency_id == current_user.agency_id)
    
    # Apply filters
    if model_id:
        stmt = stmt.where(Conversation.model_id == model_id)
    
    if status:
        stmt = stmt.where(Conversation.status == status)
    
    if assigned_to_me and current_user.role == UserRole.CHATTER:
        stmt = stmt.where(Conversation.assigned_chatter_id == current_user.id)
    
    if search:
        stmt = stmt.where(
            or_(
                Conversation.fan_username.ilike(f"%{search}%"),
                Conversation.fan_display_name.ilike(f"%{search}%"),
                Conversation.notes.ilike(f"%{search}%")
            )
        )
    
    # Apply role-based filters
    if current_user.role == UserRole.MODEL:
        # Models only see their own conversations
        model = await db.scalar(
            select(Model).where(Model.user_id == current_user.id)
        )
        if model:
            stmt = stmt.where(Conversation.model_id == model.id)
        else:
            return PaginatedConversations(items=[], total=0, page=page, pages=0)
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)
    
    # Apply sorting
    order_column = getattr(Conversation, sort_by)
    if sort_order == "desc":
        stmt = stmt.order_by(order_column.desc())
    else:
        stmt = stmt.order_by(order_column.asc())
    
    # Apply pagination
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    
    # Load relationships
    stmt = stmt.options(
        selectinload(Conversation.model),
        selectinload(Conversation.assigned_chatter)
    )
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    
    return PaginatedConversations(
        items=[ConversationResponse.from_orm(conv) for conv in conversations],
        total=total,
        page=page,
        pages=(total + limit - 1) // limit
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific conversation."""
    conversation = await get_conversation_for_user(conversation_id, current_user, db)
    return ConversationResponse.from_orm(conversation)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER, UserRole.MODEL]:
        raise AuthorizationError("You don't have permission to create conversations")
    
    # Verify model exists and user has access
    model = await db.get(Model, data.model_id)
    if not model:
        raise NotFoundError("Model", data.model_id)
    
    if current_user.role == UserRole.MODEL:
        # Models can only create conversations for themselves
        if model.user_id != current_user.id:
            raise AuthorizationError("You can only create conversations for yourself")
    elif current_user.agency_id != model.agency_id:
        raise AuthorizationError("Model doesn't belong to your agency")
    
    # Check if conversation already exists
    existing = await db.scalar(
        select(Conversation).where(
            and_(
                Conversation.model_id == data.model_id,
                Conversation.fan_id == data.fan_id
            )
        )
    )
    
    if existing:
        return ConversationResponse.from_orm(existing)
    
    # Create conversation
    conversation = Conversation(
        **data.dict(),
        agency_id=model.agency_id
    )
    
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    logger.log_business_event(
        "conversation_created",
        "Conversation",
        conversation.id,
        model_id=model.id,
        fan_id=data.fan_id
    )
    
    return ConversationResponse.from_orm(conversation)


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update conversation details."""
    conversation = await get_conversation_for_user(conversation_id, current_user, db)
    
    # Update fields
    update_data = data.dict(exclude_unset=True)
    
    # Handle chatter assignment
    if "assigned_chatter_id" in update_data:
        if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            raise AuthorizationError("You don't have permission to assign chatters")
        
        if update_data["assigned_chatter_id"]:
            # Verify chatter exists and belongs to agency
            chatter = await db.get(User, update_data["assigned_chatter_id"])
            if not chatter or chatter.agency_id != conversation.agency_id:
                raise NotFoundError("Chatter", update_data["assigned_chatter_id"])
            
            update_data["assigned_at"] = datetime.utcnow().isoformat()
    
    for field, value in update_data.items():
        setattr(conversation, field, value)
    
    await db.commit()
    await db.refresh(conversation)
    
    return ConversationResponse.from_orm(conversation)


@router.get("/conversations/{conversation_id}/stats", response_model=ConversationStats)
async def get_conversation_stats(
    conversation_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation statistics."""
    conversation = await get_conversation_for_user(conversation_id, current_user, db)
    
    # Get message counts
    message_stats = await db.execute(
        select(
            func.count(Message.id).label("total_messages"),
            func.count(Message.id).filter(Message.sender_type == "fan").label("fan_messages"),
            func.count(Message.id).filter(Message.sender_type != "fan").label("our_messages"),
            func.avg(Message.amount).filter(Message.type == MessageType.TIP).label("avg_tip"),
            func.sum(Message.amount).filter(Message.type == MessageType.TIP).label("total_tips"),
            func.count(Message.id).filter(Message.type == MessageType.PPV).label("ppv_count"),
            func.sum(Message.amount).filter(
                and_(Message.type == MessageType.PPV, Message.is_paid == True)
            ).label("ppv_revenue")
        ).where(Message.conversation_id == conversation_id)
    )
    
    stats = message_stats.one()
    
    return ConversationStats(
        conversation_id=conversation_id,
        total_messages=stats.total_messages or 0,
        fan_messages=stats.fan_messages or 0,
        our_messages=stats.our_messages or 0,
        avg_tip_amount=float(stats.avg_tip or 0),
        total_tips_amount=float(stats.total_tips or 0),
        ppv_sent=stats.ppv_count or 0,
        ppv_revenue=float(stats.ppv_revenue or 0),
        total_revenue=conversation.total_spent
    )


# Message endpoints
@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessages)
async def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = None,
    after_id: Optional[int] = None,
    message_type: Optional[MessageType] = None,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List messages in a conversation with pagination."""
    conversation = await get_conversation_for_user(conversation_id, current_user, db)
    
    stmt = select(Message).where(
        and_(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False
        )
    )
    
    # Apply filters
    if before_id:
        stmt = stmt.where(Message.id < before_id)
    
    if after_id:
        stmt = stmt.where(Message.id > after_id)
    
    if message_type:
        stmt = stmt.where(Message.type == message_type)
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt)
    
    # Order by created_at descending (newest first)
    stmt = stmt.order_by(Message.created_at.desc())
    
    # Apply pagination
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    
    # Load sender relationship
    stmt = stmt.options(selectinload(Message.sender))
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # Mark messages as read if from fan
    if messages and current_user.role in [UserRole.MODEL, UserRole.CHATTER]:
        unread_ids = [
            msg.id for msg in messages 
            if msg.sender_type == "fan" and not msg.read_at
        ]
        
        if unread_ids:
            await db.execute(
                update(Message).where(
                    Message.id.in_(unread_ids)
                ).values(
                    read_at=datetime.utcnow().isoformat(),
                    status=MessageStatus.READ
                )
            )
            
            # Update conversation unread count
            conversation.unread_count = max(0, conversation.unread_count - len(unread_ids))
            
            await db.commit()
    
    return PaginatedMessages(
        items=[MessageResponse.from_orm(msg) for msg in messages],
        total=total,
        page=page,
        pages=(total + limit - 1) // limit
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    data: MessageCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message in a conversation."""
    conversation = await get_conversation_for_user(conversation_id, current_user, db)
    
    # Determine sender type
    if current_user.role == UserRole.MODEL:
        sender_type = "model"
    elif current_user.role == UserRole.CHATTER:
        sender_type = "chatter"
    else:
        sender_type = "system"
    
    # Create message
    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        sender_type=sender_type,
        agency_id=conversation.agency_id,
        **data.dict()
    )
    
    # Update conversation
    conversation.last_message_at = datetime.utcnow().isoformat()
    if sender_type != "fan":
        # Update response metrics
        if conversation.last_fan_message_at:
            # Calculate response time
            pass  # TODO: Update conversation analytics
    
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    logger.info(
        f"Message sent in conversation {conversation_id}",
        extra={
            "conversation_id": conversation_id,
            "message_id": message.id,
            "sender_type": sender_type,
            "message_type": message.type
        }
    )
    
    # TODO: Emit socket.io event for real-time delivery
    
    return MessageResponse.from_orm(message)


@router.put("/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    data: MessageUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a message (mark as read, flag, etc)."""
    # Get message with permission check
    stmt = select(Message).where(Message.id == message_id)
    
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        stmt = stmt.where(Message.agency_id == current_user.agency_id)
    
    message = await db.scalar(stmt)
    if not message:
        raise NotFoundError("Message", message_id)
    
    # Get conversation for additional permission check
    conversation = await get_conversation_for_user(message.conversation_id, current_user, db)
    
    # Update fields
    update_data = data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(message, field, value)
    
    await db.commit()
    await db.refresh(message)
    
    return MessageResponse.from_orm(message)


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a message."""
    # Get message with permission check
    stmt = select(Message).where(Message.id == message_id)
    
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        stmt = stmt.where(Message.agency_id == current_user.agency_id)
    
    message = await db.scalar(stmt)
    if not message:
        raise NotFoundError("Message", message_id)
    
    # Only allow deletion by sender or admin
    if message.sender_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("You can only delete your own messages")
    
    # Soft delete
    message.is_deleted = True
    await db.commit()
    
    return {"status": "deleted"}


# Chat templates endpoints
@router.get("/templates", response_model=List[ChatTemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    is_active: bool = True,
    search: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List chat templates for the agency."""
    stmt = select(ChatTemplate).where(
        and_(
            ChatTemplate.agency_id == current_user.agency_id,
            ChatTemplate.is_active == is_active
        )
    )
    
    if category:
        stmt = stmt.where(ChatTemplate.category == category)
    
    if search:
        stmt = stmt.where(
            or_(
                ChatTemplate.name.ilike(f"%{search}%"),
                ChatTemplate.content.ilike(f"%{search}%")
            )
        )
    
    stmt = stmt.order_by(ChatTemplate.usage_count.desc(), ChatTemplate.name)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return [ChatTemplateResponse.from_orm(t) for t in templates]


@router.post("/templates", response_model=ChatTemplateResponse)
async def create_template(
    data: ChatTemplateCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat template."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("You don't have permission to create templates")
    
    template = ChatTemplate(
        **data.dict(),
        agency_id=current_user.agency_id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return ChatTemplateResponse.from_orm(template)


@router.put("/templates/{template_id}", response_model=ChatTemplateResponse)
async def update_template(
    template_id: int,
    data: ChatTemplateUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a chat template."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("You don't have permission to update templates")
    
    template = await db.get(ChatTemplate, template_id)
    if not template or template.agency_id != current_user.agency_id:
        raise NotFoundError("Template", template_id)
    
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    await db.commit()
    await db.refresh(template)
    
    return ChatTemplateResponse.from_orm(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat template."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("You don't have permission to delete templates")
    
    template = await db.get(ChatTemplate, template_id)
    if not template or template.agency_id != current_user.agency_id:
        raise NotFoundError("Template", template_id)
    
    await db.delete(template)
    await db.commit()
    
    return {"status": "deleted"}


# WebSocket endpoint for real-time chat
@router.websocket("/ws/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for real-time chat updates."""
    await websocket.accept()
    
    try:
        # TODO: Implement authentication for WebSocket
        # TODO: Join conversation room
        # TODO: Handle incoming messages
        # TODO: Broadcast to other connected clients
        
        while True:
            data = await websocket.receive_text()
            # Process message
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        # TODO: Leave conversation room
        logger.info(f"WebSocket disconnected for conversation {conversation_id}")