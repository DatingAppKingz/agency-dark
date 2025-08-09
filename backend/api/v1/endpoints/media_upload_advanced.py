"""
Media Upload API endpoints
"""
from typing import Optional, List
from uuid import UUID, uuid4
import os
import mimetypes
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from core.database import get_db, Base
from core.security_v2 import get_current_user
from core.domain.models import User
from core.config import settings

router = APIRouter(prefix="/media", tags=["media"])


class MediaUpload(Base):
    """Media upload tracking"""
    __tablename__ = "media_uploads"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(PGUUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    
    # URLs for access
    public_url = Column(String)
    thumbnail_url = Column(String)
    
    # Metadata
    extra_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Status
    status = Column(String, default="pending")  # pending, processing, ready, failed
    error_message = Column(String)


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    media_type: str = Form(...),
    platform: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload media file for messages or content"""
    
    # Validate file size
    max_size = settings.MAX_UPLOAD_SIZE  # Default 50MB
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size / 1024 / 1024}MB"
        )
    
    # Validate content type
    allowed_types = {
        "image": ["image/jpeg", "image/png", "image/gif", "image/webp"],
        "video": ["video/mp4", "video/quicktime", "video/x-msvideo"],
        "audio": ["audio/mpeg", "audio/wav", "audio/ogg"]
    }
    
    content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
    
    if media_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid media type: {media_type}")
    
    if content_type not in allowed_types.get(media_type, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type {content_type} for media type {media_type}"
        )
    
    # Generate storage path
    upload_id = str(uuid4())
    extension = os.path.splitext(file.filename)[1]
    storage_filename = f"{upload_id}{extension}"
    storage_path = f"uploads/{current_user.agency_id}/{media_type}/{storage_filename}"
    
    # Create upload record
    upload = MediaUpload(
        id=UUID(upload_id),
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        filename=file.filename,
        content_type=content_type,
        file_size=str(file_size),
        storage_path=storage_path,
        status="processing",
        metadata={
            "media_type": media_type,
            "platform": platform
        }
    )
    
    db.add(upload)
    await db.commit()
    
    try:
        # Save file to storage (local or S3)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(contents)
        
        # Update status
        upload.status = "ready"
        upload.public_url = f"/media/{upload_id}"
        
        # Generate thumbnail for images/videos
        if media_type in ["image", "video"]:
            # TODO: Generate thumbnail
            upload.thumbnail_url = f"/media/{upload_id}/thumbnail"
        
        await db.commit()
        
        # Return upload info
        return {
            "upload_id": str(upload.id),
            "filename": upload.filename,
            "content_type": upload.content_type,
            "file_size": upload.file_size,
            "public_url": upload.public_url,
            "thumbnail_url": upload.thumbnail_url,
            "status": upload.status
        }
        
    except Exception as e:
        upload.status = "failed"
        upload.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{upload_id}")
async def get_media(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get media upload details"""
    upload = await db.get(MediaUpload, upload_id)
    
    if not upload:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Check permissions
    if upload.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "upload_id": str(upload.id),
        "filename": upload.filename,
        "content_type": upload.content_type,
        "file_size": upload.file_size,
        "public_url": upload.public_url,
        "thumbnail_url": upload.thumbnail_url,
        "status": upload.status,
        "created_at": upload.created_at
    }


@router.delete("/{upload_id}")
async def delete_media(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete media upload"""
    upload = await db.get(MediaUpload, upload_id)
    
    if not upload:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Check permissions
    if upload.user_id != current_user.id and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete file from storage
    try:
        if os.path.exists(upload.storage_path):
            os.remove(upload.storage_path)
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
    
    # Delete record
    await db.delete(upload)
    await db.commit()
    
    return {"message": "Media deleted successfully"}


@router.post("/bulk-upload")
async def bulk_upload_media(
    files: List[UploadFile] = File(...),
    media_type: str = Form(...),
    platform: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload multiple media files"""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")
    
    results = []
    for file in files:
        try:
            # Process each file
            result = await upload_media(
                file=file,
                media_type=media_type,
                platform=platform,
                current_user=current_user,
                db=db
            )
            results.append(result)
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
    
    return {"uploads": results}