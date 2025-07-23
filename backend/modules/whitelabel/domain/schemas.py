"""
White-label domain schemas for API requests and responses.
"""
from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from .models import ThemeMode, LogoType, EmailTemplateType


# Theme schemas
class ThemeColors(BaseModel):
    """Theme color configuration."""
    # Primary colors
    primary: str = Field(..., regex="^#[0-9A-Fa-f]{6}$")
    primary_hover: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    primary_text: Optional[str] = Field("#FFFFFF", regex="^#[0-9A-Fa-f]{6}$")
    
    # Secondary colors
    secondary: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    secondary_hover: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    secondary_text: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    
    # Background colors
    background: str = Field(..., regex="^#[0-9A-Fa-f]{6}$")
    surface: str = Field(..., regex="^#[0-9A-Fa-f]{6}$")
    
    # Text colors
    text_primary: str = Field(..., regex="^#[0-9A-Fa-f]{6}$")
    text_secondary: str = Field(..., regex="^#[0-9A-Fa-f]{6}$")
    text_disabled: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    
    # Status colors
    success: Optional[str] = Field("#4CAF50", regex="^#[0-9A-Fa-f]{6}$")
    warning: Optional[str] = Field("#FF9800", regex="^#[0-9A-Fa-f]{6}$")
    error: Optional[str] = Field("#F44336", regex="^#[0-9A-Fa-f]{6}$")
    info: Optional[str] = Field("#2196F3", regex="^#[0-9A-Fa-f]{6}$")
    
    # Additional colors
    border: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    divider: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")
    shadow: Optional[str] = Field(None, regex="^#[0-9A-Fa-f]{6}$")


class ThemeConfigurationCreate(BaseModel):
    """Create theme configuration."""
    default_mode: ThemeMode = ThemeMode.LIGHT
    allow_user_preference: bool = True
    light_theme: ThemeColors
    dark_theme: ThemeColors
    custom_css: Optional[str] = None
    font_family: Optional[str] = "Inter, system-ui, sans-serif"
    font_size_base: Optional[str] = "16px"
    layout_config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ThemeConfigurationUpdate(BaseModel):
    """Update theme configuration."""
    default_mode: Optional[ThemeMode] = None
    allow_user_preference: Optional[bool] = None
    light_theme: Optional[ThemeColors] = None
    dark_theme: Optional[ThemeColors] = None
    custom_css: Optional[str] = None
    font_family: Optional[str] = None
    font_size_base: Optional[str] = None
    layout_config: Optional[Dict[str, Any]] = None


class ThemeConfigurationResponse(BaseModel):
    """Response for theme configuration."""
    id: str
    agency_id: str
    default_mode: ThemeMode
    allow_user_preference: bool
    light_theme: Dict[str, Any]
    dark_theme: Dict[str, Any]
    custom_css: Optional[str]
    font_family: str
    font_size_base: str
    layout_config: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Branding asset schemas
class BrandingAssetUpload(BaseModel):
    """Upload branding asset."""
    asset_type: LogoType
    file_name: str
    mime_type: str = Field(..., regex="^image/(jpeg|jpg|png|gif|svg\\+xml|webp)$")


class BrandingAssetResponse(BaseModel):
    """Response for branding asset."""
    id: str
    agency_id: Optional[str]
    model_id: Optional[str]
    asset_type: str
    file_name: str
    file_url: str
    file_size: Optional[int]
    mime_type: Optional[str]
    width: Optional[int]
    height: Optional[int]
    is_active: bool
    uploaded_at: datetime
    uploaded_by: str

    class Config:
        from_attributes = True


# Agency profile schemas
class SocialLinks(BaseModel):
    """Social media links."""
    twitter: Optional[HttpUrl] = None
    instagram: Optional[HttpUrl] = None
    tiktok: Optional[HttpUrl] = None
    youtube: Optional[HttpUrl] = None
    facebook: Optional[HttpUrl] = None
    linkedin: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None


class Address(BaseModel):
    """Physical address."""
    street: str
    city: str
    state: Optional[str] = None
    zip_code: str = Field(..., alias="zip")
    country: str = "US"


class AgencyProfileCreate(BaseModel):
    """Create agency profile."""
    display_name: str = Field(..., min_length=1, max_length=100)
    tagline: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    support_email: Optional[EmailStr] = None
    support_phone: Optional[str] = Field(None, regex="^\\+?[1-9]\\d{1,14}$")
    website_url: Optional[HttpUrl] = None
    social_links: Optional[SocialLinks] = None
    legal_name: Optional[str] = Field(None, max_length=200)
    tax_id: Optional[str] = Field(None, max_length=50)
    address: Optional[Address] = None
    from_email_name: Optional[str] = Field(None, max_length=100)
    from_email_address: Optional[EmailStr] = None
    reply_to_email: Optional[EmailStr] = None


