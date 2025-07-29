"""
Schema documentation and example generation
"""
from typing import Dict, Any, List, Optional, Type, Union
from pydantic import BaseModel, Field, create_model
from datetime import datetime, date
from decimal import Decimal
import json
from enum import Enum

from core.logging import logger


class ExampleGenerator:
    """Generate realistic examples for API schemas"""
    
    @staticmethod
    def generate_example(field_type: Type, field_name: str = "") -> Any:
        """Generate example value based on field type and name"""
        # Handle basic types
        type_examples = {
            str: "example_string",
            int: 123,
            float: 123.45,
            bool: True,
            bytes: b"example_bytes",
            date: date.today().isoformat(),
            datetime: datetime.now().isoformat(),
            Decimal: "123.45"
        }
        
        # Check direct type mapping
        if field_type in type_examples:
            return type_examples[field_type]
        
        # Handle common field names
        name_examples = {
            "email": "user@example.com",
            "username": "john_doe",
            "password": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+1234567890",
            "url": "https://example.com",
            "website": "https://example.com",
            "address": "123 Main St, City, Country",
            "city": "New York",
            "country": "United States",
            "postal_code": "10001",
            "zip_code": "10001",
            "description": "This is an example description",
            "title": "Example Title",
            "name": "Example Name",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "api_key": "sk_test_1234567890abcdef",
            "price": 99.99,
            "amount": 100.00,
            "quantity": 10,
            "count": 42,
            "total": 1000.00,
            "is_active": True,
            "is_verified": True,
            "is_deleted": False
        }
        
        # Check field name
        field_lower = field_name.lower()
        for key, value in name_examples.items():
            if key in field_lower:
                return value
        
        # Handle enums
        if hasattr(field_type, "__bases__") and Enum in field_type.__bases__:
            return list(field_type)[0].value
        
        # Handle lists
        if hasattr(field_type, "__origin__") and field_type.__origin__ == list:
            item_type = field_type.__args__[0] if field_type.__args__ else str
            return [ExampleGenerator.generate_example(item_type, field_name)]
        
        # Handle dicts
        if hasattr(field_type, "__origin__") and field_type.__origin__ == dict:
            return {"key": "value"}
        
        # Handle optional types
        if hasattr(field_type, "__origin__") and field_type.__origin__ == Union:
            # Get first non-None type
            for arg in field_type.__args__:
                if arg != type(None):
                    return ExampleGenerator.generate_example(arg, field_name)
        
        # Default
        return "example_value"


def create_example_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """
    Create example data for a Pydantic model
    
    Args:
        model: Pydantic model class
        
    Returns:
        Dictionary with example data
    """
    example = {}
    
    for field_name, field_info in model.__fields__.items():
        # Get field type
        field_type = field_info.type_
        
        # Check if field has example
        if hasattr(field_info, "example") and field_info.example is not None:
            example[field_name] = field_info.example
        elif hasattr(field_info, "default") and field_info.default is not None:
            example[field_name] = field_info.default
        else:
            # Generate example based on type
            example[field_name] = ExampleGenerator.generate_example(field_type, field_name)
    
    return example


def document_endpoint(
    summary: str,
    description: str = "",
    response_description: str = "Successful response",
    tags: List[str] = None,
    deprecated: bool = False,
    operation_id: Optional[str] = None,
    examples: Optional[Dict[str, Dict[str, Any]]] = None
):
    """
    Decorator to add comprehensive documentation to endpoints
    
    Args:
        summary: Short summary of the endpoint
        description: Detailed description with markdown support
        response_description: Description of successful response
        tags: List of tags for grouping
        deprecated: Whether endpoint is deprecated
        operation_id: Unique operation identifier
        examples: Request/response examples
    """
    def decorator(func):
        # Store documentation metadata
        func._api_summary = summary
        func._api_description = description
        func._api_response_description = response_description
        func._api_tags = tags or []
        func._api_deprecated = deprecated
        func._api_operation_id = operation_id
        func._api_examples = examples or {}
        
        return func
    
    return decorator


def add_response_examples(responses: Dict[int, Dict[str, Any]]):
    """
    Add response examples to endpoint documentation
    
    Args:
        responses: Dictionary mapping status codes to response info
        
    Example:
        @add_response_examples({
            200: {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "example": {"id": 1, "name": "John Doe"}
                    }
                }
            },
            404: {
                "description": "User not found",
                "content": {
                    "application/json": {
                        "example": {"detail": "User not found"}
                    }
                }
            }
        })
    """
    def decorator(func):
        func._api_responses = responses
        return func
    
    return decorator


