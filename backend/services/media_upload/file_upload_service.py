"""File upload service with security and processing."""

import os
import hashlib
import uuid
import mimetypes
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import aiofiles
import magic
from PIL import Image
import cv2
import numpy as np
from fastapi import UploadFile, HTTPException, status
import boto3
from botocore.exceptions import ClientError
import clamd
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import get_logger
from models.media import Media, MediaType, MediaStatus, MediaVisibility
from models.user import User

logger = get_logger(__name__)


class FileUploadService:
    """Service for handling file uploads with security and processing."""
    
    # Allowed MIME types by category
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/webp', 'image/bmp', 'image/tiff'
    }
    
    ALLOWED_VIDEO_TYPES = {
        'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
        'video/x-ms-wmv', 'video/webm', 'video/ogg'
    }
    
    ALLOWED_AUDIO_TYPES = {
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg',
        'audio/webm', 'audio/aac', 'audio/flac'
    }
    
    ALLOWED_DOCUMENT_TYPES = {
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/csv'
    }
    
    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB
    
    # Image processing settings
    THUMBNAIL_SIZE = (300, 300)
    IMAGE_SIZES = {
        'small': (480, 480),
        'medium': (1024, 1024),
        'large': (1920, 1920)
    }
    
    def __init__(self):
        self.s3_client = None
        self.clam_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize external service clients."""
        # Initialize S3 client
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
        
        # Initialize ClamAV client for virus scanning
        try:
            self.clam_client = clamd.ClamdUnixSocket()
            self.clam_client.ping()
        except Exception as e:
            logger.warning(f"ClamAV not available: {e}")
            self.clam_client = None
    
    async def upload_file(
        self,
        file: UploadFile,
        user: User,
        agency_id: str,
        model_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        visibility: MediaVisibility = MediaVisibility.PRIVATE,
        tags: Optional[List[str]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Media:
        """
        Upload and process a file.
        
        Args:
            file: The uploaded file
            user: User uploading the file
            agency_id: Agency ID
            model_id: Optional model ID
            folder_id: Optional folder ID
            visibility: File visibility setting
            tags: Optional tags
            title: Optional title
            description: Optional description
            
        Returns:
            Media object
            
        Raises:
            HTTPException: If upload fails
        """
        # Validate file
        await self._validate_file(file)
        
        # Generate unique filename
        file_extension = self._get_file_extension(file.filename)
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Create temporary file
        temp_path = f"/tmp/{unique_filename}"
        try:
            # Save uploaded file temporarily
            async with aiofiles.open(temp_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # Reset file position
            await file.seek(0)
            
            # Scan for viruses
            if not await self._scan_for_viruses(temp_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File failed virus scan"
                )
            
            # Calculate file hash
            file_hash = await self._calculate_file_hash(temp_path)
            
            # Determine media type
            mime_type = await self._get_mime_type(temp_path)
            media_type = self._get_media_type(mime_type)
            
            # Get file metadata
            metadata = await self._extract_metadata(temp_path, media_type)
            
            # Create media record
            media = Media(
                filename=unique_filename,
                original_filename=file.filename,
                file_path=f"uploads/{agency_id}/{unique_filename}",
                file_size=os.path.getsize(temp_path),
                mime_type=mime_type,
                file_hash=file_hash,
                media_type=media_type,
                width=metadata.get('width'),
                height=metadata.get('height'),
                duration=metadata.get('duration'),
                status=MediaStatus.PROCESSING,
                visibility=visibility,
                agency_id=agency_id,
                model_id=model_id,
                folder_id=folder_id,
                uploaded_by=user.id,
                tags=tags or [],
                title=title,
                description=description,
                exif_data=metadata.get('exif')
            )
            
            # Upload to storage
            if self.s3_client:
                upload_path = await self._upload_to_s3(temp_path, media.file_path)
                media.cdn_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{upload_path}"
            else:
                # Use local storage
                local_path = await self._save_locally(temp_path, media.file_path)
                media.cdn_url = f"/media/{local_path}"
            
            # Process media based on type
            if media_type == MediaType.IMAGE:
                await self._process_image(temp_path, media)
            elif media_type == MediaType.VIDEO:
                await self._process_video(temp_path, media)
            
            media.status = MediaStatus.READY
            
            return media
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    async def _validate_file(self, file: UploadFile):
        """Validate uploaded file."""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset position
        
        # Get mime type from filename
        mime_type, _ = mimetypes.guess_type(file.filename)
        
        # Validate based on type
        if mime_type in self.ALLOWED_IMAGE_TYPES:
            if file_size > self.MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image file too large. Maximum size: {self.MAX_IMAGE_SIZE / 1024 / 1024}MB"
                )
        elif mime_type in self.ALLOWED_VIDEO_TYPES:
            if file_size > self.MAX_VIDEO_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Video file too large. Maximum size: {self.MAX_VIDEO_SIZE / 1024 / 1024}MB"
                )
        elif mime_type in self.ALLOWED_AUDIO_TYPES:
            if file_size > self.MAX_AUDIO_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Audio file too large. Maximum size: {self.MAX_AUDIO_SIZE / 1024 / 1024}MB"
                )
        elif mime_type in self.ALLOWED_DOCUMENT_TYPES:
            if file_size > self.MAX_DOCUMENT_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Document file too large. Maximum size: {self.MAX_DOCUMENT_SIZE / 1024 / 1024}MB"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type not allowed: {mime_type}"
            )
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        if '.' in filename:
            return '.' + filename.rsplit('.', 1)[1].lower()
        return ''
    
    async def _scan_for_viruses(self, file_path: str) -> bool:
        """Scan file for viruses using ClamAV."""
        if not self.clam_client:
            logger.warning("Virus scanning not available")
            return True  # Allow if scanner not available
        
        try:
            result = self.clam_client.scan(file_path)
            if file_path in result:
                status = result[file_path][0]
                if status == 'OK':
                    return True
                else:
                    logger.warning(f"Virus detected: {result[file_path][1]}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Virus scan failed: {e}")
            return True  # Allow on scan failure (configurable)
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    async def _get_mime_type(self, file_path: str) -> str:
        """Get accurate MIME type using python-magic."""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(file_path)
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}")
            # Fallback to mimetypes
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type or 'application/octet-stream'
    
    def _get_media_type(self, mime_type: str) -> MediaType:
        """Determine media type from MIME type."""
        if mime_type in self.ALLOWED_IMAGE_TYPES:
            return MediaType.IMAGE
        elif mime_type in self.ALLOWED_VIDEO_TYPES:
            return MediaType.VIDEO
        elif mime_type in self.ALLOWED_AUDIO_TYPES:
            return MediaType.AUDIO
        elif mime_type in self.ALLOWED_DOCUMENT_TYPES:
            return MediaType.DOCUMENT
        else:
            return MediaType.OTHER
    
    async def _extract_metadata(self, file_path: str, media_type: MediaType) -> Dict[str, Any]:
        """Extract metadata from file."""
        metadata = {}
        
        if media_type == MediaType.IMAGE:
            try:
                with Image.open(file_path) as img:
                    metadata['width'], metadata['height'] = img.size
                    metadata['format'] = img.format
                    
                    # Extract EXIF data
                    if hasattr(img, '_getexif') and img._getexif():
                        exif = {
                            k: v for k, v in img._getexif().items()
                            if k in Image.ExifTags.TAGS
                        }
                        metadata['exif'] = {
                            Image.ExifTags.TAGS[k]: v
                            for k, v in exif.items()
                        }
            except Exception as e:
                logger.warning(f"Failed to extract image metadata: {e}")
        
        elif media_type == MediaType.VIDEO:
            try:
                cap = cv2.VideoCapture(file_path)
                metadata['width'] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                metadata['height'] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                metadata['fps'] = cap.get(cv2.CAP_PROP_FPS)
                metadata['frame_count'] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                metadata['duration'] = metadata['frame_count'] / metadata['fps'] if metadata['fps'] > 0 else 0
                cap.release()
            except Exception as e:
                logger.warning(f"Failed to extract video metadata: {e}")
        
        return metadata
    
    async def _upload_to_s3(self, local_path: str, s3_key: str) -> str:
        """Upload file to S3."""
        try:
            with open(local_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=settings.AWS_S3_BUCKET,
                    Key=s3_key,
                    Body=f,
                    ContentType=await self._get_mime_type(local_path)
                )
            return s3_key
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise
    
    async def _save_locally(self, temp_path: str, relative_path: str) -> str:
        """Save file locally."""
        local_dir = os.path.join(settings.MEDIA_ROOT, os.path.dirname(relative_path))
        os.makedirs(local_dir, exist_ok=True)
        
        local_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        async with aiofiles.open(temp_path, 'rb') as src:
            async with aiofiles.open(local_path, 'wb') as dst:
                await dst.write(await src.read())
        
        return relative_path
    
    async def _process_image(self, file_path: str, media: Media):
        """Process image file (create thumbnails, optimize)."""
        try:
            with Image.open(file_path) as img:
                # Create thumbnail
                thumbnail = img.copy()
                thumbnail.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                
                thumb_filename = f"thumb_{media.filename}"
                thumb_path = f"/tmp/{thumb_filename}"
                thumbnail.save(thumb_path, optimize=True, quality=85)
                
                # Upload thumbnail
                if self.s3_client:
                    thumb_s3_key = f"thumbnails/{media.agency_id}/{thumb_filename}"
                    await self._upload_to_s3(thumb_path, thumb_s3_key)
                    media.thumbnail_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{thumb_s3_key}"
                else:
                    thumb_local_path = f"thumbnails/{media.agency_id}/{thumb_filename}"
                    await self._save_locally(thumb_path, thumb_local_path)
                    media.thumbnail_url = f"/media/{thumb_local_path}"
                
                # Create optimized versions
                optimized_versions = {}
                for size_name, dimensions in self.IMAGE_SIZES.items():
                    if img.size[0] > dimensions[0] or img.size[1] > dimensions[1]:
                        resized = img.copy()
                        resized.thumbnail(dimensions, Image.Resampling.LANCZOS)
                        
                        opt_filename = f"{size_name}_{media.filename}"
                        opt_path = f"/tmp/{opt_filename}"
                        resized.save(opt_path, optimize=True, quality=90)
                        
                        if self.s3_client:
                            opt_s3_key = f"optimized/{media.agency_id}/{opt_filename}"
                            await self._upload_to_s3(opt_path, opt_s3_key)
                            optimized_versions[size_name] = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{opt_s3_key}"
                        else:
                            opt_local_path = f"optimized/{media.agency_id}/{opt_filename}"
                            await self._save_locally(opt_path, opt_local_path)
                            optimized_versions[size_name] = f"/media/{opt_local_path}"
                        
                        os.remove(opt_path)
                
                media.optimized_versions = optimized_versions
                
                # Clean up
                os.remove(thumb_path)
                
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            media.processing_error = str(e)
    
    async def _process_video(self, file_path: str, media: Media):
        """Process video file (extract thumbnail, transcode if needed)."""
        try:
            cap = cv2.VideoCapture(file_path)
            
            # Extract thumbnail from first frame
            ret, frame = cap.read()
            if ret:
                thumb_filename = f"thumb_{media.filename}.jpg"
                thumb_path = f"/tmp/{thumb_filename}"
                cv2.imwrite(thumb_path, frame)
                
                # Upload thumbnail
                if self.s3_client:
                    thumb_s3_key = f"thumbnails/{media.agency_id}/{thumb_filename}"
                    await self._upload_to_s3(thumb_path, thumb_s3_key)
                    media.thumbnail_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{thumb_s3_key}"
                else:
                    thumb_local_path = f"thumbnails/{media.agency_id}/{thumb_filename}"
                    await self._save_locally(thumb_path, thumb_local_path)
                    media.thumbnail_url = f"/media/{thumb_local_path}"
                
                os.remove(thumb_path)
            
            cap.release()
            
            # TODO: Add video transcoding for different qualities/formats
            
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            media.processing_error = str(e)
    
    async def delete_file(self, media: Media):
        """Delete file from storage."""
        try:
            if self.s3_client:
                # Delete from S3
                self.s3_client.delete_object(
                    Bucket=settings.AWS_S3_BUCKET,
                    Key=media.file_path
                )
                
                # Delete thumbnail
                if media.thumbnail_url:
                    thumb_key = media.thumbnail_url.split('/')[-2:]
                    thumb_key = '/'.join(thumb_key)
                    self.s3_client.delete_object(
                        Bucket=settings.AWS_S3_BUCKET,
                        Key=f"thumbnails/{thumb_key}"
                    )
                
                # Delete optimized versions
                if media.optimized_versions:
                    for url in media.optimized_versions.values():
                        opt_key = url.split('/')[-2:]
                        opt_key = '/'.join(opt_key)
                        self.s3_client.delete_object(
                            Bucket=settings.AWS_S3_BUCKET,
                            Key=f"optimized/{opt_key}"
                        )
            else:
                # Delete from local storage
                local_path = os.path.join(settings.MEDIA_ROOT, media.file_path)
                if os.path.exists(local_path):
                    os.remove(local_path)
                
                # Delete thumbnail
                if media.thumbnail_url:
                    thumb_path = os.path.join(settings.MEDIA_ROOT, media.thumbnail_url.replace('/media/', ''))
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                
                # Delete optimized versions
                if media.optimized_versions:
                    for url in media.optimized_versions.values():
                        opt_path = os.path.join(settings.MEDIA_ROOT, url.replace('/media/', ''))
                        if os.path.exists(opt_path):
                            os.remove(opt_path)
            
            media.status = MediaStatus.DELETED
            media.deleted_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"File deletion failed: {e}")
            raise