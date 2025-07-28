"""
Image optimization pipeline for performance
"""
import io
import os
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps
import pillow_heif
from dataclasses import dataclass

from core.config import get_settings
from core.logging import get_logger
from core.storage import StorageService

settings = get_settings()
logger = get_logger(__name__)

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()


@dataclass
class ImageOptimizationConfig:
    """Configuration for image optimization"""
    max_width: int = 2048
    max_height: int = 2048
    thumbnail_sizes: List[Tuple[int, int]] = None
    quality: int = 85
    progressive: bool = True
    optimize: bool = True
    format: str = "WEBP"  # Modern format with better compression
    fallback_format: str = "JPEG"  # Fallback for compatibility
    
    def __post_init__(self):
        if self.thumbnail_sizes is None:
            self.thumbnail_sizes = [
                (150, 150),   # Small thumbnail
                (300, 300),   # Medium thumbnail
                (600, 600),   # Large thumbnail
            ]


class ImageOptimizer:
    """Optimize images for web delivery"""
    
    def __init__(
        self,
        storage_service: StorageService,
        config: Optional[ImageOptimizationConfig] = None
    ):
        self.storage = storage_service
        self.config = config or ImageOptimizationConfig()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Supported formats
        self.supported_formats = {
            ".jpg", ".jpeg", ".png", ".gif", 
            ".webp", ".bmp", ".tiff", ".heic"
        }
    
    async def optimize_image(
        self,
        image_data: bytes,
        filename: str,
        create_thumbnails: bool = True,
        custom_sizes: Optional[List[Tuple[int, int]]] = None
    ) -> Dict[str, str]:
        """
        Optimize image and create multiple versions
        
        Args:
            image_data: Raw image bytes
            filename: Original filename
            create_thumbnails: Whether to create thumbnails
            custom_sizes: Custom thumbnail sizes
            
        Returns:
            Dictionary of optimized image URLs
        """
        # Run optimization in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._optimize_image_sync,
            image_data,
            filename,
            create_thumbnails,
            custom_sizes
        )
    
    def _optimize_image_sync(
        self,
        image_data: bytes,
        filename: str,
        create_thumbnails: bool = True,
        custom_sizes: Optional[List[Tuple[int, int]]] = None
    ) -> Dict[str, str]:
        """Synchronous image optimization"""
        results = {}
        
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if needed
            if image.mode in ("RGBA", "LA", "P"):
                rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                rgb_image.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
                image = rgb_image
            
            # Fix orientation based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Generate base filename
            base_name = Path(filename).stem
            
            # Optimize original
            optimized = self._resize_and_optimize(image, self.config.max_width, self.config.max_height)
            optimized_data = self._save_optimized(optimized, self.config.format)
            
            # Upload optimized original
            original_key = f"optimized/{base_name}_optimized.{self.config.format.lower()}"
            original_url = asyncio.run(self.storage.upload(optimized_data, original_key))
            results["original"] = original_url
            
            # Create WebP version for modern browsers
            if self.config.format != "WEBP":
                webp_data = self._save_optimized(optimized, "WEBP")
                webp_key = f"optimized/{base_name}_optimized.webp"
                webp_url = asyncio.run(self.storage.upload(webp_data, webp_key))
                results["webp"] = webp_url
            
            # Create thumbnails
            if create_thumbnails:
                sizes = custom_sizes or self.config.thumbnail_sizes
                for width, height in sizes:
                    thumbnail = self._create_thumbnail(image, width, height)
                    
                    # Save in configured format
                    thumb_data = self._save_optimized(thumbnail, self.config.format)
                    thumb_key = f"thumbnails/{base_name}_{width}x{height}.{self.config.format.lower()}"
                    thumb_url = asyncio.run(self.storage.upload(thumb_data, thumb_key))
                    results[f"thumbnail_{width}x{height}"] = thumb_url
                    
                    # Save WebP version
                    if self.config.format != "WEBP":
                        webp_thumb_data = self._save_optimized(thumbnail, "WEBP")
                        webp_thumb_key = f"thumbnails/{base_name}_{width}x{height}.webp"
                        webp_thumb_url = asyncio.run(self.storage.upload(webp_thumb_data, webp_thumb_key))
                        results[f"thumbnail_{width}x{height}_webp"] = webp_thumb_url
            
            # Generate responsive image srcset
            results["srcset"] = self._generate_srcset(base_name, image)
            
            return results
            
        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            raise
    
    def _resize_and_optimize(
        self,
        image: Image.Image,
        max_width: int,
        max_height: int
    ) -> Image.Image:
        """Resize image maintaining aspect ratio"""
        # Calculate new dimensions
        width, height = image.size
        
        if width > max_width or height > max_height:
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        return image
    
    def _create_thumbnail(
        self,
        image: Image.Image,
        width: int,
        height: int
    ) -> Image.Image:
        """Create thumbnail with smart cropping"""
        # Create a copy
        thumbnail = image.copy()
        
        # Use smart cropping to maintain focal point
        thumbnail = ImageOps.fit(
            thumbnail,
            (width, height),
            Image.Resampling.LANCZOS,
            centering=(0.5, 0.5)
        )
        
        return thumbnail
    
    def _save_optimized(
        self,
        image: Image.Image,
        format: str
    ) -> bytes:
        """Save image with optimization"""
        output = io.BytesIO()
        
        save_kwargs = {
            "format": format,
            "optimize": self.config.optimize,
            "quality": self.config.quality
        }
        
        # Format-specific options
        if format in ("JPEG", "WEBP"):
            save_kwargs["progressive"] = self.config.progressive
        
        if format == "WEBP":
            save_kwargs["method"] = 6  # Slowest but best compression
            save_kwargs["lossless"] = False
        
        image.save(output, **save_kwargs)
        output.seek(0)
        
        return output.read()
    
    def _generate_srcset(
        self,
        base_name: str,
        original_image: Image.Image
    ) -> str:
        """Generate responsive image srcset"""
        width, height = original_image.size
        srcset_sizes = []
        
        # Generate common responsive sizes
        widths = [320, 640, 768, 1024, 1366, 1920]
        
        for target_width in widths:
            if target_width < width:
                srcset_sizes.append(
                    f"/optimized/{base_name}_{target_width}w.webp {target_width}w"
                )
        
        # Add original
        srcset_sizes.append(
            f"/optimized/{base_name}_optimized.webp {width}w"
        )
        
        return ", ".join(srcset_sizes)
    
    async def bulk_optimize(
        self,
        images: List[Tuple[bytes, str]],
        create_thumbnails: bool = True
    ) -> List[Dict[str, str]]:
        """
        Optimize multiple images in parallel
        
        Args:
            images: List of (image_data, filename) tuples
            create_thumbnails: Whether to create thumbnails
            
        Returns:
            List of optimization results
        """
        tasks = [
            self.optimize_image(data, filename, create_thumbnails)
            for data, filename in images
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_image_metadata(self, image_data: bytes) -> Dict[str, any]:
        """Extract image metadata"""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            metadata = {
                "format": image.format,
                "mode": image.mode,
                "size": image.size,
                "width": image.width,
                "height": image.height,
            }
            
            # Extract EXIF data if available
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                metadata["exif"] = {
                    k: v for k, v in exif.items()
                    if k in (271, 272, 274, 282, 283)  # Make, Model, Orientation, XResolution, YResolution
                }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return {}
    
    async def cleanup_old_versions(
        self,
        base_name: str,
        keep_days: int = 30
    ):
        """Clean up old image versions"""
        # List all files with the base name
        prefix = f"optimized/{base_name}"
        old_files = await self.storage.list_files(prefix, older_than_days=keep_days)
        
        # Delete old files
        for file_key in old_files:
            await self.storage.delete(file_key)
        
        logger.info(f"Cleaned up {len(old_files)} old versions of {base_name}")


class LazyImageLoader:
    """Helper for implementing lazy loading on frontend"""
    
    @staticmethod
    def generate_placeholder(
        width: int,
        height: int,
        color: str = "#f0f0f0"
    ) -> str:
        """Generate SVG placeholder for lazy loading"""
        svg = f"""
        <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="100%" height="100%" fill="{color}"/>
        </svg>
        """
        
        # Convert to base64 data URL
        import base64
        svg_bytes = svg.encode('utf-8')
        base64_svg = base64.b64encode(svg_bytes).decode('utf-8')
        
        return f"data:image/svg+xml;base64,{base64_svg}"
    
    @staticmethod
    def generate_blur_placeholder(
        image_data: bytes,
        size: Tuple[int, int] = (20, 20)
    ) -> str:
        """Generate blurred placeholder for progressive loading"""
        try:
            # Open and resize image to tiny size
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to base64
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=40)
            output.seek(0)
            
            import base64
            base64_image = base64.b64encode(output.read()).decode('utf-8')
            
            return f"data:image/jpeg;base64,{base64_image}"
            
        except Exception as e:
            logger.error(f"Failed to generate blur placeholder: {e}")
            return LazyImageLoader.generate_placeholder(size[0], size[1])