"""
Enhanced input validation utilities using Pydantic.

This module provides comprehensive validation for all API inputs,
preventing injection attacks and ensuring data integrity.
"""

import re
from typing import Any, Optional, List, Dict
from pydantic import field_validator, ValidationInfo
from datetime import datetime, date
from uuid import UUID
import bleach
from urllib.parse import urlparse
import ipaddress

# Security patterns
SQL_INJECTION_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER|EXEC|EXECUTE|SCRIPT|JAVASCRIPT|EVAL)\b)",
    re.IGNORECASE
)

XSS_PATTERN = re.compile(
    r"(<script|<iframe|javascript:|onerror=|onload=|onclick=|<embed|<object)",
    re.IGNORECASE
)

# Email validation pattern (RFC 5322 compliant)
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
)

# Username validation pattern
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,30}$')

# Password complexity pattern
PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
)

# Phone number pattern (international format)
PHONE_PATTERN = re.compile(r'^\+?1?\d{9,15}$')

# URL validation
URL_SCHEMES = ['http', 'https']


class ValidationError(ValueError):
    """Custom validation error with field information."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def sanitize_html(value: str, allowed_tags: Optional[List[str]] = None) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    Args:
        value: HTML content to sanitize
        allowed_tags: List of allowed HTML tags
        
    Returns:
        Sanitized HTML string
    """
    if allowed_tags is None:
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li']
    
    allowed_attributes = {
        'a': ['href', 'title'],
    }
    
    return bleach.clean(
        value,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )


def validate_no_sql_injection(value: str, field_name: str = "field") -> str:
    """
    Validate that a string doesn't contain SQL injection patterns.
    
    Args:
        value: String to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If SQL injection pattern detected
    """
    if SQL_INJECTION_PATTERN.search(value):
        raise ValidationError(
            field_name,
            "Potential SQL injection detected"
        )
    return value


def validate_no_xss(value: str, field_name: str = "field") -> str:
    """
    Validate that a string doesn't contain XSS patterns.
    
    Args:
        value: String to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If XSS pattern detected
    """
    if XSS_PATTERN.search(value):
        raise ValidationError(
            field_name,
            "Potential XSS attack detected"
        )
    return value


def validate_email(email: str) -> str:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Validated email in lowercase
        
    Raises:
        ValidationError: If email format is invalid
    """
    email = email.strip().lower()
    
    if not EMAIL_PATTERN.match(email):
        raise ValidationError("email", "Invalid email format")
    
    # Additional validation
    if len(email) > 254:  # RFC 5321
        raise ValidationError("email", "Email address too long")
    
    # Check for common typos
    domain = email.split('@')[1]
    common_typos = {
        'gmial.com': 'gmail.com',
        'gmai.com': 'gmail.com',
        'yahooo.com': 'yahoo.com',
        'hotmial.com': 'hotmail.com',
    }
    
    if domain in common_typos:
        raise ValidationError(
            "email",
            f"Did you mean {email.replace(domain, common_typos[domain])}?"
        )
    
    return email


def validate_username(username: str) -> str:
    """
    Validate username format.
    
    Args:
        username: Username to validate
        
    Returns:
        Validated username
        
    Raises:
        ValidationError: If username format is invalid
    """
    username = username.strip()
    
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "username",
            "Username must be 3-30 characters and contain only letters, numbers, underscores, and hyphens"
        )
    
    # Check for reserved usernames
    reserved = ['admin', 'root', 'system', 'api', 'www', 'mail', 'ftp']
    if username.lower() in reserved:
        raise ValidationError("username", "This username is reserved")
    
    return username


def validate_password(password: str, username: Optional[str] = None, email: Optional[str] = None) -> str:
    """
    Validate password strength and complexity.
    
    Args:
        password: Password to validate
        username: Username to check password doesn't contain
        email: Email to check password doesn't contain
        
    Returns:
        Validated password
        
    Raises:
        ValidationError: If password doesn't meet requirements
    """
    # Check length
    if len(password) < 8:
        raise ValidationError("password", "Password must be at least 8 characters long")
    
    if len(password) > 128:
        raise ValidationError("password", "Password must not exceed 128 characters")
    
    # Check complexity
    if not re.search(r'[a-z]', password):
        raise ValidationError("password", "Password must contain at least one lowercase letter")
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError("password", "Password must contain at least one uppercase letter")
    
    if not re.search(r'\d', password):
        raise ValidationError("password", "Password must contain at least one number")
    
    if not re.search(r'[@$!%*?&]', password):
        raise ValidationError("password", "Password must contain at least one special character (@$!%*?&)")
    
    # Check for common passwords
    common_passwords = [
        'password123', 'admin123', 'qwerty123', 'letmein123',
        'welcome123', 'monkey123', '123456789', 'password1'
    ]
    
    if password.lower() in common_passwords:
        raise ValidationError("password", "This password is too common")
    
    # Check password doesn't contain username or email
    if username and username.lower() in password.lower():
        raise ValidationError("password", "Password must not contain your username")
    
    if email:
        email_prefix = email.split('@')[0]
        if email_prefix.lower() in password.lower():
            raise ValidationError("password", "Password must not contain your email")
    
    return password


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
    """
    Validate URL format and scheme.
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes
        
    Returns:
        Validated URL
        
    Raises:
        ValidationError: If URL is invalid
    """
    if allowed_schemes is None:
        allowed_schemes = URL_SCHEMES
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            raise ValidationError("url", "URL must include a scheme (http/https)")
        
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(
                "url",
                f"URL scheme must be one of: {', '.join(allowed_schemes)}"
            )
        
        if not parsed.netloc:
            raise ValidationError("url", "URL must include a domain")
        
        # Check for local/internal URLs
        if parsed.netloc in ['localhost', '127.0.0.1', '0.0.0.0']:
            raise ValidationError("url", "Local URLs are not allowed")
        
        # Check for IP addresses in production
        try:
            ipaddress.ip_address(parsed.netloc)
            raise ValidationError("url", "IP addresses are not allowed")
        except ValueError:
            # Not an IP address, which is good
            pass
        
        return url
        
    except Exception as e:
        raise ValidationError("url", f"Invalid URL format: {str(e)}")


def validate_phone_number(phone: str) -> str:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Validated phone number
        
    Raises:
        ValidationError: If phone number is invalid
    """
    # Remove common formatting characters
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if not PHONE_PATTERN.match(phone):
        raise ValidationError(
            "phone",
            "Invalid phone number format. Use international format: +1234567890"
        )
    
    return phone


