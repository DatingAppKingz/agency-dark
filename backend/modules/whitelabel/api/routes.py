"""
White-label API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from core.dependencies import (
    get_current_active_user,
    get_db,
    RoleChecker
)
from core.domain.models import UserRole
from modules.whitelabel.application.theme_service import ThemeService
from modules.whitelabel.application.branding_service import BrandingService
from modules.whitelabel.application.email_template_service import EmailTemplateService
from modules.whitelabel.application.agency_profile_service import AgencyProfileService
from modules.whitelabel.application.model_branding_service import ModelBrandingService
from modules.whitelabel.domain.schemas import (
    # Theme schemas
    ThemeConfigurationCreate,
    ThemeConfigurationUpdate,
    ThemeConfigurationResponse,
    ThemePresetResponse,
    # Branding schemas
    BrandingAssetUpload,
    BrandingAssetResponse,
    # Agency profile schemas
    AgencyProfileCreate,
    AgencyProfileUpdate,
    AgencyProfileResponse,
    # Model branding schemas
    ModelBrandingCreate,
    ModelBrandingUpdate,
    ModelBrandingResponse,
    # Email template schemas
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailTemplatePreview,
    WhiteLabelConfig
)
from modules.whitelabel.domain.models import (
    LogoType,
    EmailTemplateType,
    ThemeMode
)

router = APIRouter(prefix="/whitelabel", tags=["whitelabel"])

# Service instances
theme_service = ThemeService()
branding_service = BrandingService()
email_template_service = EmailTemplateService()
agency_profile_service = AgencyProfileService()
model_branding_service = ModelBrandingService()

# Role checkers
agency_roles = RoleChecker([UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN])
model_roles = RoleChecker([UserRole.MODEL])
admin_roles = RoleChecker([UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN])


# Theme endpoints
@router.get("/theme", response_model=Optional[ThemeConfigurationResponse])
async def get_agency_theme(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get theme configuration for the current user's agency."""
    return await theme_service.get_agency_theme(current_user.agency_id, db)


