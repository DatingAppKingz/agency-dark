"""
Branding asset management service.
"""
from typing import Optional, List, BinaryIO
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import aiofiles
import hashlib
from pathlib import Path
from datetime import datetime
import mimetypes
from PIL import Image
import io

from backend.modules.whitelabel.domain.models import (
    BrandingAsset,
    LogoType
)
from backend.modules.whitelabel.domain.schemas import (
    BrandingAssetUpload,
    BrandingAssetResponse
)
from backend.core.exceptions import NotFoundException, BadRequestException
from backend.core.config import settings


class BrandingService:
    """Service for managing branding assets."""
    
    def __init__(self):
        self.upload_path = Path(settings.UPLOAD_DIR) / "branding"
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.allowed_formats = {
            "image/jpeg", "image/jpg", "image/png", 
            "image/gif", "image/svg+xml", "image/webp"
        }
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.logo_dimensions = {
            LogoType.AGENCY_LOGO: (512, 512),
            LogoType.AGENCY_ICON: (64, 64),
            LogoType.MODEL_LOGO: (512, 512),
            LogoType.MODEL_BANNER: (1920, 480),
            LogoType.EMAIL_HEADER: (600, 200),
            LogoType.FAVICON: (32, 32)
        }
    
    async def upload_asset(
        self,
        file_content: bytes,
        asset_data: BrandingAssetUpload,
        agency_id: Optional[UUID],
        model_id: Optional[UUID],
        user_id: UUID,
        db: AsyncSession
    ) -> BrandingAssetResponse:
        """Upload a branding asset."""
        # Validate file
        if len(file_content) > self.max_file_size:
            raise BadRequestException(f"File size exceeds {self.max_file_size // 1024 // 1024}MB limit")
        
        if asset_data.mime_type not in self.allowed_formats:
            raise BadRequestException(f"Invalid file format. Allowed: {', '.join(self.allowed_formats)}")
        
        # Validate owner
        if not agency_id and not model_id:
            raise BadRequestException("Either agency_id or model_id must be provided")
        
        if agency_id and model_id:
            raise BadRequestException("Cannot set both agency_id and model_id")
        
        # Process image
        image_info = await self._process_image(
            file_content,
            asset_data.asset_type,
            asset_data.mime_type
        )
        
        # Generate unique filename
        file_hash = hashlib.sha256(file_content).hexdigest()[:16]
        file_ext = mimetypes.guess_extension(asset_data.mime_type) or ".png"
        unique_filename = f"{asset_data.asset_type}_{file_hash}{file_ext}"
        
        # Save file
        file_path = self.upload_path / unique_filename
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # Deactivate existing assets of same type
        await self._deactivate_existing_assets(
            asset_data.asset_type,
            agency_id,
            model_id,
            db
        )
        
        # Create database record
        asset = BrandingAsset(
            agency_id=agency_id,
            model_id=model_id,
            asset_type=asset_data.asset_type.value,
            file_name=asset_data.file_name,
            file_url=f"/uploads/branding/{unique_filename}",
            file_size=len(file_content),
            mime_type=asset_data.mime_type,
            width=image_info.get("width"),
            height=image_info.get("height"),
            is_active=True,
            uploaded_by=user_id
        )
        
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        
        return BrandingAssetResponse.from_orm(asset)
    
    async def get_asset(
        self,
        asset_id: UUID,
        db: AsyncSession
    ) -> BrandingAssetResponse:
        """Get a specific branding asset."""
        result = await db.execute(
            select(BrandingAsset)
            .filter(BrandingAsset.id == asset_id)
        )
        asset = result.scalar_one_or_none()
        
        if not asset:
            raise NotFoundException("Branding asset not found")
        
        return BrandingAssetResponse.from_orm(asset)
    
    async def get_agency_assets(
        self,
        agency_id: UUID,
        asset_type: Optional[LogoType] = None,
        active_only: bool = True,
        db: AsyncSession = None
    ) -> List[BrandingAssetResponse]:
        """Get all branding assets for an agency."""
        query = select(BrandingAsset).filter(
            BrandingAsset.agency_id == agency_id
        )
        
        if asset_type:
            query = query.filter(BrandingAsset.asset_type == asset_type.value)
        
        if active_only:
            query = query.filter(BrandingAsset.is_active == True)
        
        query = query.order_by(BrandingAsset.uploaded_at.desc())
        
        result = await db.execute(query)
        assets = result.scalars().all()
        
        return [BrandingAssetResponse.from_orm(asset) for asset in assets]
    
    async def get_model_assets(
        self,
        model_id: UUID,
        asset_type: Optional[LogoType] = None,
        active_only: bool = True,
        db: AsyncSession = None
    ) -> List[BrandingAssetResponse]:
        """Get all branding assets for a model."""
        query = select(BrandingAsset).filter(
            BrandingAsset.model_id == model_id
        )
        
        if asset_type:
            query = query.filter(BrandingAsset.asset_type == asset_type.value)
        
        if active_only:
            query = query.filter(BrandingAsset.is_active == True)
        
        query = query.order_by(BrandingAsset.uploaded_at.desc())
        
        result = await db.execute(query)
        assets = result.scalars().all()
        
        return [BrandingAssetResponse.from_orm(asset) for asset in assets]
    
    async def update_asset_status(
        self,
        asset_id: UUID,
        is_active: bool,
        db: AsyncSession
    ) -> BrandingAssetResponse:
        """Update asset active status."""
        result = await db.execute(
            select(BrandingAsset)
            .filter(BrandingAsset.id == asset_id)
        )
        asset = result.scalar_one_or_none()
        
        if not asset:
            raise NotFoundException("Branding asset not found")
        
        # If activating, deactivate others of same type
        if is_active and not asset.is_active:
            await self._deactivate_existing_assets(
                asset.asset_type,
                asset.agency_id,
                asset.model_id,
                db
            )
        
        asset.is_active = is_active
        
        await db.commit()
        await db.refresh(asset)
        
        return BrandingAssetResponse.from_orm(asset)
    
    async def delete_asset(
        self,
        asset_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a branding asset."""
        result = await db.execute(
            select(BrandingAsset)
            .filter(BrandingAsset.id == asset_id)
        )
        asset = result.scalar_one_or_none()
        
        if not asset:
            raise NotFoundException("Branding asset not found")
        
        # Delete file
        file_path = self.upload_path.parent / asset.file_url.lstrip("/uploads/")
        if file_path.exists():
            file_path.unlink()
        
        # Delete database record
        await db.delete(asset)
        await db.commit()
        
        return True
    
    async def _process_image(
        self,
        file_content: bytes,
        asset_type: LogoType,
        mime_type: str
    ) -> dict:
        """Process and validate image."""
        if mime_type == "image/svg+xml":
            # SVG files don't need dimension validation
            return {"format": "SVG"}
        
        try:
            # Open image
            image = Image.open(io.BytesIO(file_content))
            
            # Get dimensions
            width, height = image.size
            
            # Validate dimensions if required
            if asset_type in self.logo_dimensions:
                required_width, required_height = self.logo_dimensions[asset_type]
                
                # For logos, we allow larger images that will be resized
                if asset_type in [LogoType.AGENCY_LOGO, LogoType.MODEL_LOGO]:
                    if width < required_width or height < required_height:
                        raise BadRequestException(
                            f"{asset_type.value} must be at least {required_width}x{required_height}px"
                        )
                # For exact dimension requirements
                elif asset_type in [LogoType.FAVICON, LogoType.AGENCY_ICON]:
                    if width != required_width or height != required_height:
                        raise BadRequestException(
                            f"{asset_type.value} must be exactly {required_width}x{required_height}px"
                        )
            
            return {
                "width": width,
                "height": height,
                "format": image.format
            }
            
        except Exception as e:
            raise BadRequestException(f"Invalid image file: {str(e)}")
    
    async def _deactivate_existing_assets(
        self,
        asset_type: str,
        agency_id: Optional[UUID],
        model_id: Optional[UUID],
        db: AsyncSession
    ):
        """Deactivate existing assets of the same type."""
        query = select(BrandingAsset).filter(
            and_(
                BrandingAsset.asset_type == asset_type,
                BrandingAsset.is_active == True
            )
        )
        
        if agency_id:
            query = query.filter(BrandingAsset.agency_id == agency_id)
        elif model_id:
            query = query.filter(BrandingAsset.model_id == model_id)
        
        result = await db.execute(query)
        existing_assets = result.scalars().all()
        
        for asset in existing_assets:
            asset.is_active = False
        
        await db.flush()