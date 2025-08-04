# Input Validation Implementation

## Overview

Comprehensive input validation has been implemented using Pydantic schemas and custom validators to prevent injection attacks, ensure data integrity, and maintain security standards.

## Security Features

### 1. SQL Injection Prevention
- Pattern matching for SQL keywords (SELECT, DROP, UNION, etc.)
- Parameterized queries enforcement
- Input sanitization for all database operations

### 2. XSS Prevention
- HTML tag stripping for user inputs
- Script tag detection and blocking
- Event handler attribute removal
- Safe HTML rendering with bleach library

### 3. Path Traversal Prevention
- URL path validation
- File path sanitization
- Directory traversal pattern blocking

### 4. Request Size Limits
- Maximum request body size: 10MB
- Field-specific length limits
- JSON depth validation

## Validation Components

### Core Validators (`core/validation/validators.py`)

#### Email Validation
```python
from core.validation import validate_email

email = validate_email("user@example.com")
# - RFC 5322 compliant
# - Typo detection (gmial.com → gmail.com)
# - Length limits (max 254 chars)
```

#### Password Validation
```python
from core.validation import validate_password

password = validate_password("SecurePass123!", username="john", email="john@example.com")
# - Minimum 8 characters
# - Must include: uppercase, lowercase, number, special char
# - Cannot contain username or email
# - Common password blacklist
```

#### Username Validation
```python
from core.validation import validate_username

username = validate_username("john_doe")
# - 3-30 characters
# - Alphanumeric with _ and -
# - Reserved username checking
```

#### URL Validation
```python
from core.validation import validate_url

url = validate_url("https://example.com/path")
# - Scheme validation (http/https)
# - No localhost/IP addresses
# - Proper domain format
```

### Enhanced Pydantic Schemas (`core/validation/schemas.py`)

#### StrictBaseModel
Base model with security defaults:
- `extra='forbid'` - No additional fields allowed
- `str_strip_whitespace=True` - Auto-strip whitespace
- `str_max_length=1000` - Default string length limit

#### User Registration Schema
```python
from core.validation import UserCreateSchema

class UserCreateSchema(StrictBaseModel):
    email: str  # Validated email
    username: str  # 3-30 chars, alphanumeric
    password: str  # Strong password required
    full_name: Optional[str]  # XSS protected
    phone: Optional[str]  # International format
```

#### Content Creation Schema
```python
from core.validation import ContentCreateSchema

class ContentCreateSchema(StrictBaseModel):
    title: str  # XSS protected
    body: str  # Sanitized HTML
    tags: List[str]  # Each tag validated
    metadata: Optional[Dict[str, Any]]  # Size limited
```

### Validation Middleware (`core/middleware/validation.py`)

Automatically validates all incoming requests:

1. **URL Validation**
   - Path traversal prevention
   - Suspicious pattern detection

2. **Header Validation**
   - SQL injection in headers
   - XSS in User-Agent, Referer
   - CRLF injection prevention

3. **Query Parameter Validation**
   - Parameter name validation
   - Value sanitization

4. **Request Body Validation**
   - JSON structure validation
   - Recursive string validation
   - Size limits enforcement

## Usage Examples

### In FastAPI Endpoints

```python
from fastapi import APIRouter, Depends
from core.validation import UserCreateSchema, ValidationError

router = APIRouter()

@router.post("/register")
async def register(user_data: UserCreateSchema):
    # user_data is automatically validated
    # All fields are sanitized and safe to use
    
    try:
        # Create user with validated data
        user = await create_user(
            email=user_data.email,
            username=user_data.username,
            password=user_data.password
        )
        return {"message": "User created", "id": user.id}
        
    except ValidationError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=422,
            detail={"field": e.field, "error": e.message}
        )
```

### Manual Validation

```python
from core.validation import (
    validate_email,
    validate_no_sql_injection,
    validate_no_xss
)

# Validate individual fields
try:
    email = validate_email(user_input.email)
    username = validate_no_sql_injection(user_input.username, "username")
    bio = validate_no_xss(user_input.bio, "bio")
except ValidationError as e:
    return {"error": f"{e.field}: {e.message}"}
```

### Custom Validators

```python
from pydantic import field_validator
from core.validation import StrictBaseModel, no_xss_validator

class CustomSchema(StrictBaseModel):
    custom_field: str
    
    @field_validator('custom_field')
    def validate_custom(cls, v):
        # Add custom validation logic
        if "forbidden" in v.lower():
            raise ValueError("Forbidden word detected")
        
        # Chain with XSS validation
        return no_xss_validator(v, {'field_name': 'custom_field'})
```

## Security Patterns Detected

### SQL Injection Patterns
- SELECT, INSERT, UPDATE, DELETE, DROP
- UNION, CREATE, ALTER, EXEC
- Comments: --, /*, */
- String concatenation attempts

### XSS Patterns
- `<script>`, `<iframe>`, `<embed>`, `<object>`
- Event handlers: onclick=, onerror=, onload=
- JavaScript URLs: javascript:
- Data URLs with scripts

### Path Traversal Patterns
- ../ and ..\
- URL encoded traversal
- Double encoding attempts
- Null byte injection

## Configuration

### Validation Settings

```python
# Maximum request size (10MB default)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# Allowed HTML tags for content
ALLOWED_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li']

# Password complexity requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True
```

## Testing

### Test Script
```bash
cd backend
python3 test_input_validation.py
```

### Manual Testing

1. **Test SQL Injection**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "test@test.com'; DROP TABLE users; --", "password": "Test123!"}'
   ```

2. **Test XSS**
   ```bash
   curl -X POST http://localhost:8000/api/v1/profile \
     -H "Content-Type: application/json" \
     -d '{"bio": "<script>alert(\"XSS\")</script>"}'
   ```

3. **Test Large Request**
   ```bash
   # Create large file
   dd if=/dev/zero bs=1M count=11 | base64 > large.txt
   
   # Send large request
   curl -X POST http://localhost:8000/api/v1/upload \
     -H "Content-Type: application/json" \
     -d "{\"data\": \"$(cat large.txt)\"}"
   ```

## Best Practices

1. **Always Use Validation Schemas**
   - Define Pydantic schemas for all endpoints
   - Inherit from StrictBaseModel
   - Add field-specific validators

2. **Sanitize User Content**
   - Use bleach for HTML content
   - Strip dangerous tags and attributes
   - Validate URLs and file paths

3. **Implement Length Limits**
   - Set appropriate max lengths for fields
   - Limit array/list sizes
   - Control JSON depth and size

4. **Log Validation Failures**
   - Track validation errors for security monitoring
   - Alert on repeated validation failures
   - Monitor for attack patterns

5. **Regular Updates**
   - Keep validation patterns updated
   - Add new attack patterns as discovered
   - Review and update blacklists

## Common Issues

### Validation Too Strict
- Review field requirements
- Add legitimate patterns to allowlists
- Provide clear error messages

### Performance Impact
- Cache compiled regex patterns
- Limit validation depth for nested data
- Use async validation where possible

### False Positives
- Refine regex patterns
- Add context-aware validation
- Implement bypass mechanisms for admins