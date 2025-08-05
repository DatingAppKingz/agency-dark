"""Media handling service for chat messages."""

import os
import uuid
import mimetypes
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import aiofiles
from PIL import Image
try:
    import magic
except ImportError:
    magic = None

from core.config import settings
from core.storage import storage_service
from core.logger import get_logger
from models.chat import Message, MessageType
from models.user import User, UserRole
from services.chat_encryption import ChatEncryptionService

logger = get_logger(__name__)


class ChatMediaService:
    """Service for handling media in chat messages."""
    
    # Allowed file types and size limits
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
    }
    ALLOWED_VIDEO_TYPES = {
        'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo'
    }
    ALLOWED_AUDIO_TYPES = {
        'audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/ogg'
    }
    ALLOWED_DOCUMENT_TYPES = {
        'application/pdf', 'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    }
    
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB
    MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5MB
    
    THUMBNAIL_SIZE = (300, 300)
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption_service = ChatEncryptionService(db)
        self.upload_path = os.path.join(settings.MEDIA_ROOT, 'chat')
        os.makedirs(self.upload_path, exist_ok=True)
    
    async def upload_media(
        self,
        file: UploadFile,
        user: User,
        conversation_id: int,
        encrypt: bool = False
    ) -> Dict[str, Any]:
        """Upload and process media file."""
        # Validate file
        await self._validate_file(file)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(self.upload_path, unique_filename)
        
        # Save file temporarily
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        try:
            # Detect file type
            if magic:
                mime_type = magic.from_file(file_path, mime=True)
            else:
                # Fallback to mimetypes if magic is not available
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = 'application/octet-stream'
            message_type = self._get_message_type(mime_type)
            
            # Process based on type
            media_url = None
            thumbnail_url = None
            
            if message_type == MessageType.IMAGE:
                # Generate thumbnail
                thumbnail_path = await self._generate_thumbnail(file_path, unique_filename)
                
                # Upload to storage
                media_url = await storage_service.upload_file(
                    file_path, 
                    f"chat/{conversation_id}/{unique_filename}"
                )
                
                if thumbnail_path:
                    thumbnail_url = await storage_service.upload_file(
                        thumbnail_path,
                        f"chat/{conversation_id}/thumb_{unique_filename}"
                    )
                    os.unlink(thumbnail_path)
                    
            elif message_type in [MessageType.VIDEO, MessageType.AUDIO]:
                # For video/audio, generate thumbnail if possible
                if message_type == MessageType.VIDEO:
                    thumbnail_path = await self._generate_video_thumbnail(file_path, unique_filename)
                    if thumbnail_path:
                        thumbnail_url = await storage_service.upload_file(
                            thumbnail_path,
                            f"chat/{conversation_id}/thumb_{unique_filename}"
                        )
                        os.unlink(thumbnail_path)
                
                # Upload media
                media_url = await storage_service.upload_file(
                    file_path,
                    f"chat/{conversation_id}/{unique_filename}"
                )
            
            # Calculate file hash for deduplication
            file_hash = await self._calculate_file_hash(file_path)
            
            # Clean up temporary file
            os.unlink(file_path)
            
            return {
                'media_url': media_url,
                'thumbnail_url': thumbnail_url,
                'message_type': message_type.value,
                'mime_type': mime_type,
                'file_size': len(content),
                'file_hash': file_hash,
                'original_filename': file.filename,
                'encrypted': encrypt
            }
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(file_path):
                os.unlink(file_path)
            logger.error(f"Media upload failed: {e}")
            raise HTTPException(status_code=500, detail="Media upload failed")
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', 
                           '.mpeg', '.mov', '.avi', '.mp3', '.wav', '.ogg',
                           '.pdf', '.doc', '.docx', '.txt']:
            raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed")
        
        # Check content type
        if file.content_type:
            allowed_types = (
                self.ALLOWED_IMAGE_TYPES | 
                self.ALLOWED_VIDEO_TYPES | 
                self.ALLOWED_AUDIO_TYPES |
                self.ALLOWED_DOCUMENT_TYPES
            )
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Content type {file.content_type} not allowed"
                )
    
    def _get_message_type(self, mime_type: str) -> MessageType:
        """Get message type from MIME type."""
        if mime_type in self.ALLOWED_IMAGE_TYPES:
            return MessageType.IMAGE
        elif mime_type in self.ALLOWED_VIDEO_TYPES:
            return MessageType.VIDEO
        elif mime_type in self.ALLOWED_AUDIO_TYPES:
            return MessageType.AUDIO
        else:
            return MessageType.TEXT  # Treat documents as text with attachment
    
    async def _generate_thumbnail(self, image_path: str, filename: str) -> Optional[str]:
        """Generate thumbnail for image."""
        try:
            thumb_path = os.path.join(self.upload_path, f"thumb_{filename}")
            
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background
                
                # Generate thumbnail
                img.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                img.save(thumb_path, 'JPEG', quality=85)
            
            return thumb_path
            
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return None
    
    async def _generate_video_thumbnail(self, video_path: str, filename: str) -> Optional[str]:
        """Generate thumbnail for video (requires ffmpeg)."""
        try:
            import subprocess
            
            thumb_path = os.path.join(self.upload_path, f"thumb_{filename}.jpg")
            
            # Extract frame at 1 second
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-vf', 'scale=300:-1',
                thumb_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(thumb_path):
                return thumb_path
            
            return None
            
        except Exception as e:
            logger.error(f"Video thumbnail generation failed: {e}")
            return None
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    async def get_media_url(
        self,
        message: Message,
        user: User,
        quality: str = 'original'
    ) -> Optional[str]:
        """Get media URL with access control."""
        if not message.media_url:
            return None
        
        # Check permissions
        if not await self._can_access_media(message, user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # For PPV content, check if paid
        if message.type == MessageType.PPV and not message.is_paid:
            # Return blur/preview URL instead
            return message.thumbnail_url
        
        # Generate signed URL for secure access
        return await storage_service.get_signed_url(
            message.media_url,
            expires_in=3600  # 1 hour
        )
    
    async def _can_access_media(self, message: Message, user: User) -> bool:
        """Check if user can access media."""
        # Admin/agency owner can access all
        if user.role in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            return True
        
        # Check if user is part of conversation
        conversation = await self.db.get(Conversation, message.conversation_id)
        if not conversation:
            return False
        
        # Model can access their own conversation media
        if user.role == UserRole.MODEL:
            from models.model import Model
            model = await self.db.scalar(
                select(Model).where(Model.user_id == user.id)
            )
            if model and conversation.model_id == model.id:
                return True
        
        # Chatter can access assigned conversation media
        if user.role == UserRole.CHATTER:
            if conversation.assigned_chatter_id == user.id:
                return True
        
        return False
    
    async def delete_media(self, message: Message, user: User) -> None:
        """Delete media files."""
        # Check permissions
        if message.sender_id != user.id and user.role not in [UserRole.ADMIN, UserRole.AGENCY_OWNER]:
            raise HTTPException(status_code=403, detail="Cannot delete this media")
        
        # Delete from storage
        if message.media_url:
            await storage_service.delete_file(message.media_url)
        
        if message.thumbnail_url:
            await storage_service.delete_file(message.thumbnail_url)
        
        # Update message
        message.media_url = None
        message.thumbnail_url = None
        message.media_encryption_key = None
        
        await self.db.commit()
        logger.info(f"Deleted media for message {message.id}")
    
    async def get_conversation_media(
        self,
        conversation_id: int,
        user: User,
        media_type: Optional[MessageType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all media from a conversation."""
        # Build query
        stmt = select(Message).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.media_url.isnot(None),
                Message.is_deleted == False
            )
        )
        
        if media_type:
            stmt = stmt.where(Message.type == media_type)
        
        stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        media_items = []
        for message in messages:
            if await self._can_access_media(message, user):
                media_items.append({
                    'message_id': message.id,
                    'type': message.type.value,
                    'media_url': await self.get_media_url(message, user),
                    'thumbnail_url': message.thumbnail_url,
                    'sender_id': message.sender_id,
                    'sender_type': message.sender_type,
                    'created_at': message.created_at.isoformat(),
                    'is_paid': message.is_paid if message.type == MessageType.PPV else None
                })
        
        return media_items