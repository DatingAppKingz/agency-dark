"""
Mobile Messages API Endpoints

Optimized for mobile with:
- Pagination for limited bandwidth
- Compressed responses
- Real-time updates via websocket
- Offline message queue support
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from pydantic import BaseModel, Field
import uuid

from core.database import get_db
from core.security_v2 import get_current_user
from core.logging import get_logger
from models.chat import Message
from models.chat import Conversation
from models.user import User

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/api/v1/mobile/messages")


class MobileMessageRequest(BaseModel):
    """Mobile message request"""
    conversation_id: uuid.UUID
    content: str
    attachments: Optional[List[Dict[str, Any]]] = None
    offline_id: Optional[str] = None  # For offline sync


class MobileMessageResponse(BaseModel):
    """Compressed message response for mobile"""
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_avatar: Optional[str]
    content: str
    timestamp: datetime
    read: bool
    attachments: Optional[List[Dict[str, Any]]]
    offline_id: Optional[str]


class MobileConversationResponse(BaseModel):
    """Mobile conversation with last message"""
    id: str
    participant_id: str
    participant_name: str
    participant_avatar: Optional[str]
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int
    is_online: bool


class MessageSyncRequest(BaseModel):
    """Sync messages from offline queue"""
    messages: List[MobileMessageRequest]
    last_sync_timestamp: datetime


@router.get("/conversations", response_model=List[MobileConversationResponse])
async def get_mobile_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's conversations for mobile"""
    
    user_id = uuid.UUID(current_user["user_id"])
    offset = (page - 1) * limit
    
    # Get conversations with last message
    conversations = await db.execute(
        select(
            Conversation,
            User,
            Message
        )
        .join(
            User,
            or_(
                and_(Conversation.user1_id == user_id, User.id == Conversation.user2_id),
                and_(Conversation.user2_id == user_id, User.id == Conversation.user1_id)
            )
        )
        .outerjoin(
            Message,
            Message.id == Conversation.last_message_id
        )
        .where(
            or_(
                Conversation.user1_id == user_id,
                Conversation.user2_id == user_id
            )
        )
        .order_by(desc(Conversation.updated_at))
        .offset(offset)
        .limit(limit)
    )
    
    results = []
    for conv, participant, last_msg in conversations:
        # Count unread messages
        unread = await db.execute(
            select(Message)
            .where(
                and_(
                    Message.conversation_id == conv.id,
                    Message.sender_id != user_id,
                    Message.read == False
                )
            )
        )
        unread_count = len(unread.all())
        
        results.append(MobileConversationResponse(
            id=str(conv.id),
            participant_id=str(participant.id),
            participant_name=participant.full_name,
            participant_avatar=participant.avatar_url,
            last_message=last_msg.content if last_msg else None,
            last_message_time=last_msg.created_at if last_msg else None,
            unread_count=unread_count,
            is_online=False  # Would check online status in production
        ))
    
    return results


