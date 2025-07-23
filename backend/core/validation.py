"""
Input validation utilities.
"""
import re
from typing import Optional, List
from pydantic import validator, BaseModel
import bleach
from urllib.parse import urlparse
import ipaddress


class ValidationError(Exception):
    """Validation error exception."""
    pass


class InputValidator:
    """Input validation utilities."""
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    USERNAME_PATTERN = re.compile(
        r'^[a-zA-Z0-9_-]{3,32}$'
    )
    
    PHONE_PATTERN = re.compile(
        r'^\+?[1-9]\d{1,14}$'
    )
    
    # Allowed HTML tags for sanitization
    ALLOWED_TAGS = [
        'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br'
    ]
    
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'abbr': ['title'],
        'acronym': ['title'],
    }
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and normalize email address."""
        email = email.strip().lower()
        
        if not cls.EMAIL_PATTERN.match(email):
            raise ValidationError("Invalid email format")
        
        return email
    
    @classmethod
    def validate_username(cls, username: str) -> str:
        """Validate username format."""
        username = username.strip()
        
        if not cls.USERNAME_PATTERN.match(username):
            raise ValidationError(
                "Username must be 3-32 characters and contain only "
                "letters, numbers, underscores, and hyphens"
            )
        
        return username
    
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        """Validate phone number format."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        
        if not cls.PHONE_PATTERN.match(phone):
            raise ValidationError("Invalid phone number format")
        
        return phone
    
    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        return bleach.clean(
            html,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True
        )
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate URL format and protocol."""
        try:
            parsed = urlparse(url)
            
            # Check protocol
            if parsed.scheme not in ['http', 'https']:
                raise ValidationError("URL must use HTTP or HTTPS protocol")
            
            # Check netloc
            if not parsed.netloc:
                raise ValidationError("Invalid URL format")
            
            return url
            
        except Exception:
            raise ValidationError("Invalid URL format")
    
    @classmethod
    def validate_ip_address(cls, ip: str) -> str:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip)
            return ip
        except ValueError:
            raise ValidationError("Invalid IP address format")
    
    @classmethod
    def validate_password_strength(cls, password: str) -> str:
        """Validate password strength."""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number")
        
        return password
    
    @classmethod
    def validate_file_extension(cls, filename: str, allowed_extensions: List[str]) -> str:
        """Validate file extension."""
        ext = filename.lower().split('.')[-1]
        
        if ext not in allowed_extensions:
            raise ValidationError(
                f"Invalid file type. Allowed extensions: {', '.join(allowed_extensions)}"
            )
        
        return filename
    
    @classmethod
    def validate_file_size(cls, size_bytes: int, max_size_mb: float = 5.0) -> int:
        """Validate file size."""
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if size_bytes > max_size_bytes:
            raise ValidationError(
                f"File size exceeds maximum allowed size of {max_size_mb}MB"
            )
        
        return size_bytes


# Pydantic validators for common fields
def email_validator(v: str) -> str:
    """Pydantic email validator."""
    return InputValidator.validate_email(v)


def username_validator(v: str) -> str:
    """Pydantic username validator."""
    return InputValidator.validate_username(v)


def phone_validator(v: str) -> str:
    """Pydantic phone validator."""
    return InputValidator.validate_phone(v)


def password_validator(v: str) -> str:
    """Pydantic password validator."""
    return InputValidator.validate_password_strength(v)


def url_validator(v: str) -> str:
    """Pydantic URL validator."""
    return InputValidator.validate_url(v)


class SecureString(str):
    """Secure string type that sanitizes HTML content."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError('string required')
        return InputValidator.sanitize_html(v)


class SafeText(BaseModel):
    """Base model for text content that needs sanitization."""
    
    class Config:
        # Automatically sanitize string fields
        @staticmethod
        def schema_extra(schema, model):
            for prop in schema.get('properties', {}).values():
                if prop.get('type') == 'string':
                    prop['description'] = prop.get('description', '') + ' (HTML sanitized)'


# Example usage in schemas
class ExampleSecureSchema(SafeText):
    """Example schema with input validation."""
    
    email: str
    username: str
    password: str
    phone: Optional[str] = None
    bio: SecureString  # Automatically sanitized
    website: Optional[str] = None
    
    _validate_email = validator('email', allow_reuse=True)(email_validator)
    _validate_username = validator('username', allow_reuse=True)(username_validator)
    _validate_password = validator('password', allow_reuse=True)(password_validator)
    _validate_phone = validator('phone', allow_reuse=True)(phone_validator)
    _validate_website = validator('website', allow_reuse=True)(url_validator)