class AgencyProfileUpdate(BaseModel):
    """Update agency profile."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    tagline: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    support_email: Optional[EmailStr] = None
    support_phone: Optional[str] = Field(None, regex="^\\+?[1-9]\\d{1,14}$")
    website_url: Optional[HttpUrl] = None
    social_links: Optional[SocialLinks] = None
    legal_name: Optional[str] = Field(None, max_length=200)
    tax_id: Optional[str] = Field(None, max_length=50)
    address: Optional[Address] = None
    from_email_name: Optional[str] = Field(None, max_length=100)
    from_email_address: Optional[EmailStr] = None
    reply_to_email: Optional[EmailStr] = None
    brand_guidelines: Optional[str] = None


class AgencyProfileResponse(BaseModel):
    """Response for agency profile."""
    id: str
    agency_id: str
    display_name: Optional[str]
    tagline: Optional[str]
    description: Optional[str]
    support_email: Optional[str]
    support_phone: Optional[str]
    website_url: Optional[str]
    social_links: Dict[str, str]
    legal_name: Optional[str]
    tax_id: Optional[str]
    address: Optional[Dict[str, Any]]
    brand_guidelines: Optional[str]
    custom_domain: Optional[str]
    custom_domain_verified: bool
    from_email_name: Optional[str]
    from_email_address: Optional[str]
    reply_to_email: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Model branding schemas
class ModelBrandingCreate(BaseModel):
    """Create model branding."""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    theme_override: Optional[Dict[str, Any]] = None
    use_agency_theme: bool = True
    content_tags: Optional[List[str]] = Field(default_factory=list)
    links: Optional[Dict[str, HttpUrl]] = Field(default_factory=dict)
    watermark_enabled: bool = False
    watermark_text: Optional[str] = Field(None, max_length=100)
    watermark_position: Optional[str] = Field("bottom-right", regex="^(top|bottom)-(left|right)$")
    watermark_opacity: Optional[int] = Field(50, ge=0, le=100)
    auto_welcome_message: Optional[str] = None
    tip_thank_you_message: Optional[str] = None


class ModelBrandingUpdate(BaseModel):
    """Update model branding."""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    theme_override: Optional[Dict[str, Any]] = None
    use_agency_theme: Optional[bool] = None
    content_tags: Optional[List[str]] = None
    links: Optional[Dict[str, HttpUrl]] = None
    watermark_enabled: Optional[bool] = None
    watermark_text: Optional[str] = Field(None, max_length=100)
    watermark_position: Optional[str] = Field(None, regex="^(top|bottom)-(left|right)$")
    watermark_opacity: Optional[int] = Field(None, ge=0, le=100)
    auto_welcome_message: Optional[str] = None
    tip_thank_you_message: Optional[str] = None


class ModelBrandingResponse(BaseModel):
    """Response for model branding."""
    id: str
    model_id: str
    display_name: Optional[str]
    bio: Optional[str]
    theme_override: Optional[Dict[str, Any]]
    use_agency_theme: bool
    content_tags: List[str]
    links: Dict[str, str]
    watermark_enabled: bool
    watermark_text: Optional[str]
    watermark_position: str
    watermark_opacity: int
    auto_welcome_message: Optional[str]
    tip_thank_you_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Email template schemas
class EmailTemplateVariable(BaseModel):
    """Email template variable definition."""
    name: str
    description: str
    example: str
    required: bool = True


class EmailTemplateCreate(BaseModel):
    """Create email template."""
    template_type: EmailTemplateType
    language: str = Field("en", regex="^[a-z]{2}(-[A-Z]{2})?$")
    subject: str = Field(..., min_length=1, max_length=200)
    html_body: str
    text_body: Optional[str] = None
    variables: Optional[List[str]] = Field(default_factory=list)
    test_data: Optional[Dict[str, Any]] = None


class EmailTemplateUpdate(BaseModel):
    """Update email template."""
    subject: Optional[str] = Field(None, min_length=1, max_length=200)
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    variables: Optional[List[str]] = None
    test_data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """Response for email template."""
    id: str
    agency_id: str
    template_type: EmailTemplateType
    language: str
    subject: str
    html_body: str
    text_body: Optional[str]
    variables: List[str]
    is_active: bool
    is_default: bool
    test_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmailTemplatePreview(BaseModel):
    """Preview of rendered email template."""
    subject: str
    html_body: str
    text_body: Optional[str]
    warnings: List[str] = Field(default_factory=list)


# Theme preset schemas
class ThemePresetResponse(BaseModel):
    """Response for theme preset."""
    id: str
    name: str
    description: Optional[str]
    preview_url: Optional[str]
    light_theme: Dict[str, Any]
    dark_theme: Dict[str, Any]
    category: Optional[str]
    tags: List[str]
    is_premium: bool
    usage_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# White-label configuration response
class WhiteLabelConfig(BaseModel):
    """Complete white-label configuration for an agency."""
    theme: Optional[ThemeConfigurationResponse]
    profile: Optional[AgencyProfileResponse]
    logos: List[BrandingAssetResponse]
    email_templates: List[EmailTemplateResponse]