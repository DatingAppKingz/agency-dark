# Backend Polish 7: Documentation & API Specs

This module provides comprehensive API documentation and developer tools for the Agency Backend API.

## Features Implemented

### 1. OpenAPI/Swagger Documentation (`openapi.py`)
- Custom OpenAPI schema generation with enhanced documentation
- Automatic example generation from Pydantic models
- Request/response examples for all endpoints
- Webhook payload documentation
- Security scheme definitions (JWT, API Key)
- Multiple server configurations (production, staging, development)

### 2. API Versioning Strategy (`versioning.py`)
- URL-based versioning (/api/v1/, /api/v2/, etc.)
- Version deprecation and sunset dates
- Automatic version detection from URL, headers, or query params
- Version transformers for backward compatibility
- Versioned routers with automatic prefix management
- Version discovery endpoints

### 3. Schema Documentation (`schemas.py`)
- Automatic example generation for Pydantic models
- Field-level documentation with examples
- Common response models (Error, Pagination, Health)
- Schema validation helpers
- Documentation templates for endpoints

### 4. Developer Guides (`developer_guide.py`)
Generates comprehensive guides:
- **Quickstart Guide**: Getting started with the API
- **Authentication Guide**: All auth methods explained
- **Best Practices Guide**: Performance, security, and optimization tips
- **Webhook Integration Guide**: Setting up and handling webhooks

### 5. Client SDK Generator (`sdk_generator.py`)
Automatically generates SDKs for:
- **Python SDK**: Full-featured with async support
- **JavaScript/TypeScript SDK**: Type-safe with TypeScript definitions
- Includes error handling, pagination, authentication
- Ready for npm/pip publishing

### 6. Interactive API Explorer (`api_explorer.py`)
- Web-based API testing interface
- Request builder with authentication support
- Response viewer with syntax highlighting
- Request history and collections
- Export to curl/Postman

### 7. Enhanced Documentation Routes
- `/docs` - Swagger UI with custom configuration
- `/redoc` - ReDoc documentation
- `/api-explorer` - Interactive API testing tool
- `/api/v1/openapi.json` - OpenAPI spec (JSON)
- `/api/v1/openapi.yaml` - OpenAPI spec (YAML)
- `/api/v1/postman-collection.json` - Postman collection
- `/api/v1/sdk/generate` - Generate client SDKs

## Usage

### Generate Documentation
```python
from core.documentation import generate_api_docs

# Generate all documentation
docs = generate_api_docs(app, output_path=Path("docs"))
```

### Use Versioning
```python
from core.documentation import VersionedAPIRouter, APIVersion

# Create versioned router
v1_router = VersionedAPIRouter(version=APIVersion.V1)

@v1_router.get("/users")
@version_route(min_version=APIVersion.V1, deprecated_in=APIVersion.V2)
async def get_users_v1():
    return {"version": "v1", "users": []}
```

### Document Endpoints
```python
from core.documentation import document_endpoint, add_response_examples

@router.get("/users/{user_id}")
@document_endpoint(
    summary="Get user by ID",
    description="Retrieve detailed user information",
    tags=["users"],
    examples={
        "user_id": "123e4567-e89b-12d3-a456-426614174000"
    }
)
@add_response_examples({
    200: {
        "description": "User found",
        "content": {
            "application/json": {
                "example": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }
        }
    }
})
async def get_user(user_id: str):
    pass
```

### Generate SDKs
```python
from core.documentation import SDKGenerator

# Generate SDKs from OpenAPI spec
generator = SDKGenerator(openapi_spec)
sdks = generator.generate_all_sdks()
```

## API Documentation URLs

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Explorer**: http://localhost:8000/api-explorer
- **Developer Guides**: http://localhost:8000/docs/api/
- **OpenAPI Spec**: http://localhost:8000/api/v1/openapi.json

## Next Steps

With documentation complete, the next backend polish phases are:
- Backend Polish 8: Testing & Quality
- Backend Polish 9: DevOps & Deployment
- Backend Polish 10: Final Optimizations
- Backend Polish 11: Security Hardening
- Backend Polish 12: Production Readiness