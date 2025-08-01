"""Media models for file uploads and management."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Text, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum

from core.database import Base


class MediaType(str, Enum):
    """Types of media files."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class MediaStatus(str, Enum):
    """Status of media processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class MediaVisibility(str, Enum):
    """Visibility settings for media."""
    PRIVATE = "private"
    AGENCY = "agency"
    MODEL = "model"
    PUBLIC = "public"


class Media(Base):
    """Media file model."""
    
    __tablename__ = "media"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # S3 key or local path
    file_size = Column(Integer, nullable=False)  # Size in bytes
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA256 hash for deduplication
    
    # Media metadata
    media_type = Column(SQLEnum(MediaType), nullable=False, index=True)
    width = Column(Integer, nullable=True)  # For images/videos
    height = Column(Integer, nullable=True)  # For images/videos
    duration = Column(Float, nullable=True)  # For videos/audio in seconds
    
    # Processing information
    status = Column(SQLEnum(MediaStatus), default=MediaStatus.PENDING, nullable=False, index=True)
    processing_error = Column(Text, nullable=True)
    
    # CDN and optimization
    cdn_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    optimized_versions = Column(JSON, nullable=True)  # Different sizes/qualities
    
    # Organization
    folder_id = Column(UUID(as_uuid=True), ForeignKey("media_folders.id"), nullable=True)
    tags = Column(JSON, nullable=True, default=list)
    
    # Security and access
    visibility = Column(SQLEnum(MediaVisibility), default=MediaVisibility.PRIVATE, nullable=False)
    password_protected = Column(Boolean, default=False)
    password_hash = Column(String(255), nullable=True)
    
    # Ownership
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True, index=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Content moderation
    is_nsfw = Column(Boolean, default=False)
    moderation_status = Column(String(50), nullable=True)
    moderation_labels = Column(JSON, nullable=True)
    
    # Analytics
    view_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    alt_text = Column(String(500), nullable=True)  # For accessibility
    copyright_info = Column(String(500), nullable=True)
    exif_data = Column(JSON, nullable=True)  # For images
    custom_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    
    # Relationships
    folder = relationship("MediaFolder", back_populates="media_items")
    agency = relationship("Agency", back_populates="media_files")
    model = relationship("Model", back_populates="media_files")
    uploader = relationship("User", back_populates="uploaded_media")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_media_agency_type_created', 'agency_id', 'media_type', 'created_at'),
        Index('ix_media_model_type_created', 'model_id', 'media_type', 'created_at'),
        Index('ix_media_folder_created', 'folder_id', 'created_at'),
        Index('ix_media_status_created', 'status', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Media {self.filename} ({self.media_type.value})>"
    
    @property
    def is_image(self) -> bool:
        """Check if media is an image."""
        return self.media_type == MediaType.IMAGE
    
    @property
    def is_video(self) -> bool:
        """Check if media is a video."""
        return self.media_type == MediaType.VIDEO
    
    @property
    def file_extension(self) -> str:
        """Get file extension."""
        return self.filename.split('.')[-1].lower() if '.' in self.filename else ''
    
    @property
    def size_mb(self) -> float:
        """Get file size in MB."""
        return self.file_size / (1024 * 1024)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "media_type": self.media_type.value,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "status": self.status.value,
            "cdn_url": self.cdn_url,
            "thumbnail_url": self.thumbnail_url,
            "visibility": self.visibility.value,
            "tags": self.tags or [],
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "view_count": self.view_count,
            "download_count": self.download_count
        }


class MediaFolder(Base):
    """Folder for organizing media files."""
    
    __tablename__ = "media_folders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("media_folders.id"), nullable=True)
    
    # Ownership
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Settings
    is_public = Column(Boolean, default=False)
    color = Column(String(7), nullable=True)  # Hex color for UI
    icon = Column(String(50), nullable=True)  # Icon identifier
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    media_items = relationship("Media", back_populates="folder")
    parent = relationship("MediaFolder", remote_side=[id], backref="subfolders")
    agency = relationship("Agency")
    model = relationship("Model")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<MediaFolder {self.name}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "is_public": self.is_public,
            "color": self.color,
            "icon": self.icon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "media_count": len(self.media_items) if self.media_items else 0
        }


class MediaShare(Base):
    """Share links for media files."""
    
    __tablename__ = "media_shares"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_id = Column(UUID(as_uuid=True), ForeignKey("media.id"), nullable=False)
    share_token = Column(String(100), unique=True, nullable=False, index=True)
    
    # Share settings
    expires_at = Column(DateTime(timezone=True), nullable=True)
    max_views = Column(Integer, nullable=True)
    current_views = Column(Integer, default=0)
    password_protected = Column(Boolean, default=False)
    password_hash = Column(String(255), nullable=True)
    
    # Permissions
    allow_download = Column(Boolean, default=False)
    allow_embed = Column(Boolean, default=True)
    
    # Tracking
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    media = relationship("Media")
    creator = relationship("User")
    
    @property
    def is_expired(self) -> bool:
        """Check if share link is expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_views and self.current_views >= self.max_views:
            return True
        return False