def validate_uuid(value: str, field_name: str = "id") -> str:
    """
    Validate UUID format.
    
    Args:
        value: UUID string to validate
        field_name: Name of the field for error messages
        
    Returns:
        Validated UUID string
        
    Raises:
        ValidationError: If UUID is invalid
    """
    try:
        # This will raise ValueError if invalid
        UUID(value)
        return value
    except ValueError:
        raise ValidationError(field_name, "Invalid UUID format")


def validate_date_range(
    start_date: date,
    end_date: date,
    max_range_days: Optional[int] = None
) -> tuple[date, date]:
    """
    Validate date range.
    
    Args:
        start_date: Start date
        end_date: End date
        max_range_days: Maximum allowed range in days
        
    Returns:
        Validated date range tuple
        
    Raises:
        ValidationError: If date range is invalid
    """
    if start_date > end_date:
        raise ValidationError("date_range", "Start date must be before end date")
    
    if max_range_days:
        delta = (end_date - start_date).days
        if delta > max_range_days:
            raise ValidationError(
                "date_range",
                f"Date range must not exceed {max_range_days} days"
            )
    
    return start_date, end_date


def validate_pagination(page: int, limit: int, max_limit: int = 100) -> tuple[int, int]:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number (1-based)
        limit: Items per page
        max_limit: Maximum allowed items per page
        
    Returns:
        Validated (page, limit) tuple
        
    Raises:
        ValidationError: If pagination parameters are invalid
    """
    if page < 1:
        raise ValidationError("page", "Page number must be at least 1")
    
    if limit < 1:
        raise ValidationError("limit", "Limit must be at least 1")
    
    if limit > max_limit:
        raise ValidationError("limit", f"Limit must not exceed {max_limit}")
    
    return page, limit


def validate_json_field(
    value: Dict[str, Any],
    required_fields: Optional[List[str]] = None,
    max_size_kb: int = 100
) -> Dict[str, Any]:
    """
    Validate JSON field content.
    
    Args:
        value: JSON data to validate
        required_fields: List of required field names
        max_size_kb: Maximum size in kilobytes
        
    Returns:
        Validated JSON data
        
    Raises:
        ValidationError: If JSON data is invalid
    """
    # Check size
    import json
    json_str = json.dumps(value)
    size_kb = len(json_str.encode('utf-8')) / 1024
    
    if size_kb > max_size_kb:
        raise ValidationError(
            "json_field",
            f"JSON data exceeds maximum size of {max_size_kb}KB"
        )
    
    # Check required fields
    if required_fields:
        missing = [f for f in required_fields if f not in value]
        if missing:
            raise ValidationError(
                "json_field",
                f"Missing required fields: {', '.join(missing)}"
            )
    
    # Validate nested strings for XSS
    def check_nested_xss(obj: Any, path: str = "") -> None:
        if isinstance(obj, str):
            validate_no_xss(obj, f"json_field{path}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                check_nested_xss(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_nested_xss(v, f"{path}[{i}]")
    
    check_nested_xss(value)
    
    return value


# Pydantic field validators for common use cases
def email_validator(v: str) -> str:
    """Pydantic validator for email fields."""
    return validate_email(v)


def username_validator(v: str) -> str:
    """Pydantic validator for username fields."""
    return validate_username(v)


def password_validator(v: str, info: ValidationInfo) -> str:
    """Pydantic validator for password fields."""
    username = info.data.get('username')
    email = info.data.get('email')
    return validate_password(v, username, email)


def url_validator(v: str) -> str:
    """Pydantic validator for URL fields."""
    return validate_url(v)


def no_sql_injection_validator(v: str, info: ValidationInfo) -> str:
    """Pydantic validator to prevent SQL injection."""
    field_name = info.field_name or "field"
    return validate_no_sql_injection(v, field_name)


def no_xss_validator(v: str, info: ValidationInfo) -> str:
    """Pydantic validator to prevent XSS."""
    field_name = info.field_name or "field"
    return validate_no_xss(v, field_name)