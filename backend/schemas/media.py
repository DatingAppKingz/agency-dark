"""Media schemas for request/response validation."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator, HttpUrl

from models.media import MediaType, MediaStatus, MediaVisibility


# Media Schemas

class MediaBase(BaseModel):
    """Base media schema."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    alt_text: Optional[str] = Field(None, max_length=500)
    tags: List[str] = Field(default_factory=list)
    visibility: MediaVisibility = MediaVisibility.PRIVATE
    folder_id: Optional[UUID] = None


class MediaCreate(MediaBase):
    """Schema for media creation (used with metadata, not direct upload)."""
    pass


class MediaUpdate(BaseModel):
    """Schema for media update."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    alt_text: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    visibility: Optional[MediaVisibility] = None
    folder_id: Optional[UUID] = None
    copyright_info: Optional[str] = Field(None, max_length=500)


class MediaResponse(BaseModel):
    """Basic media response."""
    id: UUID
    filename: str
    original_filename: str
    media_type: MediaType
    mime_type: str
    file_size: int
    status: MediaStatus
    cdn_url: Optional[HttpUrl]
    thumbnail_url: Optional[HttpUrl]
    visibility: MediaVisibility
    tags: List[str]
    title: Optional[str]
    created_at: datetime
    view_count: int
    download_count: int
    
    class Config:
        orm_mode = True
    
    @validator('cdn_url', 'thumbnail_url', pre=True)
    def convert_urls(cls, v):
        """Convert string URLs to HttpUrl."""
        return v if v else None
    
    @property
    def size_mb(self) -> float:
        """Get file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)


class MediaDetailResponse(MediaResponse):
    """Detailed media response with additional fields."""
    file_path: str
    file_hash: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    processing_error: Optional[str]
    optimized_versions: Optional[Dict[str, str]]
    description: Optional[str]
    alt_text: Optional[str]
    copyright_info: Optional[str]
    exif_data: Optional[Dict[str, Any]]
    custom_metadata: Optional[Dict[str, Any]]
    is_nsfw: bool
    moderation_status: Optional[str]
    moderation_labels: Optional[List[str]]
    agency_id: UUID
    model_id: Optional[UUID]
    uploaded_by: UUID
    folder: Optional['MediaFolderResponse']
    uploader: Optional[Dict[str, Any]]  # User info
    updated_at: datetime
    last_accessed_at: Optional[datetime]
    
    class Config:
        orm_mode = True


# Folder Schemas

class MediaFolderBase(BaseModel):
    """Base folder schema."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_public: bool = False
    color: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)


class MediaFolderCreate(MediaFolderBase):
    """Schema for folder creation."""
    model_id: Optional[UUID] = None


class MediaFolderUpdate(BaseModel):
    """Schema for folder update."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_public: Optional[bool] = None
    color: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)


class MediaFolderResponse(BaseModel):
    """Folder response schema."""
    id: UUID
    name: str
    description: Optional[str]
    parent_id: Optional[UUID]
    is_public: bool
    color: Optional[str]
    icon: Optional[str]
    agency_id: UUID
    model_id: Optional[UUID]
    created_by: UUID
    created_at: datetime
    media_count: int = 0
    
    class Config:
        orm_mode = True
    
    @validator('media_count', pre=True, always=True)
    def count_media(cls, v, values, **kwargs):
        """Count media items if relationship is loaded."""
        if 'media_items' in values:
            return len(values['media_items'])
        return v or 0


# Share Schemas

class MediaShareCreate(BaseModel):
    """Schema for creating share link."""
    media_id: UUID
    expires_at: Optional[datetime] = None
    max_views: Optional[int] = Field(None, ge=1)
    password_protected: bool = False
    password: Optional[str] = None  # Raw password, will be hashed
    allow_download: bool = False
    allow_embed: bool = True
    
    @validator('password')
    def validate_password(cls, v, values):
        """Ensure password is provided if password_protected is True."""
        if values.get('password_protected') and not v:
            raise ValueError("Password required when password_protected is True")
        return v


class MediaShareResponse(BaseModel):
    """Share link response schema."""
    id: UUID
    media_id: UUID
    share_token: str
    share_url: Optional[str] = None  # Full URL constructed by endpoint
    expires_at: Optional[datetime]
    max_views: Optional[int]
    current_views: int
    password_protected: bool
    allow_download: bool
    allow_embed: bool
    created_by: UUID
    created_at: datetime
    last_accessed_at: Optional[datetime]
    is_expired: bool = False
    
    class Config:
        orm_mode = True
    
    @validator('is_expired', pre=True, always=True)
    def check_expired(cls, v, values):
        """Check if share link is expired."""
        if values.get('expires_at') and datetime.utcnow() > values['expires_at']:
            return True
        if values.get('max_views') and values.get('current_views', 0) >= values['max_views']:
            return True
        return False


# Search and Filter Schemas

class MediaSearchParams(BaseModel):
    """Parameters for media search."""
    query: Optional[str] = Field(None, description="Search query")
    media_types: Optional[List[MediaType]] = None
    folder_ids: Optional[List[UUID]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[List[MediaVisibility]] = None
    status: Optional[List[MediaStatus]] = None
    uploaded_by: Optional[List[UUID]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_size: Optional[int] = Field(None, ge=0)
    max_size: Optional[int] = Field(None, ge=0)
    is_nsfw: Optional[bool] = None


# Bulk Operation Schemas

class MediaBulkOperation(BaseModel):
    """Schema for bulk operations."""
    media_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., regex="^(delete|move|update_visibility|add_tags|remove_tags)$")
    data: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('data')
    def validate_data(cls, v, values):
        """Validate data based on action."""
        action = values.get('action')
        
        if action == 'move':
            if 'folder_id' not in v:
                raise ValueError("folder_id required for move action")
        
        elif action == 'update_visibility':
            if 'visibility' not in v:
                raise ValueError("visibility required for update_visibility action")
            try:
                MediaVisibility(v['visibility'])
            except ValueError:
                raise ValueError("Invalid visibility value")
        
        elif action in ['add_tags', 'remove_tags']:
            if 'tags' not in v or not isinstance(v['tags'], list):
                raise ValueError("tags list required for tag operations")
        
        return v


# Analytics Schemas

class MediaAnalytics(BaseModel):
    """Media analytics response."""
    total_files: int
    total_size: int
    size_by_type: Dict[MediaType, int]
    count_by_type: Dict[MediaType, int]
    uploads_by_day: List[Dict[str, Any]]
    popular_tags: List[Dict[str, Any]]
    top_viewed: List[MediaResponse]
    top_downloaded: List[MediaResponse]
    
    @property
    def total_size_gb(self) -> float:
        """Get total size in GB."""
        return round(self.total_size / (1024 ** 3), 2)


# Update forward references
MediaFolderResponse.update_forward_refs()
MediaDetailResponse.update_forward_refs()