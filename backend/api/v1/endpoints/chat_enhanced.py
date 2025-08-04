"""Enhanced chat API endpoints with encryption, media, and analytics."""

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.database import get_db
from core.dependencies import CurrentUser, get_current_active_user
from core.errors import NotFoundError, AuthorizationError
from core.logger import get_logger
from models.user import User, UserRole
from models.chat import Conversation, Message
from services.chat_encryption import ChatEncryptionService
from services.chat_media import ChatMediaService
from services.chat_moderation import ChatModerationService
from services.chat_analytics import ChatAnalyticsService
from api.v1.schemas.chat import MessageResponse, ConversationResponse

logger = get_logger(__name__)
router = APIRouter()


# Encryption endpoints
@router.post("/conversations/{conversation_id}/enable-e2e")
async def enable_e2e_encryption(
    conversation_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Enable end-to-end encryption for a conversation."""
    # Verify access
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
    
    # Only models and admins can enable E2E
    if current_user.role not in [UserRole.MODEL, UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    encryption_service = ChatEncryptionService(db)
    await encryption_service.enable_e2e_encryption(conversation_id)
    
    return {"status": "success", "message": "E2E encryption enabled"}


@router.post("/conversations/{conversation_id}/rotate-key")
async def rotate_encryption_key(
    conversation_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Rotate encryption key for a conversation."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    encryption_service = ChatEncryptionService(db)
    await encryption_service.rotate_conversation_key(conversation_id)
    
    return {"status": "success", "message": "Encryption key rotated"}


# Media endpoints
@router.post("/conversations/{conversation_id}/upload-media")
async def upload_media(
    conversation_id: int,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    encrypt: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """Upload media for a conversation."""
    # Verify access to conversation
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
    
    media_service = ChatMediaService(db)
    
    try:
        media_info = await media_service.upload_media(
            file=file,
            user=current_user,
            conversation_id=conversation_id,
            encrypt=encrypt
        )
        
        return {
            "status": "success",
            "media": media_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media upload failed: {e}")
        raise HTTPException(status_code=500, detail="Media upload failed")


@router.get("/conversations/{conversation_id}/media")
async def get_conversation_media(
    conversation_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    media_type: Optional[str] = None,
    limit: int = Query(50, le=100)
):
    """Get all media from a conversation."""
    media_service = ChatMediaService(db)
    
    media_items = await media_service.get_conversation_media(
        conversation_id=conversation_id,
        user=current_user,
        media_type=media_type,
        limit=limit
    )
    
    return {
        "conversation_id": conversation_id,
        "media": media_items,
        "count": len(media_items)
    }


@router.delete("/messages/{message_id}/media")
async def delete_message_media(
    message_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Delete media from a message."""
    message = await db.get(Message, message_id)
    if not message:
        raise NotFoundError("Message", message_id)
    
    media_service = ChatMediaService(db)
    await media_service.delete_media(message, current_user)
    
    return {"status": "success", "message": "Media deleted"}


# Moderation endpoints
@router.post("/messages/{message_id}/flag")
async def flag_message(
    message_id: int,
    reason: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Flag a message for moderation."""
    message = await db.get(Message, message_id)
    if not message:
        raise NotFoundError("Message", message_id)
    
    message.is_flagged = True
    message.flagged_reason = f"User flagged: {reason}"
    
    await db.commit()
    
    logger.info(f"Message {message_id} flagged by user {current_user.id}")
    
    return {"status": "success", "message": "Message flagged for review"}


@router.get("/moderation/flagged-messages")
async def get_flagged_messages(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100)
):
    """Get flagged messages for review (admin/agency owner only)."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    moderation_service = ChatModerationService(db)
    flagged = await moderation_service.review_flagged_messages(
        reviewer=current_user,
        limit=limit
    )
    
    return {
        "messages": flagged,
        "count": len(flagged)
    }


@router.post("/moderation/messages/{message_id}/approve")
async def approve_flagged_message(
    message_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Approve a flagged message."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    moderation_service = ChatModerationService(db)
    await moderation_service.approve_message(message_id, current_user)
    
    return {"status": "success", "message": "Message approved"}


@router.delete("/moderation/messages/{message_id}")
async def delete_flagged_message(
    message_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Delete a flagged message."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    moderation_service = ChatModerationService(db)
    await moderation_service.delete_flagged_message(message_id, current_user)
    
    return {"status": "success", "message": "Message deleted"}


@router.post("/conversations/{conversation_id}/block")
async def block_conversation(
    conversation_id: int,
    reason: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Block a conversation."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER, UserRole.MODEL]:
        raise AuthorizationError("Insufficient permissions")
    
    moderation_service = ChatModerationService(db)
    await moderation_service.block_conversation(
        conversation_id=conversation_id,
        blocked_by=current_user,
        reason=reason
    )
    
    return {"status": "success", "message": "Conversation blocked"}


@router.get("/moderation/stats")
async def get_moderation_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=90)
):
    """Get moderation statistics."""
    if current_user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
        raise AuthorizationError("Insufficient permissions")
    
    moderation_service = ChatModerationService(db)
    
    agency_id = None
    if current_user.role == UserRole.AGENCY_OWNER:
        agency_id = current_user.agency_id
    
    stats = await moderation_service.get_moderation_stats(
        agency_id=agency_id,
        days=days
    )
    
    return stats


# Analytics endpoints
@router.get("/conversations/{conversation_id}/analytics")
async def get_conversation_analytics(
    conversation_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed analytics for a conversation."""
    analytics_service = ChatAnalyticsService(db)
    
    try:
        analytics = await analytics_service.get_conversation_metrics(
            conversation_id=conversation_id,
            user=current_user
        )
        
        return analytics
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/models/{model_id}/chat-analytics")
async def get_model_chat_analytics(
    model_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    period_days: int = Query(30, ge=1, le=365)
):
    """Get chat analytics for a model."""
    analytics_service = ChatAnalyticsService(db)
    
    try:
        analytics = await analytics_service.get_model_analytics(
            model_id=model_id,
            user=current_user,
            period_days=period_days
        )
        
        return analytics
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/agencies/{agency_id}/chat-analytics")
async def get_agency_chat_analytics(
    agency_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    period_days: int = Query(30, ge=1, le=365)
):
    """Get chat analytics for an agency."""
    analytics_service = ChatAnalyticsService(db)
    
    try:
        analytics = await analytics_service.get_agency_analytics(
            agency_id=agency_id,
            user=current_user,
            period_days=period_days
        )
        
        return analytics
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/conversations/{conversation_id}/report")
async def generate_conversation_report(
    conversation_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Generate a comprehensive report for a conversation."""
    analytics_service = ChatAnalyticsService(db)
    
    try:
        report = await analytics_service.generate_conversation_report(
            conversation_id=conversation_id,
            user=current_user
        )
        
        return report
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


# Conversation tags
@router.post("/conversations/{conversation_id}/tags")
async def add_conversation_tag(
    conversation_id: int,
    tag: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Add a tag to a conversation."""
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
    
    # Update tags in metadata
    if not conversation.tags:
        conversation.tags = []
    
    if tag not in conversation.tags:
        conversation.tags.append(tag)
        await db.commit()
    
    return {"status": "success", "tags": conversation.tags}


@router.delete("/conversations/{conversation_id}/tags/{tag}")
async def remove_conversation_tag(
    conversation_id: int,
    tag: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Remove a tag from a conversation."""
    conversation = await db.get(Conversation, conversation_id)
    if not conversation:
        raise NotFoundError("Conversation", conversation_id)
    
    if conversation.tags and tag in conversation.tags:
        conversation.tags.remove(tag)
        await db.commit()
    
    return {"status": "success", "tags": conversation.tags}