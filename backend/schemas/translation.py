"""Translation schemas for request/response validation."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Translation schemas
class TranslationBase(BaseModel):
    """Base translation schema."""
    key: str = Field(..., min_length=1, max_length=500, description="Translation key")
    language: str = Field(..., min_length=2, max_length=10, description="Language code")
    value: str = Field(..., description="Translation value")
    context: Optional[str] = Field(None, max_length=100, description="Translation context")


class TranslationCreate(TranslationBase):
    """Create translation request."""
    is_verified: bool = Field(False, description="Whether translation is verified")


class TranslationUpdate(BaseModel):
    """Update translation request."""
    value: Optional[str] = None
    context: Optional[str] = None
    is_verified: Optional[bool] = None


class TranslationResponse(TranslationBase):
    """Translation response."""
    id: str
    is_verified: bool
    verified_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TranslationBulkCreate(BaseModel):
    """Bulk create translations request."""
    translations: List[TranslationCreate]


# Model translation schemas
class ModelTranslationBase(BaseModel):
    """Base model translation schema."""
    model_name: str = Field(..., description="Model name")
    model_id: str = Field(..., description="Model ID")
    field_name: str = Field(..., description="Field name")
    language: str = Field(..., description="Language code")
    value: str = Field(..., description="Translation value")


class ModelTranslationCreate(ModelTranslationBase):
    """Create model translation request."""
    is_machine_translated: bool = Field(False, description="Whether machine translated")


class ModelTranslationResponse(ModelTranslationBase):
    """Model translation response."""
    id: str
    is_machine_translated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Language preference schemas
class LanguagePreferenceUpdate(BaseModel):
    """Update language preference request."""
    primary_language: Optional[str] = Field(None, min_length=2, max_length=10)
    fallback_languages: Optional[List[str]] = None
    auto_translate: Optional[bool] = None
    show_original: Optional[bool] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    number_format: Optional[str] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    timezone: Optional[str] = None


class LanguagePreferenceResponse(BaseModel):
    """Language preference response."""
    id: str
    user_id: str
    primary_language: str
    fallback_languages: Optional[List[str]]
    auto_translate: bool
    show_original: bool
    date_format: Optional[str]
    time_format: Optional[str]
    number_format: Optional[str]
    currency: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Translation request schemas
class TranslationRequestCreate(BaseModel):
    """Create translation request."""
    key: str = Field(..., description="Translation key")
    source_language: str = Field(..., description="Source language")
    target_language: str = Field(..., description="Target language")
    source_text: str = Field(..., description="Text to translate")
    context: Optional[str] = Field(None, description="Context for translation")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")


class TranslationRequestResponse(BaseModel):
    """Translation request response."""
    id: str
    key: str
    source_language: str
    target_language: str
    source_text: str
    context: Optional[str]
    status: str
    translated_text: Optional[str]
    translator_id: Optional[str]
    requested_by: str
    agency_id: str
    priority: str
    requested_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Language info
class LanguageInfo(BaseModel):
    """Language information."""
    code: str
    name: str
    native_name: str
    rtl: bool
    decimal_symbol: Optional[str] = "."
    thousands_separator: Optional[str] = ","
    currency_symbol: Optional[str] = "$"
    date_format: Optional[str] = "MMM d, y"
    time_format: Optional[str] = "h:mm:ss a"
    first_week_day: Optional[int] = 0


# Translation stats
class TranslationStats(BaseModel):
    """Translation statistics."""
    stats: Dict[str, Dict[str, Any]]
    total_keys: int
    total_translations: int
    languages_complete: List[str]
    languages_incomplete: List[str]


# Export/Import
class TranslationExport(BaseModel):
    """Translation export response."""
    language: str
    format: str
    translations: Optional[Dict[str, str]] = None
    content: Optional[str] = None
    count: int


class TranslationImport(BaseModel):
    """Translation import request."""
    language: str
    translations: Dict[str, str]
    verified: bool = False