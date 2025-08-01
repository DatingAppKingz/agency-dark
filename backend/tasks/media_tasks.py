"""Media processing background tasks."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
import tempfile
import hashlib
from PIL import Image
import cv2
import numpy as np
from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import asyncio
import aiofiles

from core.database_sync import get_db_sync
from core.logger import get_logger
from core.config import settings
from models.media import Media, MediaType, MediaStatus
from services.media_upload.file_upload_service import FileUploadService

logger = get_logger(__name__)


class MediaTask(Task):
    """Base task with database session management."""
    _db = None
    _file_service = None

    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            self._db = get_db_sync()
        return self._db
    
    @property
    def file_service(self) -> FileUploadService:
        if self._file_service is None:
            self._file_service = FileUploadService()
        return self._file_service


@shared_task(bind=True, base=MediaTask, name='tasks.media_tasks.process_image')
def process_image(self, media_id: str, processing_options: Optional[Dict[str, Any]] = None):
    """
    Process an uploaded image.
    
    Tasks:
    - Generate thumbnails
    - Create optimized versions
    - Extract metadata
    - Apply watermarks (if configured)
    - Run content moderation
    """
    try:
        logger.info(f"Processing image {media_id}")
        
        # Get media record
        media = asyncio.run(self._get_media(media_id))
        if not media:
            logger.error(f"Media {media_id} not found")
            return {"success": False, "error": "Media not found"}
        
        if media.status != MediaStatus.PROCESSING:
            logger.warning(f"Media {media_id} not in processing state")
            return {"success": False, "error": "Invalid media state"}
        
        # Download file to temp location
        temp_path = asyncio.run(self._download_to_temp(media))
        
        try:
            # Open image
            with Image.open(temp_path) as img:
                # Extract metadata
                metadata = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode
                }
                
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
                
                # Generate thumbnail
                thumbnail_path = self._generate_thumbnail(img, media_id)
                thumbnail_url = asyncio.run(self._upload_file(
                    thumbnail_path, 
                    f"thumbnails/{media.agency_id}/thumb_{media.filename}"
                ))
                
                # Generate optimized versions
                optimized_versions = {}
                sizes = {
                    'small': (480, 480),
                    'medium': (1024, 1024),
                    'large': (1920, 1920)
                }
                
                for size_name, dimensions in sizes.items():
                    if img.width > dimensions[0] or img.height > dimensions[1]:
                        opt_path = self._create_optimized_version(
                            img, dimensions, size_name, media_id
                        )
                        opt_url = asyncio.run(self._upload_file(
                            opt_path,
                            f"optimized/{media.agency_id}/{size_name}_{media.filename}"
                        ))
                        optimized_versions[size_name] = opt_url
                        os.remove(opt_path)
                
                # Apply watermark if configured
                if processing_options and processing_options.get('watermark'):
                    watermark_path = self._apply_watermark(
                        temp_path, 
                        processing_options['watermark']
                    )
                    # Update main file with watermarked version
                    asyncio.run(self._upload_file(
                        watermark_path,
                        media.file_path,
                        replace=True
                    ))
                    os.remove(watermark_path)
                
                # Run content moderation
                moderation_result = self._moderate_image(temp_path)
                
                # Update media record
                asyncio.run(self._update_media(
                    media_id,
                    {
                        'status': MediaStatus.READY,
                        'width': metadata['width'],
                        'height': metadata['height'],
                        'thumbnail_url': thumbnail_url,
                        'optimized_versions': optimized_versions,
                        'exif_data': metadata.get('exif'),
                        'is_nsfw': moderation_result.get('is_nsfw', False),
                        'moderation_labels': moderation_result.get('labels', [])
                    }
                ))
                
                # Clean up
                os.remove(thumbnail_path)
                
                logger.info(f"Successfully processed image {media_id}")
                return {
                    "success": True,
                    "media_id": media_id,
                    "thumbnail_url": thumbnail_url,
                    "optimized_versions": optimized_versions
                }
                
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout processing image {media_id}")
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.FAILED,
                'processing_error': 'Processing timeout'
            }
        ))
        raise
        
    except Exception as e:
        logger.error(f"Error processing image {media_id}: {e}")
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.FAILED,
                'processing_error': str(e)
            }
        ))
        return {"success": False, "error": str(e)}
    
    async def _get_media(self, media_id: str) -> Optional[Media]:
        """Get media record from database."""
        async with self.db as session:
            result = await session.execute(
                select(Media).where(Media.id == media_id)
            )
            return result.scalar_one_or_none()
    
    async def _update_media(self, media_id: str, updates: Dict[str, Any]):
        """Update media record."""
        async with self.db as session:
            media = await session.get(Media, media_id)
            if media:
                for key, value in updates.items():
                    setattr(media, key, value)
                media.updated_at = datetime.utcnow()
                await session.commit()
    
    async def _download_to_temp(self, media: Media) -> str:
        """Download media file to temporary location."""
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"media_{media.id}_{media.filename}")
        
        # If using S3, download from S3
        # For now, assume local storage
        if media.file_path.startswith('/'):
            # Local file
            import shutil
            shutil.copy(media.file_path, temp_path)
        else:
            # Download from S3 or CDN
            # Implement S3 download logic here
            pass
        
        return temp_path
    
    async def _upload_file(self, local_path: str, remote_path: str, replace: bool = False) -> str:
        """Upload file to storage."""
        # Implement S3 upload or local storage
        # Return the URL
        return f"/media/{remote_path}"
    
    def _generate_thumbnail(self, img: Image.Image, media_id: str) -> str:
        """Generate thumbnail image."""
        thumb_size = (300, 300)
        thumb = img.copy()
        thumb.thumbnail(thumb_size, Image.Resampling.LANCZOS)
        
        temp_path = os.path.join(tempfile.gettempdir(), f"thumb_{media_id}.jpg")
        thumb.save(temp_path, 'JPEG', quality=85, optimize=True)
        
        return temp_path
    
    def _create_optimized_version(
        self, 
        img: Image.Image, 
        dimensions: tuple, 
        size_name: str, 
        media_id: str
    ) -> str:
        """Create optimized version of image."""
        opt_img = img.copy()
        opt_img.thumbnail(dimensions, Image.Resampling.LANCZOS)
        
        temp_path = os.path.join(
            tempfile.gettempdir(), 
            f"{size_name}_{media_id}.jpg"
        )
        opt_img.save(temp_path, 'JPEG', quality=90, optimize=True)
        
        return temp_path
    
    def _apply_watermark(self, image_path: str, watermark_config: Dict[str, Any]) -> str:
        """Apply watermark to image."""
        # Implement watermarking logic
        # For now, return original path
        return image_path
    
    def _moderate_image(self, image_path: str) -> Dict[str, Any]:
        """Run content moderation on image."""
        # Implement image moderation using AI service
        # For now, return dummy result
        return {
            'is_nsfw': False,
            'labels': []
        }


@shared_task(bind=True, base=MediaTask, name='tasks.media_tasks.process_video')
def process_video(self, media_id: str, processing_options: Optional[Dict[str, Any]] = None):
    """
    Process an uploaded video.
    
    Tasks:
    - Extract thumbnail
    - Generate preview clips
    - Transcode to different qualities
    - Extract metadata
    - Run content moderation
    """
    try:
        logger.info(f"Processing video {media_id}")
        
        # Get media record
        media = asyncio.run(self._get_media(media_id))
        if not media:
            logger.error(f"Media {media_id} not found")
            return {"success": False, "error": "Media not found"}
        
        # Download file to temp location
        temp_path = asyncio.run(self._download_to_temp(media))
        
        try:
            # Open video
            cap = cv2.VideoCapture(temp_path)
            
            # Extract metadata
            metadata = {
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'duration': 0
            }
            
            if metadata['fps'] > 0:
                metadata['duration'] = metadata['frame_count'] / metadata['fps']
            
            # Extract thumbnail from first frame
            ret, frame = cap.read()
            if ret:
                thumb_path = os.path.join(
                    tempfile.gettempdir(), 
                    f"thumb_{media_id}.jpg"
                )
                cv2.imwrite(thumb_path, frame)
                
                thumbnail_url = asyncio.run(self._upload_file(
                    thumb_path,
                    f"thumbnails/{media.agency_id}/thumb_{media.filename}.jpg"
                ))
                os.remove(thumb_path)
            else:
                thumbnail_url = None
            
            cap.release()
            
            # Generate preview clip (first 10 seconds)
            if processing_options and processing_options.get('generate_preview', True):
                preview_path = self._generate_preview_clip(temp_path, media_id)
                preview_url = asyncio.run(self._upload_file(
                    preview_path,
                    f"previews/{media.agency_id}/preview_{media.filename}"
                ))
                os.remove(preview_path)
            else:
                preview_url = None
            
            # Transcode to different qualities
            transcoded_versions = {}
            if processing_options and processing_options.get('transcode', False):
                qualities = ['720p', '480p', '360p']
                for quality in qualities:
                    transcoded_path = self._transcode_video(
                        temp_path, quality, media_id
                    )
                    if transcoded_path:
                        transcoded_url = asyncio.run(self._upload_file(
                            transcoded_path,
                            f"transcoded/{media.agency_id}/{quality}_{media.filename}"
                        ))
                        transcoded_versions[quality] = transcoded_url
                        os.remove(transcoded_path)
            
            # Run content moderation
            moderation_result = self._moderate_video(temp_path)
            
            # Update media record
            asyncio.run(self._update_media(
                media_id,
                {
                    'status': MediaStatus.READY,
                    'width': metadata['width'],
                    'height': metadata['height'],
                    'duration': metadata['duration'],
                    'thumbnail_url': thumbnail_url,
                    'optimized_versions': {
                        'preview': preview_url,
                        **transcoded_versions
                    },
                    'is_nsfw': moderation_result.get('is_nsfw', False),
                    'moderation_labels': moderation_result.get('labels', [])
                }
            ))
            
            logger.info(f"Successfully processed video {media_id}")
            return {
                "success": True,
                "media_id": media_id,
                "thumbnail_url": thumbnail_url,
                "preview_url": preview_url,
                "transcoded_versions": transcoded_versions
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except SoftTimeLimitExceeded:
        logger.error(f"Task timeout processing video {media_id}")
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.FAILED,
                'processing_error': 'Processing timeout'
            }
        ))
        raise
        
    except Exception as e:
        logger.error(f"Error processing video {media_id}: {e}")
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.FAILED,
                'processing_error': str(e)
            }
        ))
        return {"success": False, "error": str(e)}
    
    def _generate_preview_clip(self, video_path: str, media_id: str) -> str:
        """Generate preview clip (first 10 seconds)."""
        # Use ffmpeg-python or moviepy to generate preview
        # For now, return dummy path
        preview_path = os.path.join(
            tempfile.gettempdir(),
            f"preview_{media_id}.mp4"
        )
        # Implement preview generation
        return preview_path
    
    def _transcode_video(self, video_path: str, quality: str, media_id: str) -> Optional[str]:
        """Transcode video to different quality."""
        # Use ffmpeg-python to transcode
        # For now, return None
        return None
    
    def _moderate_video(self, video_path: str) -> Dict[str, Any]:
        """Run content moderation on video."""
        # Implement video moderation
        return {
            'is_nsfw': False,
            'labels': []
        }


@shared_task(bind=True, base=MediaTask, name='tasks.media_tasks.process_document')
def process_document(self, media_id: str):
    """
    Process an uploaded document.
    
    Tasks:
    - Extract text content
    - Generate preview/thumbnail
    - Extract metadata
    """
    try:
        logger.info(f"Processing document {media_id}")
        
        # Get media record
        media = asyncio.run(self._get_media(media_id))
        if not media:
            return {"success": False, "error": "Media not found"}
        
        # Process based on document type
        if media.mime_type == 'application/pdf':
            result = self._process_pdf(media)
        elif media.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            result = self._process_word(media)
        else:
            result = {'text_content': None, 'page_count': None}
        
        # Update media record
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.READY,
                'custom_metadata': result
            }
        ))
        
        return {"success": True, "media_id": media_id, "metadata": result}
        
    except Exception as e:
        logger.error(f"Error processing document {media_id}: {e}")
        asyncio.run(self._update_media(
            media_id,
            {
                'status': MediaStatus.FAILED,
                'processing_error': str(e)
            }
        ))
        return {"success": False, "error": str(e)}
    
    def _process_pdf(self, media: Media) -> Dict[str, Any]:
        """Process PDF document."""
        # Use PyPDF2 or pdfplumber to extract text
        return {
            'page_count': 0,
            'text_content': None
        }
    
    def _process_word(self, media: Media) -> Dict[str, Any]:
        """Process Word document."""
        # Use python-docx to extract text
        return {
            'page_count': 0,
            'text_content': None
        }


@shared_task(name='tasks.media_tasks.process_pending_media')
def process_pending_media():
    """
    Periodic task to process pending media files.
    
    Runs every 5 minutes to check for media in PENDING status.
    """
    try:
        # Get pending media
        pending_media = asyncio.run(_get_pending_media())
        
        logger.info(f"Found {len(pending_media)} pending media files")
        
        for media in pending_media:
            # Update status to processing
            asyncio.run(_update_media_status(media.id, MediaStatus.PROCESSING))
            
            # Queue appropriate processing task
            if media.media_type == MediaType.IMAGE:
                process_image.delay(str(media.id))
            elif media.media_type == MediaType.VIDEO:
                process_video.delay(str(media.id))
            elif media.media_type == MediaType.DOCUMENT:
                process_document.delay(str(media.id))
            else:
                # Mark as ready for other types
                asyncio.run(_update_media_status(media.id, MediaStatus.READY))
        
        return {
            "success": True,
            "processed_count": len(pending_media)
        }
        
    except Exception as e:
        logger.error(f"Error processing pending media: {e}")
        return {"success": False, "error": str(e)}


async def _get_pending_media() -> List[Media]:
    """Get media files in pending status."""
    async with get_db_sync() as session:
        result = await session.execute(
            select(Media).where(
                and_(
                    Media.status == MediaStatus.PENDING,
                    Media.created_at > datetime.utcnow() - timedelta(hours=24)
                )
            ).limit(50)
        )
        return result.scalars().all()


async def _update_media_status(media_id: str, status: MediaStatus):
    """Update media status."""
    async with get_db_sync() as session:
        media = await session.get(Media, media_id)
        if media:
            media.status = status
            media.updated_at = datetime.utcnow()
            await session.commit()


@shared_task(name='tasks.media_tasks.cleanup_failed_uploads')
def cleanup_failed_uploads():
    """
    Clean up failed media uploads older than 7 days.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        # Get failed media
        failed_media = asyncio.run(_get_failed_media(cutoff_date))
        
        logger.info(f"Cleaning up {len(failed_media)} failed uploads")
        
        for media in failed_media:
            # Delete from storage if exists
            try:
                asyncio.run(_delete_media_files(media))
            except Exception as e:
                logger.error(f"Error deleting files for media {media.id}: {e}")
            
            # Delete from database
            asyncio.run(_delete_media_record(media.id))
        
        return {
            "success": True,
            "cleaned_count": len(failed_media)
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up failed uploads: {e}")
        return {"success": False, "error": str(e)}


async def _get_failed_media(cutoff_date: datetime) -> List[Media]:
    """Get failed media older than cutoff date."""
    async with get_db_sync() as session:
        result = await session.execute(
            select(Media).where(
                and_(
                    Media.status == MediaStatus.FAILED,
                    Media.created_at < cutoff_date
                )
            )
        )
        return result.scalars().all()


async def _delete_media_files(media: Media):
    """Delete media files from storage."""
    # Implement file deletion logic
    pass


async def _delete_media_record(media_id: str):
    """Delete media record from database."""
    async with get_db_sync() as session:
        media = await session.get(Media, media_id)
        if media:
            await session.delete(media)
            await session.commit()


@shared_task(name='tasks.media_tasks.generate_missing_thumbnails')
def generate_missing_thumbnails():
    """
    Generate thumbnails for media files that don't have them.
    """
    try:
        # Get media without thumbnails
        media_list = asyncio.run(_get_media_without_thumbnails())
        
        logger.info(f"Generating thumbnails for {len(media_list)} media files")
        
        for media in media_list:
            if media.media_type == MediaType.IMAGE:
                process_image.delay(str(media.id), {'thumbnail_only': True})
            elif media.media_type == MediaType.VIDEO:
                process_video.delay(str(media.id), {'thumbnail_only': True})
        
        return {
            "success": True,
            "queued_count": len(media_list)
        }
        
    except Exception as e:
        logger.error(f"Error generating missing thumbnails: {e}")
        return {"success": False, "error": str(e)}


async def _get_media_without_thumbnails() -> List[Media]:
    """Get media files without thumbnails."""
    async with get_db_sync() as session:
        result = await session.execute(
            select(Media).where(
                and_(
                    Media.status == MediaStatus.READY,
                    Media.thumbnail_url.is_(None),
                    Media.media_type.in_([MediaType.IMAGE, MediaType.VIDEO])
                )
            ).limit(100)
        )
        return result.scalars().all()