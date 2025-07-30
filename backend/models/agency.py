from sqlalchemy import Column, String, Boolean, Integer, JSON, Numeric, Text
from sqlalchemy.orm import relationship
from models.base import Base, BaseModel


class Agency(BaseModel):
    """Agency model for multi-tenant support."""
    __tablename__ = "agencies"
    
    # Basic information
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    domain = Column(String(255), unique=True, nullable=True)  # Custom domain
    subdomain = Column(String(100), unique=True, nullable=True)  # subdomain.agencydark.com
    
    # Contact information
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    country = Column(String(2), nullable=True)  # ISO country code
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Branding
    logo_url = Column(String(500), nullable=True)
    favicon_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#3B82F6", nullable=False)  # Hex color
    secondary_color = Column(String(7), default="#1E40AF", nullable=False)
    
    # Settings
    settings = Column(JSON, default=dict, nullable=False)
    features = Column(JSON, default=dict, nullable=False)  # Enabled features
    
    # Commission settings
    default_commission_rate = Column(Numeric(5, 2), default=20.00, nullable=False)  # Percentage
    payment_frequency = Column(String(20), default="monthly", nullable=False)  # weekly, biweekly, monthly
    minimum_payout = Column(Numeric(10, 2), default=100.00, nullable=False)
    
    # Limits
    max_models = Column(Integer, default=100, nullable=False)
    max_chatters = Column(Integer, default=50, nullable=False)
    max_staff = Column(Integer, default=20, nullable=False)
    storage_quota_gb = Column(Integer, default=100, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    trial_ends_at = Column(String(30), nullable=True)  # ISO datetime string
    
    # Billing
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    billing_email = Column(String(255), nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="agency", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="agency", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="agency", cascade="all, delete-orphan")
    
    # Webhook configurations
    webhooks = relationship("Webhook", back_populates="agency", cascade="all, delete-orphan")
    
    # Financial relationships
    transactions = relationship("Transaction", back_populates="agency", cascade="all, delete-orphan")
    payouts = relationship("Payout", back_populates="agency", cascade="all, delete-orphan")
    
    # Content and chat
    content_templates = relationship("ContentTemplate", back_populates="agency", cascade="all, delete-orphan")
    chat_templates = relationship("ChatTemplate", back_populates="agency", cascade="all, delete-orphan")
    
    # Analytics
    metrics = relationship("AgencyMetrics", back_populates="agency", cascade="all, delete-orphan")
    
    # Invoices
    invoices = relationship("Invoice", back_populates="agency", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Agency {self.name}>"
    
    @property
    def domain_url(self):
        """Get the agency's full domain URL."""
        if self.domain:
            return f"https://{self.domain}"
        elif self.subdomain:
            return f"https://{self.subdomain}.agencydark.com"
        return None
    
    @property
    def branding(self):
        """Get branding configuration."""
        return {
            "logo_url": self.logo_url,
            "favicon_url": self.favicon_url,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "name": self.name
        }
    
    @property
    def is_on_trial(self):
        """Check if agency is on trial."""
        if not self.trial_ends_at:
            return False
        from datetime import datetime
        return datetime.fromisoformat(self.trial_ends_at) > datetime.utcnow()
    
    @property
    def has_custom_domain(self):
        """Check if agency has custom domain configured."""
        return bool(self.domain)
    
    def get_setting(self, key, default=None):
        """Get a specific setting value."""
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """Set a specific setting value."""
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value
    
    def is_feature_enabled(self, feature):
        """Check if a specific feature is enabled."""
        return self.features.get(feature, False)