"""
Theme configuration service for white-label customization.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import json

from backend.modules.whitelabel.domain.models import (
    ThemeConfiguration,
    ThemePreset,
    ThemeMode
)
from backend.modules.whitelabel.domain.schemas import (
    ThemeConfigurationCreate,
    ThemeConfigurationUpdate,
    ThemeConfigurationResponse,
    ThemePresetResponse
)
from backend.core.exceptions import NotFoundException, BadRequestException
from backend.modules.auth.domain.models import Agency


class ThemeService:
    """Service for managing theme configurations."""
    
    async def get_agency_theme(
        self,
        agency_id: UUID,
        db: AsyncSession
    ) -> Optional[ThemeConfigurationResponse]:
        """Get theme configuration for an agency."""
        result = await db.execute(
            select(ThemeConfiguration)
            .filter(ThemeConfiguration.agency_id == agency_id)
        )
        theme = result.scalar_one_or_none()
        
        if not theme:
            return None
            
        return ThemeConfigurationResponse.from_orm(theme)
    
    async def create_agency_theme(
        self,
        agency_id: UUID,
        theme_data: ThemeConfigurationCreate,
        user_id: UUID,
        db: AsyncSession
    ) -> ThemeConfigurationResponse:
        """Create theme configuration for an agency."""
        # Check if theme already exists
        existing = await self.get_agency_theme(agency_id, db)
        if existing:
            raise BadRequestException("Theme configuration already exists for this agency")
        
        # Verify agency exists
        agency_result = await db.execute(
            select(Agency).filter(Agency.id == agency_id)
        )
        if not agency_result.scalar_one_or_none():
            raise NotFoundException("Agency not found")
        
        # Create theme configuration
        theme = ThemeConfiguration(
            agency_id=agency_id,
            default_mode=theme_data.default_mode,
            allow_user_preference=theme_data.allow_user_preference,
            light_theme=theme_data.light_theme.dict(),
            dark_theme=theme_data.dark_theme.dict(),
            custom_css=theme_data.custom_css,
            font_family=theme_data.font_family,
            font_size_base=theme_data.font_size_base,
            layout_config=theme_data.layout_config,
            updated_by=user_id
        )
        
        db.add(theme)
        await db.commit()
        await db.refresh(theme)
        
        return ThemeConfigurationResponse.from_orm(theme)
    
    async def update_agency_theme(
        self,
        agency_id: UUID,
        theme_update: ThemeConfigurationUpdate,
        user_id: UUID,
        db: AsyncSession
    ) -> ThemeConfigurationResponse:
        """Update theme configuration for an agency."""
        result = await db.execute(
            select(ThemeConfiguration)
            .filter(ThemeConfiguration.agency_id == agency_id)
        )
        theme = result.scalar_one_or_none()
        
        if not theme:
            raise NotFoundException("Theme configuration not found")
        
        # Update fields
        update_data = theme_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "light_theme" and value:
                setattr(theme, field, value.dict())
            elif field == "dark_theme" and value:
                setattr(theme, field, value.dict())
            else:
                setattr(theme, field, value)
        
        theme.updated_by = user_id
        
        await db.commit()
        await db.refresh(theme)
        
        return ThemeConfigurationResponse.from_orm(theme)
    
    async def delete_agency_theme(
        self,
        agency_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete theme configuration for an agency."""
        result = await db.execute(
            select(ThemeConfiguration)
            .filter(ThemeConfiguration.agency_id == agency_id)
        )
        theme = result.scalar_one_or_none()
        
        if not theme:
            raise NotFoundException("Theme configuration not found")
        
        await db.delete(theme)
        await db.commit()
        
        return True
    
    async def get_theme_presets(
        self,
        category: Optional[str] = None,
        is_premium: Optional[bool] = None,
        db: AsyncSession = None
    ) -> List[ThemePresetResponse]:
        """Get available theme presets."""
        query = select(ThemePreset).filter(ThemePreset.is_active == True)
        
        if category:
            query = query.filter(ThemePreset.category == category)
        
        if is_premium is not None:
            query = query.filter(ThemePreset.is_premium == is_premium)
        
        query = query.order_by(ThemePreset.usage_count.desc())
        
        result = await db.execute(query)
        presets = result.scalars().all()
        
        return [ThemePresetResponse.from_orm(preset) for preset in presets]
    
    async def apply_theme_preset(
        self,
        agency_id: UUID,
        preset_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> ThemeConfigurationResponse:
        """Apply a theme preset to an agency."""
        # Get preset
        preset_result = await db.execute(
            select(ThemePreset)
            .filter(and_(
                ThemePreset.id == preset_id,
                ThemePreset.is_active == True
            ))
        )
        preset = preset_result.scalar_one_or_none()
        
        if not preset:
            raise NotFoundException("Theme preset not found")
        
        # Check if theme exists
        theme_result = await db.execute(
            select(ThemeConfiguration)
            .filter(ThemeConfiguration.agency_id == agency_id)
        )
        theme = theme_result.scalar_one_or_none()
        
        if theme:
            # Update existing theme
            theme.light_theme = preset.light_theme
            theme.dark_theme = preset.dark_theme
            theme.updated_by = user_id
        else:
            # Create new theme
            theme = ThemeConfiguration(
                agency_id=agency_id,
                light_theme=preset.light_theme,
                dark_theme=preset.dark_theme,
                updated_by=user_id
            )
            db.add(theme)
        
        # Increment usage count
        preset.usage_count += 1
        
        await db.commit()
        await db.refresh(theme)
        
        return ThemeConfigurationResponse.from_orm(theme)
    
    async def preview_theme(
        self,
        theme_config: Dict[str, Any],
        mode: ThemeMode = ThemeMode.LIGHT
    ) -> Dict[str, Any]:
        """Generate a preview of theme configuration."""
        # This would generate CSS variables or a preview object
        # For now, return a structured preview
        colors = theme_config.get("light_theme" if mode == ThemeMode.LIGHT else "dark_theme", {})
        
        return {
            "mode": mode,
            "cssVariables": {
                "--primary": colors.get("primary", "#000000"),
                "--primary-hover": colors.get("primary_hover", "#333333"),
                "--primary-text": colors.get("primary_text", "#FFFFFF"),
                "--secondary": colors.get("secondary", "#666666"),
                "--background": colors.get("background", "#FFFFFF"),
                "--surface": colors.get("surface", "#F5F5F5"),
                "--text-primary": colors.get("text_primary", "#000000"),
                "--text-secondary": colors.get("text_secondary", "#666666"),
                "--success": colors.get("success", "#4CAF50"),
                "--warning": colors.get("warning", "#FF9800"),
                "--error": colors.get("error", "#F44336"),
                "--info": colors.get("info", "#2196F3"),
            },
            "preview": {
                "header": {
                    "background": colors.get("primary"),
                    "text": colors.get("primary_text")
                },
                "sidebar": {
                    "background": colors.get("surface"),
                    "text": colors.get("text_primary")
                },
                "content": {
                    "background": colors.get("background"),
                    "text": colors.get("text_primary")
                }
            }
        }