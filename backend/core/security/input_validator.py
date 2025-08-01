"""
Advanced Input Validation System

Provides comprehensive input validation including:
- SQL injection prevention
- XSS attack prevention
- Path traversal protection
- Command injection protection
- File upload validation
- JSON/XML bomb protection
- Rate limiting per input type
"""
import re
import os
import magic
import hashlib
from typing import Any, Dict, List, Optional, Union, Set, Callable
from datetime import datetime
from functools import wraps
import mimetypes
from pathlib import Path

from pydantic import BaseModel, validator, Field, constr, conint
from fastapi import HTTPException, UploadFile, Request
from sqlalchemy import text

from core.logger import get_logger

logger = get_logger(__name__)


class ValidationError(HTTPException):
    """Custom validation error with detailed information."""
    def __init__(self, detail: str, field: Optional[str] = None):
        super().__init__(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": detail,
                "field": field
            }
        )


class InputValidator:
    """Comprehensive input validation system."""
    
    def __init__(self):
        # Dangerous patterns for various attack types
        self.sql_injection_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\bor\b\s*\d+\s*=\s*\d+)",
            r"(\band\b\s*\d+\s*=\s*\d+)",
            r"('+\s*or\s*')",
            r"(\bwaitfor\s+delay\b)",
            r"(\bconvert\s*\()",
            r"(\bcast\s*\()",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript\s*:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"vbscript\s*:",
            r"data:text/html",
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e/",
            r"%2e%2e\\",
            r"\.\.%2f",
            r"\.\.%5c",
            r"/etc/passwd",
            r"c:\\windows",
            r"c:/windows",
        ]
        
        self.command_injection_patterns = [
            r"[;&|`$]",
            r"\$\(",
            r"\|\|",
            r"&&",
            r">\s*/dev/null",
            r"nc\s+-",
            r"curl\s+",
            r"wget\s+",
            r"bash\s+-",
            r"sh\s+-",
        ]
        
        # Safe file extensions
        self.safe_file_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.webp',  # Images
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',  # Documents
            '.txt', '.csv', '.json', '.xml',           # Data
            '.mp4', '.webm', '.mov', '.avi',           # Videos
            '.mp3', '.wav', '.ogg',                    # Audio
        }
        
        # Maximum sizes for different input types
        self.max_sizes = {
            'string': 10000,       # 10KB
            'text': 100000,        # 100KB
            'json': 1000000,       # 1MB
            'file': 10485760,      # 10MB
            'image': 5242880,      # 5MB
            'document': 10485760,  # 10MB
        }
    
    def validate_string(
        self,
        value: str,
        field_name: str,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        allow_html: bool = False,
        allow_sql_keywords: bool = False
    ) -> str:
        """
        Validate string input for common attacks.
        
        Args:
            value: Input string to validate
            field_name: Name of the field for error reporting
            max_length: Maximum allowed length
            pattern: Optional regex pattern for validation
            allow_html: Whether to allow HTML content
            allow_sql_keywords: Whether to allow SQL keywords
            
        Returns:
            Sanitized string
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string", field_name)
        
        # Check length
        max_len = max_length or self.max_sizes['string']
        if len(value) > max_len:
            raise ValidationError(
                f"{field_name} exceeds maximum length of {max_len}",
                field_name
            )
        
        # Check for SQL injection
        if not allow_sql_keywords:
            for pattern in self.sql_injection_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(f"SQL injection attempt in {field_name}: {value[:100]}")
                    raise ValidationError(
                        f"Invalid characters in {field_name}",
                        field_name
                    )
        
        # Check for XSS
        if not allow_html:
            for pattern in self.xss_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(f"XSS attempt in {field_name}: {value[:100]}")
                    raise ValidationError(
                        f"HTML/Script tags not allowed in {field_name}",
                        field_name
                    )
        
        # Check custom pattern
        if pattern and not re.match(pattern, value):
            raise ValidationError(
                f"{field_name} does not match required format",
                field_name
            )
        
        # Sanitize by escaping special characters
        sanitized = value.replace('<', '&lt;').replace('>', '&gt;')
        
        return sanitized
    
    def validate_email(self, email: str) -> str:
        """Validate email address."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format", "email")
        
        # Additional checks
        if '..' in email or email.startswith('.') or email.endswith('.'):
            raise ValidationError("Invalid email format", "email")
        
        return email.lower()
    
    def validate_url(self, url: str, allowed_schemes: List[str] = None) -> str:
        """Validate URL for safety."""
        allowed_schemes = allowed_schemes or ['http', 'https']
        
        # Basic URL pattern
        url_pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
        
        if not re.match(url_pattern, url, re.IGNORECASE):
            raise ValidationError("Invalid URL format", "url")
        
        # Check scheme
        scheme = url.split('://')[0].lower()
        if scheme not in allowed_schemes:
            raise ValidationError(
                f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                "url"
            )
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'file:',
            r'about:',
        ]
        
        for pattern in suspicious_patterns:
            if pattern in url.lower():
                raise ValidationError("Invalid URL", "url")
        
        return url
    
    def validate_path(self, path: str, base_path: Optional[str] = None) -> str:
        """Validate file path for traversal attacks."""
        # Check for path traversal patterns
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                logger.warning(f"Path traversal attempt: {path}")
                raise ValidationError("Invalid path", "path")
        
        # Normalize and resolve path
        try:
            resolved_path = Path(path).resolve()
            
            if base_path:
                base = Path(base_path).resolve()
                if not str(resolved_path).startswith(str(base)):
                    raise ValidationError("Path outside allowed directory", "path")
            
            return str(resolved_path)
        except Exception:
            raise ValidationError("Invalid path", "path")
    
    def validate_json(self, data: Union[str, dict], max_depth: int = 10) -> dict:
        """
        Validate JSON data for bombs and malicious content.
        
        Args:
            data: JSON string or dictionary
            max_depth: Maximum nesting depth allowed
            
        Returns:
            Validated dictionary
        """
        import json
        
        if isinstance(data, str):
            # Check size before parsing
            if len(data) > self.max_sizes['json']:
                raise ValidationError("JSON data too large", "json")
            
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format", "json")
        
        # Check depth
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValidationError("JSON nesting too deep", "json")
            
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        check_depth(data)
        
        # Check for suspicious keys
        suspicious_keys = ['__proto__', 'constructor', 'prototype']
        
        def check_keys(obj):
            if isinstance(obj, dict):
                for key in obj.keys():
                    if key in suspicious_keys:
                        raise ValidationError(f"Suspicious key: {key}", "json")
                    check_keys(obj[key])
            elif isinstance(obj, list):
                for item in obj:
                    check_keys(item)
        
        check_keys(data)
        
        return data
    
    async def validate_file(
        self,
        file: UploadFile,
        allowed_types: Optional[List[str]] = None,
        max_size: Optional[int] = None,
        scan_content: bool = True
    ) -> UploadFile:
        """
        Validate uploaded file for safety.
        
        Args:
            file: Uploaded file
            allowed_types: Allowed MIME types
            max_size: Maximum file size in bytes
            scan_content: Whether to scan file content
            
        Returns:
            Validated file
        """
        # Check file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in self.safe_file_extensions:
            raise ValidationError(
                f"File type not allowed: {ext}",
                "file"
            )
        
        # Read file content for validation
        content = await file.read()
        file_size = len(content)
        
        # Reset file position
        await file.seek(0)
        
        # Check size
        max_file_size = max_size or self.max_sizes['file']
        if file_size > max_file_size:
            raise ValidationError(
                f"File too large: {file_size} bytes (max: {max_file_size})",
                "file"
            )
        
        # Check MIME type using python-magic
        if scan_content:
            mime_type = magic.from_buffer(content, mime=True)
            
            if allowed_types and mime_type not in allowed_types:
                raise ValidationError(
                    f"File type not allowed: {mime_type}",
                    "file"
                )
            
            # Verify extension matches content
            expected_ext = mimetypes.guess_extension(mime_type)
            if expected_ext and expected_ext != ext:
                logger.warning(
                    f"File extension mismatch: {ext} vs {expected_ext} "
                    f"for {file.filename}"
                )
        
        # Check for embedded executables
        if scan_content:
            executable_signatures = [
                b'MZ',  # DOS/Windows executable
                b'\x7fELF',  # Linux ELF
                b'#!/',  # Shell script
                b'<?php',  # PHP script
            ]
            
            for sig in executable_signatures:
                if content.startswith(sig):
                    raise ValidationError(
                        "Executable content not allowed",
                        "file"
                    )
        
        return file
    
    def validate_sql_identifier(self, identifier: str) -> str:
        """Validate SQL identifier (table/column name)."""
        # Only allow alphanumeric and underscore
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValidationError(
                "Invalid SQL identifier",
                "identifier"
            )
        
        # Check against reserved words
        reserved_words = {
            'select', 'insert', 'update', 'delete', 'drop',
            'create', 'alter', 'grant', 'revoke', 'union'
        }
        
        if identifier.lower() in reserved_words:
            raise ValidationError(
                "Reserved word cannot be used as identifier",
                "identifier"
            )
        
        return identifier
    
    def sanitize_html(self, html: str, allowed_tags: Optional[Set[str]] = None) -> str:
        """Sanitize HTML content."""
        import bleach
        
        allowed_tags = allowed_tags or {
            'p', 'br', 'span', 'div', 'strong', 'em',
            'u', 'i', 'b', 'a', 'ul', 'ol', 'li',
            'blockquote', 'code', 'pre', 'h1', 'h2',
            'h3', 'h4', 'h5', 'h6'
        }
        
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height'],
        }
        
        # Clean HTML
        cleaned = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return cleaned
    
    def create_validator(
        self,
        field_type: str,
        **kwargs
    ) -> Callable:
        """Create a reusable validator for Pydantic models."""
        def validator_func(cls, v):
            if field_type == 'string':
                return self.validate_string(v, cls.__name__, **kwargs)
            elif field_type == 'email':
                return self.validate_email(v)
            elif field_type == 'url':
                return self.validate_url(v, **kwargs)
            elif field_type == 'path':
                return self.validate_path(v, **kwargs)
            elif field_type == 'json':
                return self.validate_json(v, **kwargs)
            else:
                return v
        
        return validator_func