@router.get("/conversation/{conversation_id}/messages", response_model=List[MobileMessageResponse])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a conversation"""
    
    user_id = uuid.UUID(current_user["user_id"])
    offset = (page - 1) * limit
    
    # Verify user is part of conversation
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or (conversation.user1_id != user_id and conversation.user2_id != user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages
    messages = await db.execute(
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .offset(offset)
        .limit(limit)
    )
    
    # Mark messages as read
    await db.execute(
        select(Message)
        .where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.read == False
            )
        )
    )
    await db.commit()
    
    results = []
    for msg, sender in messages:
        results.append(MobileMessageResponse(
            id=str(msg.id),
            conversation_id=str(msg.conversation_id),
            sender_id=str(sender.id),
            sender_name=sender.full_name,
            sender_avatar=sender.avatar_url,
            content=msg.content,
            timestamp=msg.created_at,
            read=msg.read,
            attachments=msg.attachments,
            offline_id=None
        ))
    
    return results


@router.post("/send", response_model=MobileMessageResponse)
async def send_mobile_message(
    request: MobileMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message from mobile"""
    
    user_id = uuid.UUID(current_user["user_id"])
    
    # Verify user is part of conversation
    conversation = await db.get(Conversation, request.conversation_id)
    if not conversation or (conversation.user1_id != user_id and conversation.user2_id != user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Create message
    message = Message(
        id=uuid.uuid4(),
        conversation_id=request.conversation_id,
        sender_id=user_id,
        content=request.content,
        attachments=request.attachments,
        read=False,
        created_at=datetime.utcnow()
    )
    
    db.add(message)
    
    # Update conversation
    conversation.last_message_id = message.id
    conversation.updated_at = datetime.utcnow()
    
    await db.commit()
    
    # Get sender info
    sender = await db.get(User, user_id)
    
    # Send push notification to recipient
    from modules.notifications.push_service import push_service
    
    notification_result = await push_service.send_push_notification(
        db=db,
        user_id=UUID(recipient_id),
        title=f"New message from {sender.full_name}",
        body=content[:100] + "..." if len(content) > 100 else content,
        data={
            "type": "message",
            "conversation_id": str(conversation.id),
            "sender_id": str(sender.id),
            "message_id": str(message.id)
        },
        image_url=sender.avatar_url,
        action_url=f"/conversations/{conversation.id}",
        priority="high"
    )
    
    logger.info(f"Push notification result: {notification_result}")
    
    # Emit websocket event
    from core.realtime.socketio_server import sio
    
    await sio.emit(
        'new_message',
        {
            'conversation_id': str(conversation.id),
            'message': {
                'id': str(message.id),
                'sender_id': str(sender.id),
                'sender_name': sender.full_name,
                'content': content,
                'timestamp': message.created_at.isoformat()
            }
        },
        room=f"user_{recipient_id}"
    )
    
    return MobileMessageResponse(
        id=str(message.id),
        conversation_id=str(message.conversation_id),
        sender_id=str(sender.id),
        sender_name=sender.full_name,
        sender_avatar=sender.avatar_url,
        content=message.content,
        timestamp=message.created_at,
        read=message.read,
        attachments=message.attachments,
        offline_id=request.offline_id
    )


@router.post("/sync", response_model=Dict[str, Any])
async def sync_offline_messages(
    request: MessageSyncRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sync messages created offline"""
    
    user_id = uuid.UUID(current_user["user_id"])
    synced_messages = []
    failed_messages = []
    
    for msg_request in request.messages:
        try:
            # Send message
            message = await send_mobile_message(msg_request, current_user, db)
            synced_messages.append({
                "offline_id": msg_request.offline_id,
                "server_id": message.id,
                "status": "synced"
            })
        except Exception as e:
            logger.error(f"Failed to sync message {msg_request.offline_id}: {e}")
            failed_messages.append({
                "offline_id": msg_request.offline_id,
                "error": str(e),
                "status": "failed"
            })
    
    # Get new messages since last sync
    new_messages = await db.execute(
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            and_(
                or_(
                    Conversation.user1_id == user_id,
                    Conversation.user2_id == user_id
                ),
                Message.created_at > request.last_sync_timestamp
            )
        )
        .order_by(Message.created_at)
    )
    
    new_messages_list = []
    for msg, sender in new_messages:
        new_messages_list.append(MobileMessageResponse(
            id=str(msg.id),
            conversation_id=str(msg.conversation_id),
            sender_id=str(sender.id),
            sender_name=sender.full_name,
            sender_avatar=sender.avatar_url,
            content=msg.content,
            timestamp=msg.created_at,
            read=msg.read,
            attachments=msg.attachments,
            offline_id=None
        ))
    
    return {
        "synced_messages": synced_messages,
        "failed_messages": failed_messages,
        "new_messages": new_messages_list,
        "sync_timestamp": datetime.utcnow()
    }


@router.put("/conversation/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all messages in conversation as read"""
    
    user_id = uuid.UUID(current_user["user_id"])
    
    # Verify user is part of conversation
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or (conversation.user1_id != user_id and conversation.user2_id != user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Mark messages as read
    result = await db.execute(
        select(Message)
        .where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sender_id != user_id,
                Message.read == False
            )
        )
    )
    
    messages = result.scalars().all()
    for message in messages:
        message.read = True
    
    await db.commit()
    
    return {"messages_marked": len(messages)}


@router.delete("/message/{message_id}")
async def delete_mobile_message(
    message_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message (soft delete)"""
    
    user_id = uuid.UUID(current_user["user_id"])
    
    # Get message
    message = await db.get(Message, message_id)
    if not message or message.sender_id != user_id:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Soft delete
    message.deleted_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Message deleted"}