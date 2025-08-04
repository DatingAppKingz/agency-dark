"""
Enhanced Pydantic schemas with comprehensive validation.

This module provides validated schemas for all API endpoints,
ensuring data integrity and preventing security vulnerabilities.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID
from enum import Enum
import re

from .validators import (
    email_validator,
    username_validator,
    password_validator,
    url_validator,
    no_sql_injection_validator,
    no_xss_validator,
    validate_phone_number,
    validate_uuid,
    validate_pagination,
    sanitize_html
)


class StrictBaseModel(BaseModel):
    """Base model with strict validation and security features."""
    
    model_config = ConfigDict(
        # Forbid extra fields to prevent parameter pollution
        extra='forbid',
        # Validate on assignment
        validate_assignment=True,
        # Use enum values
        use_enum_values=True,
        # Validate default values
        validate_default=True,
        # Strip whitespace from strings
        str_strip_whitespace=True,
        # Limit string length by default
        str_max_length=1000,
    )


# User Management Schemas
class UserCreateSchema(StrictBaseModel):
    """Schema for user registration with comprehensive validation."""
    
    email: str = Field(
        ...,
        description="User's email address",
        example="user@example.com"
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Username (3-30 characters, alphanumeric with _ and -)",
        example="john_doe"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (8+ chars, must include uppercase, lowercase, number, and special char)",
        example="SecurePass123!"
    )
    full_name: Optional[str] = Field(
        None,
        max_length=100,
        description="User's full name",
        example="John Doe"
    )
    phone: Optional[str] = Field(
        None,
        description="Phone number in international format",
        example="+1234567890"
    )
    agency_id: Optional[UUID] = Field(
        None,
        description="Agency ID to associate user with"
    )
    
    @field_validator('email')
    def validate_email(cls, v):
        return email_validator(v)
    
    @field_validator('username')
    def validate_username(cls, v):
        return username_validator(v)
    
    @field_validator('password')
    def validate_password(cls, v, info):
        return password_validator(v, info)
    
    @field_validator('full_name')
    def validate_full_name(cls, v):
        if v:
            return no_xss_validator(v, {'field_name': 'full_name'})
        return v
    
    @field_validator('phone')
    def validate_phone(cls, v):
        if v:
            return validate_phone_number(v)
        return v


class UserUpdateSchema(StrictBaseModel):
    """Schema for user profile updates."""
    
    email: Optional[str] = Field(None, description="New email address")
    full_name: Optional[str] = Field(None, max_length=100, description="New full name")
    phone: Optional[str] = Field(None, description="New phone number")
    
    @field_validator('email')
    def validate_email(cls, v):
        if v:
            return email_validator(v)
        return v
    
    @field_validator('full_name')
    def validate_full_name(cls, v):
        if v:
            return no_xss_validator(v, {'field_name': 'full_name'})
        return v
    
    @field_validator('phone')
    def validate_phone(cls, v):
        if v:
            return validate_phone_number(v)
        return v


class PasswordChangeSchema(StrictBaseModel):
    """Schema for password change requests."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_password: str = Field(..., description="Confirm new password")
    
    @field_validator('new_password')
    def validate_new_password(cls, v, info):
        return password_validator(v, info)
    
    @model_validator(mode='after')
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self


# Content Management Schemas
class ContentCreateSchema(StrictBaseModel):
    """Schema for creating content with XSS prevention."""
    
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Content title"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Content description"
    )
    body: str = Field(
        ...,
        description="Content body (HTML allowed but sanitized)"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_items=10,
        description="Content tags"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )
    
    @field_validator('title', 'description')
    def validate_text_fields(cls, v, info):
        if v:
            return no_xss_validator(v, info)
        return v
    
    @field_validator('body')
    def sanitize_body(cls, v):
        # Allow some HTML tags but sanitize
        return sanitize_html(v)
    
    @field_validator('tags')
    def validate_tags(cls, v):
        # Validate each tag
        validated_tags = []
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"Tag '{tag}' is too long (max 50 chars)")
            validated_tags.append(no_xss_validator(tag, {'field_name': 'tag'}))
        return validated_tags