@router.post("/theme", response_model=ThemeConfigurationResponse)
async def create_agency_theme(
    theme_data: ThemeConfigurationCreate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Create theme configuration for agency."""
    return await theme_service.create_agency_theme(
        current_user.agency_id,
        theme_data,
        current_user.id,
        db
    )


@router.put("/theme", response_model=ThemeConfigurationResponse)
async def update_agency_theme(
    theme_update: ThemeConfigurationUpdate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Update theme configuration for agency."""
    return await theme_service.update_agency_theme(
        current_user.agency_id,
        theme_update,
        current_user.id,
        db
    )


@router.delete("/theme")
async def delete_agency_theme(
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Delete theme configuration for agency."""
    return await theme_service.delete_agency_theme(current_user.agency_id, db)


@router.get("/theme/presets", response_model=List[ThemePresetResponse])
async def get_theme_presets(
    category: Optional[str] = None,
    is_premium: Optional[bool] = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available theme presets."""
    return await theme_service.get_theme_presets(category, is_premium, db)


@router.post("/theme/presets/{preset_id}/apply", response_model=ThemeConfigurationResponse)
async def apply_theme_preset(
    preset_id: UUID,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Apply a theme preset to agency."""
    return await theme_service.apply_theme_preset(
        current_user.agency_id,
        preset_id,
        current_user.id,
        db
    )


@router.post("/theme/preview")
async def preview_theme(
    theme_config: dict,
    mode: ThemeMode = ThemeMode.LIGHT,
    current_user=Depends(get_current_active_user)
):
    """Preview theme configuration."""
    return await theme_service.preview_theme(theme_config, mode)


# Branding asset endpoints
@router.post("/assets", response_model=BrandingAssetResponse)
async def upload_branding_asset(
    file: UploadFile = File(...),
    asset_type: LogoType = Form(...),
    model_id: Optional[UUID] = Form(None),
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Upload a branding asset."""
    # Read file content
    content = await file.read()
    
    # Determine owner
    agency_id = current_user.agency_id if not model_id else None
    
    asset_data = BrandingAssetUpload(
        asset_type=asset_type,
        file_name=file.filename,
        mime_type=file.content_type
    )
    
    return await branding_service.upload_asset(
        content,
        asset_data,
        agency_id,
        model_id,
        current_user.id,
        db
    )


@router.get("/assets", response_model=List[BrandingAssetResponse])
async def get_branding_assets(
    asset_type: Optional[LogoType] = None,
    model_id: Optional[UUID] = None,
    active_only: bool = True,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get branding assets."""
    if model_id:
        return await branding_service.get_model_assets(
            model_id, asset_type, active_only, db
        )
    else:
        return await branding_service.get_agency_assets(
            current_user.agency_id, asset_type, active_only, db
        )


@router.get("/assets/{asset_id}", response_model=BrandingAssetResponse)
async def get_branding_asset(
    asset_id: UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific branding asset."""
    return await branding_service.get_asset(asset_id, db)


@router.put("/assets/{asset_id}/status")
async def update_asset_status(
    asset_id: UUID,
    is_active: bool,
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Update asset active status."""
    return await branding_service.update_asset_status(asset_id, is_active, db)


@router.delete("/assets/{asset_id}")
async def delete_branding_asset(
    asset_id: UUID,
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Delete a branding asset."""
    return await branding_service.delete_asset(asset_id, db)


# Agency profile endpoints
@router.get("/profile", response_model=Optional[AgencyProfileResponse])
async def get_agency_profile(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get agency profile."""
    return await agency_profile_service.get_agency_profile(
        current_user.agency_id, db
    )


@router.post("/profile", response_model=AgencyProfileResponse)
async def create_agency_profile(
    profile_data: AgencyProfileCreate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Create agency profile."""
    return await agency_profile_service.create_agency_profile(
        current_user.agency_id,
        profile_data,
        db
    )


@router.put("/profile", response_model=AgencyProfileResponse)
async def update_agency_profile(
    profile_update: AgencyProfileUpdate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Update agency profile."""
    return await agency_profile_service.update_agency_profile(
        current_user.agency_id,
        profile_update,
        db
    )


@router.delete("/profile")
async def delete_agency_profile(
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Delete agency profile."""
    return await agency_profile_service.delete_agency_profile(
        current_user.agency_id, db
    )


@router.post("/profile/domain/verify")
async def verify_custom_domain(
    domain: str,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Verify custom domain ownership."""
    return await agency_profile_service.verify_custom_domain(
        current_user.agency_id,
        domain,
        db
    )


# Model branding endpoints
@router.get("/models/{model_id}/branding", response_model=Optional[ModelBrandingResponse])
async def get_model_branding(
    model_id: UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get model branding configuration."""
    return await model_branding_service.get_model_branding(model_id, db)


@router.post("/models/{model_id}/branding", response_model=ModelBrandingResponse)
async def create_model_branding(
    model_id: UUID,
    branding_data: ModelBrandingCreate,
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Create model branding configuration."""
    return await model_branding_service.create_model_branding(
        model_id,
        branding_data,
        db
    )


@router.put("/models/{model_id}/branding", response_model=ModelBrandingResponse)
async def update_model_branding(
    model_id: UUID,
    branding_update: ModelBrandingUpdate,
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Update model branding configuration."""
    return await model_branding_service.update_model_branding(
        model_id,
        branding_update,
        db
    )


@router.delete("/models/{model_id}/branding")
async def delete_model_branding(
    model_id: UUID,
    current_user=Depends(admin_roles),
    db: AsyncSession = Depends(get_db)
):
    """Delete model branding configuration."""
    return await model_branding_service.delete_model_branding(model_id, db)


@router.get("/models/by-tag/{tag}", response_model=List[ModelBrandingResponse])
async def get_models_by_tag(
    tag: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get models by content tag."""
    return await model_branding_service.get_models_by_tag(
        current_user.agency_id,
        tag,
        db
    )


@router.post("/models/watermark/preview")
async def preview_watermark(
    watermark_text: str,
    position: str = "bottom-right",
    opacity: int = 50,
    current_user=Depends(get_current_active_user)
):
    """Preview watermark settings."""
    return await model_branding_service.generate_watermark_preview(
        watermark_text,
        position,
        opacity
    )


# Email template endpoints
@router.get("/emails/templates", response_model=List[EmailTemplateResponse])
async def get_email_templates(
    template_type: Optional[EmailTemplateType] = None,
    language: Optional[str] = None,
    active_only: bool = True,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get agency email templates."""
    return await email_template_service.get_agency_templates(
        current_user.agency_id,
        template_type,
        language,
        active_only,
        db
    )


@router.get("/emails/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: UUID,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific email template."""
    return await email_template_service.get_template(template_id, db)


@router.post("/emails/templates", response_model=EmailTemplateResponse)
async def create_email_template(
    template_data: EmailTemplateCreate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Create an email template."""
    return await email_template_service.create_template(
        current_user.agency_id,
        template_data,
        current_user.id,
        db
    )


@router.put("/emails/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: UUID,
    template_update: EmailTemplateUpdate,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Update an email template."""
    return await email_template_service.update_template(
        template_id,
        template_update,
        current_user.id,
        db
    )


@router.delete("/emails/templates/{template_id}")
async def delete_email_template(
    template_id: UUID,
    current_user=Depends(agency_roles),
    db: AsyncSession = Depends(get_db)
):
    """Delete an email template."""
    return await email_template_service.delete_template(template_id, db)


@router.post("/emails/templates/{template_id}/preview", response_model=EmailTemplatePreview)
async def preview_email_template(
    template_id: UUID,
    data: Optional[dict] = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Preview an email template with sample data."""
    return await email_template_service.preview_template(template_id, data or {}, db)


# Combined configuration endpoint
@router.get("/config", response_model=WhiteLabelConfig)
async def get_whitelabel_config(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete white-label configuration for agency."""
    agency_id = current_user.agency_id
    
    # Get all components
    theme = await theme_service.get_agency_theme(agency_id, db)
    profile = await agency_profile_service.get_agency_profile(agency_id, db)
    logos = await branding_service.get_agency_assets(agency_id, None, True, db)
    templates = await email_template_service.get_agency_templates(
        agency_id, None, None, True, db
    )
    
    return WhiteLabelConfig(
        theme=theme,
        profile=profile,
        logos=logos,
        email_templates=templates
    )