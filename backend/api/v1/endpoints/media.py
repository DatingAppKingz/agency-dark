"""Media management endpoints with advanced features."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import json

from core.database import get_db
from core.dependencies import get_current_active_user
from core.rbac import check_permission
from services.media_upload.file_upload_service import FileUploadService
from models.media import Media, MediaFolder, MediaShare, MediaType, MediaStatus, MediaVisibility
from models.user import User
from schemas.media import (
    MediaCreate, MediaUpdate, MediaResponse, MediaDetailResponse,
    MediaFolderCreate, MediaFolderUpdate, MediaFolderResponse,
    MediaShareCreate, MediaShareResponse,
    MediaSearchParams, MediaBulkOperation
)
from core.logger import get_logger
from core.simple_cache import cache_result, invalidate_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

# Initialize file upload service
file_upload_service = FileUploadService()


@router.post("/upload", response_model=MediaDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[UUID] = Form(None),
    visibility: MediaVisibility = Form(MediaVisibility.PRIVATE),
    tags: Optional[str] = Form(None),  # JSON string
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Upload a new media file.
    
    Features:
    - Virus scanning
    - Automatic type detection
    - Image/video processing
    - S3 upload with CDN
    - Metadata extraction
    """
    # Check permission
    check_permission(current_user, "media", "create")
    
    # Check storage quota
    quota_check = await _check_storage_quota(db, current_user.agency_id)
    if not quota_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=f"Storage quota exceeded. Used: {quota_check['used_gb']}GB of {quota_check['quota_gb']}GB"
        )
    
    # Parse tags if provided
    tag_list = json.loads(tags) if tags else None
    
    # Determine model_id based on user role
    model_id = None
    if current_user.role == "model" and hasattr(current_user, "model_id"):
        model_id = current_user.model_id
    
    try:
        # Upload file
        media = await file_upload_service.upload_file(
            file=file,
            user=current_user,
            agency_id=str(current_user.agency_id),
            model_id=str(model_id) if model_id else None,
            folder_id=str(folder_id) if folder_id else None,
            visibility=visibility,
            tags=tag_list,
            title=title,
            description=description
        )
        
        # Save to database
        db.add(media)
        await db.commit()
        await db.refresh(media)
        
        # Invalidate cache
        await invalidate_cache(f"media:agency:{current_user.agency_id}:*")
        
        # Log analytics in background
        background_tasks.add_task(
            _track_upload_analytics,
            media.id,
            current_user.id,
            current_user.agency_id
        )
        
        return MediaDetailResponse.from_orm(media)
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/upload/batch", response_model=List[MediaDetailResponse])
async def batch_upload(
    files: List[UploadFile] = File(...),
    folder_id: Optional[UUID] = Form(None),
    visibility: MediaVisibility = Form(MediaVisibility.PRIVATE),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Upload multiple files at once.
    
    - Maximum 10 files per batch
    - Returns list of uploaded media
    - Failed uploads included with error details
    """
    # Check permission
    check_permission(current_user, "media", "create")
    
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed per batch"
        )
    
    results = []
    
    for file in files:
        try:
            media = await file_upload_service.upload_file(
                file=file,
                user=current_user,
                agency_id=str(current_user.agency_id),
                folder_id=str(folder_id) if folder_id else None,
                visibility=visibility
            )
            
            db.add(media)
            results.append(media)
            
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            # Create failed media entry
            failed_media = Media(
                filename=file.filename,
                original_filename=file.filename,
                file_path="",
                file_size=0,
                mime_type="",
                media_type=MediaType.OTHER,
                status=MediaStatus.FAILED,
                processing_error=str(e),
                agency_id=current_user.agency_id,
                uploaded_by=current_user.id
            )
            results.append(failed_media)
    
    await db.commit()
    
    # Refresh all media objects
    for media in results:
        if media.status != MediaStatus.FAILED:
            await db.refresh(media)
    
    return [MediaDetailResponse.from_orm(m) for m in results]


@router.get("/", response_model=Dict[str, Any])
@cache_result(key_prefix="media:list", ttl=300)
async def list_media(
    media_type: Optional[MediaType] = None,
    folder_id: Optional[UUID] = None,
    visibility: Optional[MediaVisibility] = None,
    status: Optional[MediaStatus] = None,
    tags: Optional[List[str]] = Query(None),
    search: Optional[str] = None,
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|file_size|title)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List media files with advanced filtering.
    
    Features:
    - Filter by type, folder, visibility, status
    - Tag-based filtering
    - Full-text search
    - Flexible sorting
    - Pagination
    """
    # Check permission
    check_permission(current_user, "media", "read")
    
    # Build query
    query = select(Media).where(
        and_(
            Media.agency_id == current_user.agency_id,
            Media.status != MediaStatus.DELETED
        )
    )
    
    # Apply filters
    if media_type:
        query = query.where(Media.media_type == media_type)
    
    if folder_id:
        query = query.where(Media.folder_id == folder_id)
    
    if visibility:
        query = query.where(Media.visibility == visibility)
    
    if status:
        query = query.where(Media.status == status)
    
    if tags:
        # Filter by tags (PostgreSQL array contains)
        for tag in tags:
            query = query.where(Media.tags.contains([tag]))
    
    if search:
        # Full-text search on title, description, filename
        search_filter = or_(
            Media.title.ilike(f"%{search}%"),
            Media.description.ilike(f"%{search}%"),
            Media.original_filename.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    # Apply sorting
    order_column = getattr(Media, sort_by)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    # Include relationships
    query = query.options(
        selectinload(Media.folder),
        selectinload(Media.uploader)
    )
    
    # Execute query
    result = await db.execute(query)
    media_items = result.scalars().all()
    
    return {
        "items": [MediaResponse.from_orm(m) for m in media_items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


@router.get("/{media_id}", response_model=MediaDetailResponse)
@cache_result(key_prefix="media:get", ttl=3600)
async def get_media(
    media_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a media file."""
    # Get media
    media = await db.get(Media, media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    # Check access
    if not await _check_media_access(media, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update view count
    media.view_count += 1
    media.last_accessed_at = datetime.utcnow()
    await db.commit()
    
    return MediaDetailResponse.from_orm(media)


@router.put("/{media_id}", response_model=MediaDetailResponse)
async def update_media(
    media_id: UUID,
    update_data: MediaUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update media metadata."""
    # Check permission
    check_permission(current_user, "media", "update")
    
    # Get media
    media = await db.get(Media, media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    # Check ownership
    if media.uploaded_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update media you don't own"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(media, field, value)
    
    media.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(media)
    
    # Invalidate cache
    await invalidate_cache(f"media:{media_id}")
    await invalidate_cache(f"media:agency:{media.agency_id}:*")
    
    return MediaDetailResponse.from_orm(media)


@router.delete("/{media_id}")
async def delete_media(
    media_id: UUID,
    permanent: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Delete a media file.
    
    - Soft delete by default
    - Permanent delete removes from storage
    """
    # Check permission
    check_permission(current_user, "media", "delete")
    
    # Get media
    media = await db.get(Media, media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    # Check ownership
    if media.uploaded_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete media you don't own"
        )
    
    if permanent:
        # Delete from storage
        background_tasks.add_task(
            file_upload_service.delete_file,
            media
        )
        
        # Delete from database
        await db.delete(media)
    else:
        # Soft delete
        media.status = MediaStatus.DELETED
        media.deleted_at = datetime.utcnow()
    
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache(f"media:{media_id}")
    await invalidate_cache(f"media:agency:{media.agency_id}:*")
    
    return {"message": "Media deleted successfully"}


@router.post("/bulk", response_model=Dict[str, Any])
async def bulk_operation(
    operation: MediaBulkOperation,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Perform bulk operations on media files.
    
    Operations:
    - delete: Delete multiple files
    - move: Move to different folder
    - update_visibility: Change visibility
    - add_tags: Add tags to files
    - remove_tags: Remove tags from files
    """
    # Check permission
    check_permission(current_user, "media", operation.action)
    
    # Get media items
    query = select(Media).where(
        and_(
            Media.id.in_(operation.media_ids),
            Media.agency_id == current_user.agency_id
        )
    )
    
    result = await db.execute(query)
    media_items = result.scalars().all()
    
    if len(media_items) != len(operation.media_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some media files not found"
        )
    
    success_count = 0
    errors = []
    
    for media in media_items:
        try:
            if operation.action == "delete":
                if operation.data.get("permanent"):
                    background_tasks.add_task(
                        file_upload_service.delete_file,
                        media
                    )
                    await db.delete(media)
                else:
                    media.status = MediaStatus.DELETED
                    media.deleted_at = datetime.utcnow()
            
            elif operation.action == "move":
                folder_id = operation.data.get("folder_id")
                media.folder_id = UUID(folder_id) if folder_id else None
            
            elif operation.action == "update_visibility":
                visibility = MediaVisibility(operation.data["visibility"])
                media.visibility = visibility
            
            elif operation.action == "add_tags":
                tags = operation.data.get("tags", [])
                media.tags = list(set(media.tags + tags))
            
            elif operation.action == "remove_tags":
                tags = operation.data.get("tags", [])
                media.tags = [t for t in media.tags if t not in tags]
            
            success_count += 1
            
        except Exception as e:
            errors.append({
                "media_id": str(media.id),
                "error": str(e)
            })
    
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache(f"media:agency:{current_user.agency_id}:*")
    
    return {
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors
    }


# Folder Management Endpoints

@router.post("/folders", response_model=MediaFolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder_data: MediaFolderCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new media folder."""
    # Check permission
    check_permission(current_user, "media", "create")
    
    # Check parent folder if specified
    if folder_data.parent_id:
        parent = await db.get(MediaFolder, folder_data.parent_id)
        if not parent or parent.agency_id != current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found"
            )
    
    # Create folder
    folder = MediaFolder(
        **folder_data.dict(),
        agency_id=current_user.agency_id,
        created_by=current_user.id
    )
    
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    
    return MediaFolderResponse.from_orm(folder)


@router.get("/folders", response_model=List[MediaFolderResponse])
@cache_result(key_prefix="media:stats", ttl=600)
async def list_folders(
    parent_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List media folders."""
    # Check permission
    check_permission(current_user, "media", "read")
    
    # Build query
    query = select(MediaFolder).where(
        MediaFolder.agency_id == current_user.agency_id
    )
    
    if parent_id is not None:
        query = query.where(MediaFolder.parent_id == parent_id)
    else:
        query = query.where(MediaFolder.parent_id.is_(None))
    
    query = query.order_by(MediaFolder.name)
    
    # Include media count
    query = query.options(selectinload(MediaFolder.media_items))
    
    result = await db.execute(query)
    folders = result.scalars().all()
    
    return [MediaFolderResponse.from_orm(f) for f in folders]


@router.put("/folders/{folder_id}", response_model=MediaFolderResponse)
async def update_folder(
    folder_id: UUID,
    update_data: MediaFolderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a media folder."""
    # Check permission
    check_permission(current_user, "media", "update")
    
    # Get folder
    folder = await db.get(MediaFolder, folder_id)
    
    if not folder or folder.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(folder, field, value)
    
    folder.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(folder)
    
    # Invalidate cache
    await invalidate_cache(f"media:folders:agency:{current_user.agency_id}")
    
    return MediaFolderResponse.from_orm(folder)


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: UUID,
    move_contents_to: Optional[UUID] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a media folder.
    
    - Can move contents to another folder
    - Or delete all contents
    """
    # Check permission
    check_permission(current_user, "media", "delete")
    
    # Get folder
    folder = await db.get(MediaFolder, folder_id)
    
    if not folder or folder.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Check if folder has contents
    media_count = await db.scalar(
        select(func.count()).select_from(Media).where(Media.folder_id == folder_id)
    )
    
    if media_count > 0:
        if move_contents_to:
            # Move contents to another folder
            await db.execute(
                update(Media)
                .where(Media.folder_id == folder_id)
                .values(folder_id=move_contents_to)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder contains media files. Specify move_contents_to or delete contents first."
            )
    
    # Delete folder
    await db.delete(folder)
    await db.commit()
    
    # Invalidate cache
    await invalidate_cache(f"media:folders:agency:{current_user.agency_id}")
    
    return {"message": "Folder deleted successfully"}


# Media Sharing Endpoints

@router.post("/share", response_model=MediaShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share_link(
    share_data: MediaShareCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a shareable link for media."""
    # Check permission
    check_permission(current_user, "media", "share")
    
    # Get media
    media = await db.get(Media, share_data.media_id)
    
    if not media or media.agency_id != current_user.agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    # Generate unique token
    import secrets
    share_token = secrets.token_urlsafe(32)
    
    # Create share
    share = MediaShare(
        **share_data.dict(),
        share_token=share_token,
        created_by=current_user.id
    )
    
    db.add(share)
    await db.commit()
    await db.refresh(share)
    
    # Include full URL
    share_url = f"{settings.FRONTEND_URL}/shared/{share.share_token}"
    
    return MediaShareResponse.from_orm(share, share_url=share_url)


@router.get("/share/{share_token}")
async def access_shared_media(
    share_token: str,
    password: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Access media via share link."""
    # Get share
    query = select(MediaShare).where(
        MediaShare.share_token == share_token
    ).options(selectinload(MediaShare.media))
    
    result = await db.execute(query)
    share = result.scalar_one_or_none()
    
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )
    
    # Check if expired
    if share.is_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Share link has expired"
        )
    
    # Check password
    if share.password_protected:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password required"
            )
        # Verify password (implement password verification)
        # if not verify_password(password, share.password_hash):
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Invalid password"
        #     )
    
    # Update view count
    share.current_views += 1
    share.last_accessed_at = datetime.utcnow()
    share.media.view_count += 1
    
    await db.commit()
    
    return {
        "media": MediaResponse.from_orm(share.media),
        "allow_download": share.allow_download,
        "allow_embed": share.allow_embed
    }


@router.get("/download/{media_id}")
async def download_media(
    media_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a media file.
    
    Returns a streaming response for file download.
    """
    # Get media
    media = await db.get(Media, media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    # Check access
    if not await _check_media_access(media, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update download count
    media.download_count += 1
    await db.commit()
    
    # For S3, return a presigned URL
    if media.cdn_url and media.cdn_url.startswith("https://"):
        # Generate presigned URL for S3
        # This is a placeholder - implement actual S3 presigned URL generation
        return {
            "download_url": media.cdn_url,
            "filename": media.original_filename
        }
    
    # For local files, stream the file
    import aiofiles
    from os.path import exists
    
    file_path = media.file_path
    if not exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    async def file_streamer():
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                yield chunk
    
    return StreamingResponse(
        file_streamer(),
        media_type=media.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{media.original_filename}"'
        }
    )


# Helper functions

async def _check_media_access(media: Media, user: User) -> bool:
    """Check if user has access to media."""
    # Owner always has access
    if media.uploaded_by == user.id:
        return True
    
    # Check visibility
    if media.visibility == MediaVisibility.PUBLIC:
        return True
    
    if media.visibility == MediaVisibility.AGENCY:
        return media.agency_id == user.agency_id
    
    if media.visibility == MediaVisibility.MODEL:
        return media.model_id == getattr(user, "model_id", None)
    
    # Private - only owner
    return False


async def _check_storage_quota(db: AsyncSession, agency_id: UUID) -> Dict[str, Any]:
    """Check agency storage quota."""
    # Get total storage used
    result = await db.execute(
        select(func.sum(Media.file_size))
        .where(
            and_(
                Media.agency_id == agency_id,
                Media.status != MediaStatus.DELETED
            )
        )
    )
    
    total_bytes = result.scalar() or 0
    total_gb = total_bytes / (1024 ** 3)
    
    # Get agency quota (placeholder - implement actual quota management)
    quota_gb = 100  # 100GB default quota
    
    return {
        "allowed": total_gb < quota_gb,
        "used_gb": round(total_gb, 2),
        "quota_gb": quota_gb,
        "remaining_gb": round(quota_gb - total_gb, 2)
    }


async def _track_upload_analytics(media_id: UUID, user_id: UUID, agency_id: UUID):
    """Track media upload analytics."""
    # Placeholder for analytics tracking
    logger.info(f"Media uploaded: {media_id} by user {user_id} in agency {agency_id}")