# Search and Filter Schemas
class SearchQuerySchema(StrictBaseModel):
    """Schema for search queries with injection prevention."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Search query"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Search filters"
    )
    sort_by: Optional[str] = Field(
        None,
        pattern=r'^[a-zA-Z_]+$',
        description="Field to sort by"
    )
    sort_order: Optional[str] = Field(
        'desc',
        pattern=r'^(asc|desc)$',
        description="Sort order"
    )
    
    @field_validator('query')
    def validate_query(cls, v):
        # Prevent SQL injection in search queries
        return no_sql_injection_validator(v, {'field_name': 'query'})
    
    @field_validator('filters')
    def validate_filters(cls, v):
        if v:
            # Validate filter keys and values
            for key, value in v.items():
                if not re.match(r'^[a-zA-Z_]+$', key):
                    raise ValueError(f"Invalid filter key: {key}")
                if isinstance(value, str):
                    no_sql_injection_validator(value, {'field_name': f'filter.{key}'})
        return v


class PaginationSchema(StrictBaseModel):
    """Schema for pagination parameters."""
    
    page: int = Field(1, ge=1, le=10000, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    
    @model_validator(mode='after')
    def validate_pagination(self):
        validate_pagination(self.page, self.limit)
        return self


# File Upload Schemas
class FileUploadSchema(StrictBaseModel):
    """Schema for file upload validation."""
    
    filename: str = Field(
        ...,
        max_length=255,
        description="Original filename"
    )
    content_type: str = Field(
        ...,
        pattern=r'^[a-zA-Z0-9][a-zA-Z0-9\/\-\+\.]+$',
        description="MIME type"
    )
    size: int = Field(
        ...,
        gt=0,
        le=10485760,  # 10MB limit
        description="File size in bytes"
    )
    
    @field_validator('filename')
    def validate_filename(cls, v):
        # Remove path traversal attempts
        v = v.replace('..', '').replace('/', '').replace('\\', '')
        
        # Check for dangerous extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
            '.vbs', '.js', '.jar', '.zip', '.rar'
        ]
        
        lower_filename = v.lower()
        for ext in dangerous_extensions:
            if lower_filename.endswith(ext):
                raise ValueError(f"File type {ext} is not allowed")
        
        return v
    
    @field_validator('content_type')
    def validate_content_type(cls, v):
        # Whitelist allowed content types
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'text/plain', 'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        if v not in allowed_types:
            raise ValueError(f"Content type {v} is not allowed")
        
        return v


# API Request Schemas
class WebhookPayloadSchema(StrictBaseModel):
    """Schema for webhook payloads with strict validation."""
    
    event_type: str = Field(
        ...,
        pattern=r'^[a-zA-Z][a-zA-Z0-9_\.]+$',
        max_length=50,
        description="Event type"
    )
    timestamp: datetime = Field(
        ...,
        description="Event timestamp"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Event data"
    )
    signature: Optional[str] = Field(
        None,
        description="Request signature for verification"
    )
    
    @field_validator('data')
    def validate_data(cls, v):
        # Limit data size
        import json
        data_str = json.dumps(v)
        if len(data_str) > 100000:  # 100KB limit
            raise ValueError("Webhook data too large")
        return v


# Financial Schemas
class TransactionSchema(StrictBaseModel):
    """Schema for financial transactions."""
    
    amount: float = Field(
        ...,
        gt=0,
        le=1000000,
        description="Transaction amount"
    )
    currency: str = Field(
        ...,
        pattern=r'^[A-Z]{3}$',
        description="ISO 4217 currency code"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Transaction description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional transaction data"
    )
    
    @field_validator('amount')
    def validate_amount(cls, v):
        # Ensure proper decimal places for currency
        if round(v, 2) != v:
            raise ValueError("Amount must have at most 2 decimal places")
        return v
    
    @field_validator('description')
    def validate_description(cls, v):
        if v:
            return no_xss_validator(v, {'field_name': 'description'})
        return v


# Date Range Schemas
class DateRangeSchema(StrictBaseModel):
    """Schema for date range queries."""
    
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    timezone: Optional[str] = Field(
        'UTC',
        pattern=r'^[A-Za-z]+/[A-Za-z_]+$',
        description="Timezone (e.g., America/New_York)"
    )
    
    @model_validator(mode='after')
    def validate_date_range(self):
        if self.start_date > self.end_date:
            raise ValueError("Start date must be before end date")
        
        # Limit range to 1 year
        delta = (self.end_date - self.start_date).days
        if delta > 365:
            raise ValueError("Date range must not exceed 365 days")
        
        return self


# Bulk Operation Schemas
class BulkOperationSchema(StrictBaseModel):
    """Schema for bulk operations with safety limits."""
    
    operation: str = Field(
        ...,
        pattern=r'^(create|update|delete)$',
        description="Operation type"
    )
    ids: List[UUID] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of IDs to operate on"
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Data for create/update operations"
    )
    
    @field_validator('ids')
    def validate_ids(cls, v):
        # Ensure all IDs are valid UUIDs
        for id_val in v:
            validate_uuid(str(id_val), 'id')
        return v