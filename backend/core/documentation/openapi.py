"""
OpenAPI/Swagger documentation generation and customization
"""
from typing import Dict, Any, List, Optional, Callable
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
from pathlib import Path

from core.config import settings
from core.logging import logger


class OpenAPIConfig(BaseModel):
    """OpenAPI configuration"""
    title: str = "Agency Backend API"
    version: str = "1.0.0"
    description: str = """
    ## Agency Backend API Documentation
    
    This API provides comprehensive functionality for the Agency platform including:
    
    - **Authentication & Authorization**: JWT-based auth with role-based access control
    - **User Management**: User CRUD operations and profile management
    - **Content Management**: Create, read, update, and delete content
    - **Analytics**: Real-time and historical analytics data
    - **Machine Learning**: ML-powered insights and predictions
    - **Monitoring**: System health and performance metrics
    - **Reporting**: Advanced reporting and data export capabilities
    
    ### API Versioning
    
    The API uses URL-based versioning. The current version is `v1`.
    All endpoints are prefixed with `/api/v1/`.
    
    ### Authentication
    
    Most endpoints require authentication via JWT tokens. Include the token in the Authorization header:
    ```
    Authorization: Bearer <your-token>
    ```
    
    ### Rate Limiting
    
    API endpoints are rate-limited based on your subscription tier:
    - **Free**: 100 requests/hour
    - **Basic**: 1,000 requests/hour
    - **Pro**: 10,000 requests/hour
    - **Enterprise**: Unlimited
    
    ### Error Responses
    
    All errors follow a consistent format:
    ```json
    {
        "detail": "Error message",
        "status_code": 400,
        "error_code": "VALIDATION_ERROR",
        "timestamp": "2024-01-28T12:00:00Z"
    }
    ```
    """
    terms_of_service: str = "https://agency.com/terms"
    contact: Dict[str, str] = {
        "name": "Agency API Support",
        "url": "https://agency.com/support",
        "email": "api@agency.com"
    }
    license: Dict[str, str] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
    servers: List[Dict[str, str]] = [
        {
            "url": "https://api.agency.com",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.agency.com",
            "description": "Staging server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]
    tags: List[Dict[str, Any]] = [
        {
            "name": "auth",
            "description": "Authentication and authorization operations",
            "externalDocs": {
                "description": "Auth guide",
                "url": "https://docs.agency.com/auth"
            }
        },
        {
            "name": "users",
            "description": "User management operations"
        },
        {
            "name": "content",
            "description": "Content management operations"
        },
        {
            "name": "analytics",
            "description": "Analytics and reporting"
        },
        {
            "name": "ml",
            "description": "Machine learning insights"
        },
        {
            "name": "monitoring",
            "description": "System monitoring and health"
        },
        {
            "name": "admin",
            "description": "Administrative operations"
        }
    ]


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced documentation
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    config = OpenAPIConfig()
    
    openapi_schema = get_openapi(
        title=config.title,
        version=config.version,
        description=config.description,
        routes=app.routes,
        terms_of_service=config.terms_of_service,
        contact=config.contact,
        license_info=config.license,
        servers=config.servers,
        tags=config.tags
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token authentication"
        },
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    # Add additional response schemas
    openapi_schema["components"]["schemas"]["HTTPError"] = {
        "title": "HTTPError",
        "type": "object",
        "properties": {
            "detail": {"type": "string"},
            "status_code": {"type": "integer"},
            "error_code": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"}
        },
        "required": ["detail", "status_code"]
    }
    
    openapi_schema["components"]["schemas"]["ValidationError"] = {
        "title": "ValidationError",
        "type": "object",
        "properties": {
            "loc": {
                "type": "array",
                "items": {"type": "string"}
            },
            "msg": {"type": "string"},
            "type": {"type": "string"}
        },
        "required": ["loc", "msg", "type"]
    }
    
    # Add webhook definitions
    openapi_schema["webhooks"] = {
        "userCreated": {
            "post": {
                "requestBody": {
                    "description": "User creation notification",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Webhook processed successfully"}
                }
            }
        },
        "contentPublished": {
            "post": {
                "requestBody": {
                    "description": "Content publication notification",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Content"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Webhook processed successfully"}
                }
            }
        }
    }
    
    # Add x-logo extension
    openapi_schema["info"]["x-logo"] = {
        "url": "https://agency.com/logo.png",
        "altText": "Agency Logo"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def get_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Get the OpenAPI schema for the application"""
    return custom_openapi(app)


def add_api_route_tags(route: Any, tags: List[str]) -> None:
    """Add tags to API routes for better organization"""
    if hasattr(route, "tags"):
        route.tags.extend(tags)
    else:
        route.tags = tags


def generate_api_docs(app: FastAPI, output_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Generate API documentation in various formats
    
    Args:
        app: FastAPI application instance
        output_path: Optional path to save the documentation
        
    Returns:
        OpenAPI schema dictionary
    """
    schema = get_openapi_schema(app)
    
    if output_path:
        # Save as JSON
        json_path = output_path / "openapi.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(schema, f, indent=2)
        
        # Save as YAML
        try:
            import yaml
            yaml_path = output_path / "openapi.yaml"
            with open(yaml_path, "w") as f:
                yaml.dump(schema, f, default_flow_style=False)
        except ImportError:
            logger.warning("PyYAML not installed, skipping YAML export")
        
        # Generate HTML documentation
        html_path = output_path / "api-docs.html"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{schema['info']['title']} - API Documentation</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
                const spec = {json.dumps(schema)};
                SwaggerUIBundle({{
                    spec: spec,
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.SwaggerUIStandalonePreset
                    ],
                    layout: "BaseLayout"
                }});
            </script>
        </body>
        </html>
        """
        with open(html_path, "w") as f:
            f.write(html_content)
        
        logger.info(f"API documentation generated at: {output_path}")
    
    return schema


def setup_documentation_routes(app: FastAPI) -> None:
    """Setup documentation routes with custom UI"""
    
    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def custom_swagger_ui_html():
        """Custom Swagger UI with enhanced styling"""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
        )
    
    @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
    async def redoc_html():
        """ReDoc documentation with enhanced features"""
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
            with_google_fonts=True
        )
    
    @app.get("/api-docs/postman", include_in_schema=False)
    async def get_postman_collection():
        """Generate Postman collection from OpenAPI schema"""
        schema = get_openapi_schema(app)
        
        # Convert OpenAPI to Postman collection format
        postman_collection = {
            "info": {
                "name": schema["info"]["title"],
                "description": schema["info"]["description"],
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }
        
        # Convert paths to Postman requests
        for path, methods in schema.get("paths", {}).items():
            for method, operation in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    request = {
                        "name": operation.get("summary", path),
                        "request": {
                            "method": method.upper(),
                            "url": {
                                "raw": f"{{{{base_url}}}}{path}",
                                "host": ["{{base_url}}"],
                                "path": path.strip("/").split("/")
                            },
                            "description": operation.get("description", "")
                        }
                    }
                    
                    # Add headers
                    if "security" in operation:
                        request["request"]["header"] = [
                            {
                                "key": "Authorization",
                                "value": "Bearer {{access_token}}",
                                "type": "text"
                            }
                        ]
                    
                    postman_collection["item"].append(request)
        
        return postman_collection