"""Translation models for dynamic content."""

from sqlalchemy import Column, String, Text, JSON, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from core.database import Base


class Translation(Base):
    """Translation for dynamic content."""
    __tablename__ = "translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Key for translation
    key = Column(String(500), nullable=False, index=True)
    
    # Language
    language = Column(String(10), nullable=False, index=True)
    
    # Translation value
    value = Column(Text, nullable=False)
    
    # Context information
    context = Column(String(100), nullable=True)  # e.g., "menu", "button", "error"
    
    # Metadata
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('key', 'language', name='_key_language_uc'),
    )
    
    # Relationships
    verifier = relationship("User", foreign_keys=[verified_by])


class ModelTranslation(Base):
    """Translation for model fields."""
    __tablename__ = "model_translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Model information
    model_name = Column(String(100), nullable=False, index=True)
    model_id = Column(String(100), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    
    # Language
    language = Column(String(10), nullable=False, index=True)
    
    # Translation value
    value = Column(Text, nullable=False)
    
    # Metadata
    is_machine_translated = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('model_name', 'model_id', 'field_name', 'language', 
                        name='_model_field_language_uc'),
    )


class LanguagePreference(Base):
    """User language preferences."""
    __tablename__ = "language_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    
    # Primary language
    primary_language = Column(String(10), nullable=False, default="en")
    
    # Fallback languages (ordered list)
    fallback_languages = Column(JSON, nullable=True)  # e.g., ["es", "en"]
    
    # Preferences
    auto_translate = Column(Boolean, default=True, nullable=False)
    show_original = Column(Boolean, default=False, nullable=False)
    
    # Regional settings
    date_format = Column(String(50), nullable=True)
    time_format = Column(String(50), nullable=True)
    number_format = Column(String(50), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="language_preference")


class TranslationRequest(Base):
    """Request for translation."""
    __tablename__ = "translation_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # What needs translation
    key = Column(String(500), nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    source_text = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default="pending", nullable=False)  # pending, in_progress, completed, rejected
    
    # Translation
    translated_text = Column(Text, nullable=True)
    translator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Requester
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Priority
    priority = Column(String(20), default="normal", nullable=False)  # low, normal, high, urgent
    
    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    requester = relationship("User", foreign_keys=[requested_by])
    translator = relationship("User", foreign_keys=[translator_id])
    agency = relationship("Agency")