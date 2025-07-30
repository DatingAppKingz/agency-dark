"""Media upload endpoints for file management."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.media_service import MediaService
from core.exceptions import ValidationError, NotFoundError, PermissionError

router = APIRouter()


# Request/Response schemas
class UploadUrlRequest(BaseModel):
    """Request for generating upload URL."""
    file_type: str = Field(..., description="File extension (jpg, png, mp4, etc.)")
    file_size: int = Field(..., ge=1, description="File size in bytes")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UploadUrlResponse(BaseModel):
    """Response with upload URL."""
    upload_id: str
    upload_url: str
    expires_at: str
    file_path: str
    max_size: int
    allowed_types: List[str]


class ConfirmUploadRequest(BaseModel):
    """Request to confirm upload completion."""
    upload_id: str
    file_hash: Optional[str] = None


class MediaResponse(BaseModel):
    """Media file response."""
    id: int
    type: str
    url: str
    thumbnail_url: Optional[str]
    file_size: int
    mime_type: str
    is_public: bool
    view_count: int
    created_at: str


class MediaListResponse(BaseModel):
    """Media list response."""
    items: List[MediaResponse]
    total: int
    limit: int
    offset: int


class StorageUsageResponse(BaseModel):
    """Storage usage response."""
    agency_id: int
    usage_by_type: Dict[str, Dict[str, int]]
    total_size: int
    total_count: int
    storage_quota: int
    usage_percentage: float
    remaining_storage: int


@router.post("/upload-url", response_model=UploadUrlResponse)
async def generate_upload_url(
    request: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UploadUrlResponse:
    """
    Generate a presigned URL for file upload.
    
    - Validates file type and size
    - Returns temporary upload URL
    - URL expires after 1 hour
    """
    try:
        result = await MediaService.generate_upload_url(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            file_type=request.file_type,
            file_size=request.file_size,
            metadata=request.metadata
        )
        
        return UploadUrlResponse(**result)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/confirm-upload")
async def confirm_upload(
    request: ConfirmUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Confirm that a file was successfully uploaded.
    
    - Creates content record in database
    - Returns content details
    """
    try:
        result = await MediaService.confirm_upload(
            db=db,
            upload_id=request.upload_id,
            file_hash=request.file_hash
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/download-url/{content_id}")
async def generate_download_url(
    content_id: int,
    expires_in: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate a presigned URL for file download.
    
    - Checks user permissions
    - Returns temporary download URL
    - Default expiration: 24 hours
    """
    try:
        result = await MediaService.generate_download_url(
            db=db,
            content_id=content_id,
            user_id=current_user.id,
            expires_in=expires_in
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/list", response_model=MediaListResponse)
async def list_media(
    media_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MediaListResponse:
    """
    List user's media files.
    
    - Filter by type (image, video, document)
    - Paginated results
    - Sorted by creation date (newest first)
    """
    result = await MediaService.list_user_media(
        db=db,
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        media_type=media_type,
        limit=limit,
        offset=offset
    )
    
    return MediaListResponse(**result)


@router.delete("/{content_id}")
async def delete_media(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a media file.
    
    - Only owner can delete
    - Removes from storage and database
    """
    try:
        await MediaService.delete_media(
            db=db,
            content_id=content_id,
            user_id=current_user.id
        )
        return {"message": "Media deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/bulk-delete")
async def bulk_delete_media(
    content_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete multiple media files.
    
    - Only owner can delete
    - Atomic operation
    """
    try:
        result = await MediaService.bulk_delete_media(
            db=db,
            content_ids=content_ids,
            user_id=current_user.id
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/storage-usage", response_model=StorageUsageResponse)
async def get_storage_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> StorageUsageResponse:
    """
    Get storage usage statistics.
    
    - Shows usage by file type
    - Compares against agency quota
    - Useful for monitoring limits
    """
    try:
        result = await MediaService.get_storage_usage(
            db=db,
            agency_id=current_user.agency_id
        )
        return StorageUsageResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Direct upload endpoint (for small files)
@router.post("/direct-upload")
async def direct_upload(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Direct file upload for small files.
    
    - Maximum 10MB
    - Synchronous processing
    - Returns content details immediately
    """
    # Check file size
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > MediaService.MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="File too large for direct upload")
    
    # Get file type
    file_type = file.filename.split('.')[-1].lower()
    
    try:
        # Generate upload URL
        upload_result = await MediaService.generate_upload_url(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            file_type=file_type,
            file_size=file_size,
            metadata=metadata
        )
        
        # In production, save file to storage here
        # For now, just confirm upload
        
        confirm_result = await MediaService.confirm_upload(
            db=db,
            upload_id=upload_result["upload_id"]
        )
        
        return confirm_result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))