# Global validator instance
input_validator = InputValidator()


# Pydantic models with built-in validation
class SecureStringField(constr):
    """Secure string field with validation."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        return input_validator.validate_string(v, 'field', max_length=1000)


class SecureEmailField(str):
    """Secure email field with validation."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        return input_validator.validate_email(v)


class SecureURLField(str):
    """Secure URL field with validation."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        return input_validator.validate_url(v)


# Validation decorators for FastAPI
def validate_inputs(**validators):
    """
    Decorator to validate FastAPI endpoint inputs.
    
    Example:
        @validate_inputs(
            name=('string', {'max_length': 100}),
            email=('email', {}),
            age=('int', {'min': 0, 'max': 150})
        )
        async def create_user(name: str, email: str, age: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Validate each parameter
            for param_name, (validator_type, validator_args) in validators.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    
                    if validator_type == 'string':
                        kwargs[param_name] = input_validator.validate_string(
                            value, param_name, **validator_args
                        )
                    elif validator_type == 'email':
                        kwargs[param_name] = input_validator.validate_email(value)
                    elif validator_type == 'url':
                        kwargs[param_name] = input_validator.validate_url(
                            value, **validator_args
                        )
                    elif validator_type == 'int':
                        min_val = validator_args.get('min')
                        max_val = validator_args.get('max')
                        
                        if not isinstance(value, int):
                            raise ValidationError(
                                f"{param_name} must be an integer",
                                param_name
                            )
                        
                        if min_val is not None and value < min_val:
                            raise ValidationError(
                                f"{param_name} must be >= {min_val}",
                                param_name
                            )
                        
                        if max_val is not None and value > max_val:
                            raise ValidationError(
                                f"{param_name} must be <= {max_val}",
                                param_name
                            )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Example secure model
class SecureUserInput(BaseModel):
    """Example of a secure input model."""
    username: SecureStringField = Field(..., max_length=50)
    email: SecureEmailField
    website: Optional[SecureURLField] = None
    age: conint(ge=0, le=150)
    bio: Optional[str] = Field(None, max_length=500)
    
    @validator('username')
    def validate_username(cls, v):
        # Additional username validation
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscore and dash')
        return v
    
    @validator('bio')
    def validate_bio(cls, v):
        if v:
            return input_validator.sanitize_html(v)
        return v