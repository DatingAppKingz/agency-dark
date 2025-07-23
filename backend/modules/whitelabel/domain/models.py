"""
White-label domain models for theming and customization.
"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey, Index, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from backend.core.database import Base


class ThemeMode(str, enum.Enum):
    """Available theme modes."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"  # Follow system preference


class LogoType(str, enum.Enum):
    """Types of logos."""
    AGENCY_LOGO = "agency_logo"
    AGENCY_ICON = "agency_icon"
    MODEL_LOGO = "model_logo"
    MODEL_BANNER = "model_banner"
    EMAIL_HEADER = "email_header"
    FAVICON = "favicon"


class EmailTemplateType(str, enum.Enum):
    """Types of email templates."""
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    INVOICE = "invoice"
    PAYOUT_CONFIRMATION = "payout_confirmation"
    NEW_SUBSCRIBER = "new_subscriber"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    CLAIM_NOTIFICATION = "claim_notification"
    REPORT_SUMMARY = "report_summary"


class ThemeConfiguration(Base):
    """Theme configuration for agencies."""
    __tablename__ = "theme_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), unique=True, nullable=False)
    
    # Theme mode
    default_mode = Column(String(10), default=ThemeMode.LIGHT)
    allow_user_preference = Column(Boolean, default=True)
    
    # Color scheme
    light_theme = Column(JSON, default=dict)  # Light theme colors
    dark_theme = Column(JSON, default=dict)   # Dark theme colors
    
    # Custom CSS
    custom_css = Column(Text)
    
    # Font settings
    font_family = Column(String(100), default="Inter, system-ui, sans-serif")
    font_size_base = Column(String(10), default="16px")
    
    # Layout preferences
    layout_config = Column(JSON, default=dict)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    __table_args__ = (
        Index('idx_theme_configuration_agency', 'agency_id'),
    )


class BrandingAsset(Base):
    """Branding assets (logos, images) for agencies and models."""
    __tablename__ = "branding_assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Owner (agency or model)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"))
    
    # Asset details
    asset_type = Column(String(50), nullable=False)  # LogoType enum
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size = Column(Integer)  # In bytes
    mime_type = Column(String(100))
    
    # Image metadata
    width = Column(Integer)
    height = Column(Integer)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Metadata
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    __table_args__ = (
        Index('idx_branding_asset_agency', 'agency_id'),
        Index('idx_branding_asset_model', 'model_id'),
        Index('idx_branding_asset_type', 'asset_type'),
        # Only one active asset per type per owner
        Index('idx_branding_asset_unique_active', 'agency_id', 'model_id', 'asset_type', 'is_active',
              unique=True, postgresql_where='is_active = true'),
    )


class AgencyProfile(Base):
    """Extended agency profile for white-label features."""
    __tablename__ = "agency_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), unique=True, nullable=False)
    
    # Display information
    display_name = Column(String(100))
    tagline = Column(String(200))
    description = Column(Text)
    
    # Contact information
    support_email = Column(String(255))
    support_phone = Column(String(50))
    website_url = Column(String(500))
    
    # Social media
    social_links = Column(JSON, default=dict)  # {platform: url}
    
    # Legal information
    legal_name = Column(String(200))
    tax_id = Column(String(50))
    address = Column(JSON)  # {street, city, state, zip, country}
    
    # Branding guidelines
    brand_guidelines = Column(Text)
    
    # Custom domain (future feature)
    custom_domain = Column(String(255))
    custom_domain_verified = Column(Boolean, default=False)
    
    # Email settings
    from_email_name = Column(String(100))
    from_email_address = Column(String(255))
    reply_to_email = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_agency_profile_agency', 'agency_id'),
    )


class ModelBranding(Base):
    """Model-specific branding options."""
    __tablename__ = "model_branding"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), unique=True, nullable=False)
    
    # Display preferences
    display_name = Column(String(100))
    bio = Column(Text)
    
    # Theme override
    theme_override = Column(JSON)  # Custom colors for this model
    use_agency_theme = Column(Boolean, default=True)
    
    # Content categories/tags
    content_tags = Column(JSON, default=list)
    
    # Links
    links = Column(JSON, default=dict)  # {platform: url}
    
    # Watermark settings
    watermark_enabled = Column(Boolean, default=False)
    watermark_text = Column(String(100))
    watermark_position = Column(String(20), default="bottom-right")
    watermark_opacity = Column(Integer, default=50)
    
    # Fan interaction preferences
    auto_welcome_message = Column(Text)
    tip_thank_you_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_model_branding_model', 'model_id'),
    )


class EmailTemplate(Base):
    """Customizable email templates."""
    __tablename__ = "email_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Template identification
    template_type = Column(String(50), nullable=False)  # EmailTemplateType enum
    language = Column(String(10), default="en")
    
    # Content
    subject = Column(String(200), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text)  # Plain text version
    
    # Variables used in template
    variables = Column(JSON, default=list)  # List of variable names
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Testing
    test_data = Column(JSON)  # Sample data for preview
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    __table_args__ = (
        Index('idx_email_template_agency', 'agency_id'),
        Index('idx_email_template_type', 'template_type'),
        Index('idx_email_template_language', 'language'),
        # Only one active template per type per language per agency
        Index('idx_email_template_unique_active', 'agency_id', 'template_type', 'language', 'is_active',
              unique=True, postgresql_where='is_active = true'),
    )


class ThemePreset(Base):
    """Pre-defined theme presets."""
    __tablename__ = "theme_presets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Preset details
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    preview_url = Column(String(500))
    
    # Theme data
    light_theme = Column(JSON, nullable=False)
    dark_theme = Column(JSON, nullable=False)
    
    # Categories
    category = Column(String(50))  # professional, playful, minimal, etc.
    tags = Column(JSON, default=list)
    
    # Usage
    is_premium = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    __table_args__ = (
        Index('idx_theme_preset_name', 'name'),
        Index('idx_theme_preset_category', 'category'),
    )