class DocumentedModel(BaseModel):
    """Base model with automatic example generation"""
    
    class Config:
        schema_extra = {
            "example": None  # Will be populated automatically
        }
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # Generate example for schema
        if cls.Config.schema_extra.get("example") is None:
            cls.Config.schema_extra["example"] = create_example_schema(cls)


# Common response models with examples
class ErrorResponse(DocumentedModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class PaginationParams(DocumentedModel):
    """Standard pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field("asc", regex="^(asc|desc)$", description="Sort order")


class PaginatedResponse(DocumentedModel):
    """Standard paginated response"""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")
    limit: int = Field(..., description="Items per page")


class HealthResponse(DocumentedModel):
    """Health check response"""
    status: str = Field("healthy", description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")
    version: str = Field(..., description="API version")
    services: Dict[str, str] = Field(default_factory=dict, description="Sub-service health status")


class TokenResponse(DocumentedModel):
    """Authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(3600, description="Token expiration time in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token for token renewal")
    scope: Optional[str] = Field(None, description="Token permissions scope")


# API documentation templates
API_DESCRIPTION_TEMPLATE = """
## {title}

{description}

### Authentication

This endpoint requires {auth_type} authentication.

### Rate Limiting

- **Limit**: {rate_limit} requests per {rate_window}
- **Tier**: {tier_required}

### Request

{request_description}

### Response

{response_description}

### Error Codes

| Code | Description |
|------|-------------|
{error_codes}

### Examples

```bash
{curl_example}
```

### Notes

{additional_notes}
"""


def generate_endpoint_documentation(
    endpoint_info: Dict[str, Any],
    request_model: Optional[Type[BaseModel]] = None,
    response_model: Optional[Type[BaseModel]] = None
) -> str:
    """
    Generate comprehensive documentation for an endpoint
    
    Args:
        endpoint_info: Dictionary with endpoint information
        request_model: Request body model
        response_model: Response body model
        
    Returns:
        Formatted documentation string
    """
    # Generate request example
    request_example = {}
    if request_model:
        request_example = create_example_schema(request_model)
    
    # Generate response example
    response_example = {}
    if response_model:
        response_example = create_example_schema(response_model)
    
    # Generate curl example
    curl_example = f"""
curl -X {endpoint_info.get('method', 'GET')} \\
  {endpoint_info.get('url', 'https://api.agency.com/endpoint')} \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json"
"""
    
    if request_example and endpoint_info.get('method') in ['POST', 'PUT', 'PATCH']:
        curl_example += f"  -d '{json.dumps(request_example, indent=2)}'"
    
    # Format error codes
    error_codes = "\n".join([
        f"| {code} | {desc} |"
        for code, desc in endpoint_info.get('error_codes', {}).items()
    ])
    
    # Generate documentation
    doc = API_DESCRIPTION_TEMPLATE.format(
        title=endpoint_info.get('title', 'API Endpoint'),
        description=endpoint_info.get('description', ''),
        auth_type=endpoint_info.get('auth_type', 'Bearer token'),
        rate_limit=endpoint_info.get('rate_limit', '100'),
        rate_window=endpoint_info.get('rate_window', 'hour'),
        tier_required=endpoint_info.get('tier_required', 'Free'),
        request_description=endpoint_info.get('request_description', 'See request schema'),
        response_description=endpoint_info.get('response_description', 'See response schema'),
        error_codes=error_codes or "| 400 | Bad Request |\n| 401 | Unauthorized |\n| 500 | Internal Server Error |",
        curl_example=curl_example.strip(),
        additional_notes=endpoint_info.get('notes', 'None')
    )
    
    return doc


# Schema validation helpers
def validate_schema_examples(model: Type[BaseModel]) -> List[str]:
    """
    Validate that examples in a schema are valid
    
    Args:
        model: Pydantic model to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        # Get example from schema
        example = model.Config.schema_extra.get("example")
        if example:
            # Try to create instance with example data
            model(**example)
    except Exception as e:
        errors.append(f"Invalid example in {model.__name__}: {str(e)}")
    
    # Validate field examples
    for field_name, field_info in model.__fields__.items():
        if hasattr(field_info, "example") and field_info.example is not None:
            try:
                # Validate field example
                test_data = {field_name: field_info.example}
                # Add required fields with generated examples
                for req_field, req_info in model.__fields__.items():
                    if req_field != field_name and req_info.required:
                        test_data[req_field] = ExampleGenerator.generate_example(
                            req_info.type_, req_field
                        )
                model(**test_data)
            except Exception as e:
                errors.append(
                    f"Invalid example for {model.__name__}.{field_name}: {str(e)}"
                )
    
    return errors