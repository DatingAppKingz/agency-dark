"""Media upload service for handling file uploads and storage."""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
import secrets
import mimetypes
import hashlib
from pathlib import Path

from models.user import User
from models.agency import Agency
from models.content import Content
from core.exceptions import ValidationError, NotFoundError, PermissionError
from core.config import settings
from core.redis import redis_manager


class MediaService:
    """Service for handling media uploads and storage."""
    
    # Allowed file types
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp'
    }
    
    ALLOWED_VIDEO_TYPES = {
        'video/mp4': '.mp4',
        'video/quicktime': '.mov',
        'video/x-msvideo': '.avi',
        'video/webm': '.webm'
    }
    
    ALLOWED_DOCUMENT_TYPES = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
    }
    
    # Size limits (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB
    
    # Upload URL expiration
    UPLOAD_URL_EXPIRATION = 3600  # 1 hour
    DOWNLOAD_URL_EXPIRATION = 86400  # 24 hours
    
    @staticmethod
    async def generate_upload_url(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        file_type: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a presigned URL for file upload."""
        # Validate file type
        mime_type = mimetypes.guess_type(f"file.{file_type}")[0]
        if not mime_type:
            raise ValidationError(f"Unknown file type: {file_type}")
        
        # Determine category and validate
        category = None
        max_size = 0
        
        if mime_type in MediaService.ALLOWED_IMAGE_TYPES:
            category = "image"
            max_size = MediaService.MAX_IMAGE_SIZE
        elif mime_type in MediaService.ALLOWED_VIDEO_TYPES:
            category = "video"
            max_size = MediaService.MAX_VIDEO_SIZE
        elif mime_type in MediaService.ALLOWED_DOCUMENT_TYPES:
            category = "document"
            max_size = MediaService.MAX_DOCUMENT_SIZE
        else:
            raise ValidationError(f"File type not allowed: {mime_type}")
        
        # Validate file size
        if file_size > max_size:
            raise ValidationError(f"File too large. Maximum size: {max_size} bytes")
        
        # Generate unique upload ID
        upload_id = secrets.token_urlsafe(32)
        
        # Generate file path
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        file_name = f"{upload_id}.{file_type}"
        file_path = f"{agency_id}/{category}/{timestamp}/{file_name}"
        
        # Store upload metadata in Redis
        upload_data = {
            "upload_id": upload_id,
            "user_id": user_id,
            "agency_id": agency_id,
            "file_type": file_type,
            "mime_type": mime_type,
            "file_size": file_size,
            "category": category,
            "file_path": file_path,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        await redis_manager.set(
            f"upload:{upload_id}",
            upload_data,
            expire=MediaService.UPLOAD_URL_EXPIRATION
        )
        
        # Generate presigned URL (in production, this would use S3 or similar)
        upload_url = f"{settings.BASE_URL}/api/v1/media/upload/{upload_id}"
        
        return {
            "upload_id": upload_id,
            "upload_url": upload_url,
            "expires_at": (datetime.utcnow() + timedelta(seconds=MediaService.UPLOAD_URL_EXPIRATION)).isoformat(),
            "file_path": file_path,
            "max_size": max_size,
            "allowed_types": [mime_type]
        }
    
    @staticmethod
    async def confirm_upload(
        db: AsyncSession,
        upload_id: str,
        file_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """Confirm that a file was successfully uploaded."""
        # Get upload data from Redis
        upload_data = await redis_manager.get(f"upload:{upload_id}")
        if not upload_data:
            raise NotFoundError("Upload not found or expired")
        
        # Update status
        upload_data["status"] = "completed"
        upload_data["completed_at"] = datetime.utcnow().isoformat()
        if file_hash:
            upload_data["file_hash"] = file_hash
        
        # Create content record
        content = Content(
            user_id=upload_data["user_id"],
            agency_id=upload_data["agency_id"],
            type=upload_data["category"],
            url=upload_data["file_path"],
            thumbnail_url=None,  # Would be generated for images/videos
            file_size=upload_data["file_size"],
            mime_type=upload_data["mime_type"],
            metadata=upload_data.get("metadata", {}),
            is_public=False,
            view_count=0
        )
        
        db.add(content)
        await db.commit()
        await db.refresh(content)
        
        # Clean up Redis
        await redis_manager.delete(f"upload:{upload_id}")
        
        return {
            "content_id": content.id,
            "url": content.url,
            "type": content.type,
            "created_at": content.created_at.isoformat()
        }
    
    @staticmethod
    async def generate_download_url(
        db: AsyncSession,
        content_id: int,
        user_id: int,
        expires_in: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate a presigned URL for file download."""
        # Get content
        content = await db.get(Content, content_id)
        if not content:
            raise NotFoundError("Content not found")
        
        # Check permissions
        if content.user_id != user_id and not content.is_public:
            # Check if user has access through agency
            user = await db.get(User, user_id)
            if not user or user.agency_id != content.agency_id:
                raise PermissionError("Access denied")
        
        # Generate download token
        download_token = secrets.token_urlsafe(32)
        expiration = expires_in or MediaService.DOWNLOAD_URL_EXPIRATION
        
        # Store download metadata
        download_data = {
            "content_id": content_id,
            "user_id": user_id,
            "file_path": content.url,
            "accessed_at": datetime.utcnow().isoformat()
        }
        
        await redis_manager.set(
            f"download:{download_token}",
            download_data,
            expire=expiration
        )
        
        # Generate URL
        download_url = f"{settings.BASE_URL}/api/v1/media/download/{download_token}"
        
        return {
            "download_url": download_url,
            "expires_at": (datetime.utcnow() + timedelta(seconds=expiration)).isoformat(),
            "content_type": content.mime_type,
            "file_size": content.file_size
        }
    
    @staticmethod
    async def list_user_media(
        db: AsyncSession,
        user_id: int,
        agency_id: int,
        media_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List media files for a user."""
        # Build query
        query = select(Content).where(
            and_(
                Content.user_id == user_id,
                Content.agency_id == agency_id
            )
        )
        
        if media_type:
            query = query.where(Content.type == media_type)
        
        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get items
        query = query.order_by(Content.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return {
            "items": [
                {
                    "id": item.id,
                    "type": item.type,
                    "url": item.url,
                    "thumbnail_url": item.thumbnail_url,
                    "file_size": item.file_size,
                    "mime_type": item.mime_type,
                    "is_public": item.is_public,
                    "view_count": item.view_count,
                    "created_at": item.created_at.isoformat()
                }
                for item in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    @staticmethod
    async def delete_media(
        db: AsyncSession,
        content_id: int,
        user_id: int
    ) -> bool:
        """Delete a media file."""
        # Get content
        content = await db.get(Content, content_id)
        if not content:
            raise NotFoundError("Content not found")
        
        # Check ownership
        if content.user_id != user_id:
            raise PermissionError("You can only delete your own content")
        
        # Delete from database
        await db.delete(content)
        await db.commit()
        
        # In production, also delete from storage (S3, etc.)
        
        return True
    
    @staticmethod
    async def get_storage_usage(
        db: AsyncSession,
        agency_id: int
    ) -> Dict[str, Any]:
        """Get storage usage statistics for an agency."""
        # Get agency
        agency = await db.get(Agency, agency_id)
        if not agency:
            raise NotFoundError("Agency not found")
        
        # Calculate usage by type
        usage_query = select(
            Content.type,
            func.count(Content.id).label('count'),
            func.sum(Content.file_size).label('total_size')
        ).where(
            Content.agency_id == agency_id
        ).group_by(Content.type)
        
        result = await db.execute(usage_query)
        usage_by_type = {
            row.type: {
                "count": row.count,
                "size": row.total_size or 0
            }
            for row in result
        }
        
        # Calculate total usage
        total_size = sum(data["size"] for data in usage_by_type.values())
        total_count = sum(data["count"] for data in usage_by_type.values())
        
        # Get quota
        storage_quota = agency.storage_quota_gb * 1024 * 1024 * 1024  # Convert GB to bytes
        
        return {
            "agency_id": agency_id,
            "usage_by_type": usage_by_type,
            "total_size": total_size,
            "total_count": total_count,
            "storage_quota": storage_quota,
            "usage_percentage": (total_size / storage_quota * 100) if storage_quota > 0 else 0,
            "remaining_storage": max(0, storage_quota - total_size)
        }
    
    @staticmethod
    async def bulk_delete_media(
        db: AsyncSession,
        content_ids: List[int],
        user_id: int
    ) -> Dict[str, Any]:
        """Bulk delete media files."""
        # Get contents
        query = select(Content).where(
            and_(
                Content.id.in_(content_ids),
                Content.user_id == user_id
            )
        )
        
        result = await db.execute(query)
        contents = result.scalars().all()
        
        if len(contents) != len(content_ids):
            raise PermissionError("Some content not found or not owned by user")
        
        # Delete all
        for content in contents:
            await db.delete(content)
        
        await db.commit()
        
        return {
            "deleted_count": len(contents),
            "deleted_ids": [c.id for c in contents]
        }