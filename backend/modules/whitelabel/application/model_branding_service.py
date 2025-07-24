"""
Model branding management service.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Union

from modules.whitelabel.domain.models import ModelBranding
from modules.whitelabel.domain.schemas import (
    ModelBrandingCreate,
    ModelBrandingUpdate,
    ModelBrandingResponse
)
from core.exceptions import NotFoundException, BadRequestException
from core.domain.models import ModelProfile


class ModelBrandingService:
    """Service for managing model branding options."""
    
    async def get_model_branding(
        self,
        model_id: UUID,
        db: AsyncSession
    ) -> Optional[ModelBrandingResponse]:
        """Get model branding configuration."""
        result = await db.execute(
            select(ModelBranding)
            .filter(ModelBranding.model_id == model_id)
        )
        branding = result.scalar_one_or_none()
        
        if not branding:
            return None
        
        return ModelBrandingResponse.from_orm(branding)
    
    async def create_model_branding(
        self,
        model_id: UUID,
        branding_data: ModelBrandingCreate,
        db: AsyncSession
    ) -> ModelBrandingResponse:
        """Create model branding configuration."""
        # Check if branding already exists
        existing = await self.get_model_branding(model_id, db)
        if existing:
            raise BadRequestException("Model branding already exists")
        
        # Verify model exists
        model_result = await db.execute(
            select(ModelProfile).filter(ModelProfile.id == model_id)
        )
        if not model_result.scalar_one_or_none():
            raise NotFoundException("Model not found")
        
        # Validate data
        await self._validate_branding_data(branding_data)
        
        # Create branding
        branding = ModelBranding(
            model_id=model_id,
            display_name=branding_data.display_name,
            bio=branding_data.bio,
            theme_override=branding_data.theme_override,
            use_agency_theme=branding_data.use_agency_theme,
            content_tags=branding_data.content_tags,
            links={k: str(v) for k, v in branding_data.links.items()} if branding_data.links else {},
            watermark_enabled=branding_data.watermark_enabled,
            watermark_text=branding_data.watermark_text,
            watermark_position=branding_data.watermark_position,
            watermark_opacity=branding_data.watermark_opacity,
            auto_welcome_message=branding_data.auto_welcome_message,
            tip_thank_you_message=branding_data.tip_thank_you_message
        )
        
        db.add(branding)
        await db.commit()
        await db.refresh(branding)
        
        return ModelBrandingResponse.from_orm(branding)
    
    async def update_model_branding(
        self,
        model_id: UUID,
        branding_update: ModelBrandingUpdate,
        db: AsyncSession
    ) -> ModelBrandingResponse:
        """Update model branding configuration."""
        result = await db.execute(
            select(ModelBranding)
            .filter(ModelBranding.model_id == model_id)
        )
        branding = result.scalar_one_or_none()
        
        if not branding:
            raise NotFoundException("Model branding not found")
        
        # Validate update data
        await self._validate_branding_data(branding_update, is_update=True)
        
        # Update fields
        update_data = branding_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "links" and value:
                setattr(branding, field, {k: str(v) for k, v in value.items()})
            else:
                setattr(branding, field, value)
        
        await db.commit()
        await db.refresh(branding)
        
        return ModelBrandingResponse.from_orm(branding)
    
    async def delete_model_branding(
        self,
        model_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete model branding configuration."""
        result = await db.execute(
            select(ModelBranding)
            .filter(ModelBranding.model_id == model_id)
        )
        branding = result.scalar_one_or_none()
        
        if not branding:
            raise NotFoundException("Model branding not found")
        
        await db.delete(branding)
        await db.commit()
        
        return True
    
    async def get_models_by_tag(
        self,
        agency_id: UUID,
        tag: str,
        db: AsyncSession
    ) -> List[ModelBrandingResponse]:
        """Get models by content tag."""
        # Join with ModelProfile to filter by agency
        query = select(ModelBranding).join(
            ModelProfile,
            ModelBranding.model_id == ModelProfile.id
        ).filter(
            ModelProfile.agency_id == agency_id,
            ModelBranding.content_tags.contains([tag])
        )
        
        result = await db.execute(query)
        brandings = result.scalars().all()
        
        return [ModelBrandingResponse.from_orm(branding) for branding in brandings]
    
    async def generate_watermark_preview(
        self,
        watermark_text: str,
        position: str,
        opacity: int
    ) -> Dict[str, Any]:
        """Generate a preview of watermark settings."""
        # This would generate an actual watermarked image in production
        # For now, return configuration
        return {
            "text": watermark_text,
            "position": position,
            "opacity": opacity,
            "css": {
                "position": "absolute",
                "opacity": opacity / 100,
                **self._get_position_styles(position),
                "font-family": "Arial, sans-serif",
                "font-size": "16px",
                "color": "rgba(255, 255, 255, 0.8)",
                "text-shadow": "1px 1px 2px rgba(0, 0, 0, 0.5)"
            }
        }
    
    def _get_position_styles(self, position: str) -> Dict[str, str]:
        """Get CSS styles for watermark position."""
        positions = {
            "top-left": {"top": "10px", "left": "10px"},
            "top-right": {"top": "10px", "right": "10px"},
            "bottom-left": {"bottom": "10px", "left": "10px"},
            "bottom-right": {"bottom": "10px", "right": "10px"}
        }
        return positions.get(position, positions["bottom-right"])
    
    async def _validate_branding_data(
        self,
        data: Union[ModelBrandingCreate, ModelBrandingUpdate],
        is_update: bool = False
    ):
        """Validate branding data."""
        # Validate watermark settings
        if hasattr(data, 'watermark_enabled') and data.watermark_enabled:
            if not is_update and not data.watermark_text:
                raise BadRequestException("Watermark text is required when watermark is enabled")
            
            if hasattr(data, 'watermark_position') and data.watermark_position:
                valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
                if data.watermark_position not in valid_positions:
                    raise BadRequestException(f"Invalid watermark position. Must be one of: {', '.join(valid_positions)}")
            
            if hasattr(data, 'watermark_opacity') and data.watermark_opacity is not None:
                if data.watermark_opacity < 0 or data.watermark_opacity > 100:
                    raise BadRequestException("Watermark opacity must be between 0 and 100")
        
        # Validate content tags
        if hasattr(data, 'content_tags') and data.content_tags:
            if len(data.content_tags) > 20:
                raise BadRequestException("Maximum 20 content tags allowed")
            
            for tag in data.content_tags:
                if len(tag) > 50:
                    raise BadRequestException("Content tag must be 50 characters or less")
        
        # Validate theme override
        if hasattr(data, 'theme_override') and data.theme_override:
            # Basic validation - ensure it's a valid color configuration
            if not isinstance(data.theme_override, dict):
                raise BadRequestException("Theme override must be a valid configuration object")