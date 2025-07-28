"""
OpenAPI/Swagger configuration and customization for AgencyDark API.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from typing import Dict, Any


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Custom OpenAPI schema generation with enhanced documentation.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AgencyDark API",
        version="1.0.0",
        description="""
        ## AgencyDark - White-label OnlyFans Marketing Agency Platform

        A comprehensive SaaS platform designed for marketing agencies managing OnlyFans creators.

        ### Key Features:
        - 🔐 **Unified Authentication** - JWT-based auth with MFA support
        - 📊 **Advanced Analytics** - Real-time metrics and insights
        - 💬 **Smart Messaging** - Bulk messaging, AI responses, and scheduling
        - 💰 **Financial Management** - Automated commission tracking and payouts
        - 📈 **Custom Reporting** - Build and schedule custom reports
        - 🔄 **Multi-platform Support** - OnlyFans, Fansly, and more

        ### Authentication
        All API endpoints require authentication using JWT tokens. Include the token in the Authorization header:
        ```
        Authorization: Bearer <your-token>
        ```

        ### Rate Limiting
        - Default: 100 requests per minute
        - Bulk operations: 10 requests per minute
        - WebSocket connections: 5 concurrent per user

        ### Pagination
        List endpoints support pagination using `skip` and `limit` parameters:
        - `skip`: Number of items to skip (default: 0)
        - `limit`: Maximum items to return (default: 20, max: 100)

        ### Error Responses
        All errors follow a consistent format:
        ```json
        {
            "detail": "Error message",
            "code": "ERROR_CODE",
            "field": "field_name" // Optional, for validation errors
        }
        ```

        ### Webhooks
        Register webhooks to receive real-time updates for:
        - New transactions
        - Fan subscriptions/unsubscriptions
        - Message events
        - Report generation completion

        ### API Versioning
        The API uses URL versioning. Current version: v1
        """,
        routes=app.routes,
        tags=[
            {
                "name": "Authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "Analytics",
                "description": "Analytics data and metrics endpoints"
            },
            {
                "name": "Messaging",
                "description": "Messaging, bulk campaigns, and AI responses"
            },
            {
                "name": "Financial",
                "description": "Transactions, commissions, and payouts"
            },
            {
                "name": "Reporting",
                "description": "Custom reports and scheduled reports"
            },
            {
                "name": "Models",
                "description": "OnlyFans model management"
            },
            {
                "name": "Fans",
                "description": "Fan management and segmentation"
            },
            {
                "name": "Agencies",
                "description": "Agency settings and management"
            },
            {
                "name": "Webhooks",
                "description": "Webhook management and configuration"
            }
        ],
        servers=[
            {
                "url": "https://api.agencydark.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.agencydark.com",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ],
        components={
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT token obtained from /api/v1/auth/login"
                },
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key for webhook endpoints"
                }
            }
        }
    )
    
    # Add security requirement to all endpoints
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    # Add additional examples and schemas
    add_request_examples(openapi_schema)
    add_response_examples(openapi_schema)
    add_webhook_schemas(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def add_request_examples(schema: Dict[str, Any]):
    """Add request examples to OpenAPI schema."""
    examples = {
        "BulkMessageCreate": {
            "summary": "Bulk message to active subscribers",
            "value": {
                "campaign_name": "Weekend Special",
                "model_id": "123e4567-e89b-12d3-a456-426614174000",
                "message_template": "Hey {{display_name}}! 🎉 Special weekend content just for you!",
                "recipient_filters": {
                    "subscription_status": ["active"],
                    "spent_min": 50,
                    "tags": ["vip"]
                },
                "platform": "onlyfans",
                "schedule_time": "2024-02-01T18:00:00Z"
            }
        },
        "ReportTemplateCreate": {
            "summary": "Monthly revenue report template",
            "value": {
                "name": "Monthly Revenue Analysis",
                "description": "Comprehensive monthly revenue breakdown with trends",
                "report_type": "revenue",
                "layout": {"columns": 2, "rows": 3},
                "widgets": [
                    {
                        "type": "metric",
                        "title": "Total Revenue",
                        "config": {
                            "metric_type": "revenue",
                            "show_comparison": True,
                            "comparison_period": "previous_month"
                        },
                        "size": "medium"
                    },
                    {
                        "type": "chart",
                        "title": "Daily Revenue Trend",
                        "config": {
                            "chart_type": "line",
                            "data_source": "revenue",
                            "group_by": "day"
                        },
                        "size": "large"
                    }
                ]
            }
        }
    }
    
    # Add examples to components
    if "components" not in schema:
        schema["components"] = {}
    if "examples" not in schema["components"]:
        schema["components"]["examples"] = examples


def add_response_examples(schema: Dict[str, Any]):
    """Add response examples to OpenAPI schema."""
    responses = {
        "UnauthorizedError": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated",
                        "code": "UNAUTHORIZED"
                    }
                }
            }
        },
        "NotFoundError": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Model not found",
                        "code": "NOT_FOUND"
                    }
                }
            }
        },
        "ValidationError": {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid email format",
                        "code": "VALIDATION_ERROR",
                        "field": "email"
                    }
                }
            }
        },
        "RateLimitError": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds.",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "retry_after": 60
                    }
                }
            }
        }
    }
    
    if "components" not in schema:
        schema["components"] = {}
    if "responses" not in schema["components"]:
        schema["components"]["responses"] = responses


def add_webhook_schemas(schema: Dict[str, Any]):
    """Add webhook payload schemas."""
    webhooks = {
        "transaction.created": {
            "post": {
                "requestBody": {
                    "description": "New transaction created",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "example": "transaction.created"},
                                    "timestamp": {"type": "string", "format": "date-time"},
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "transaction_id": {"type": "string", "format": "uuid"},
                                            "model_id": {"type": "string", "format": "uuid"},
                                            "fan_id": {"type": "string", "format": "uuid"},
                                            "amount": {"type": "number", "example": 49.99},
                                            "type": {"type": "string", "example": "tip"},
                                            "platform": {"type": "string", "example": "onlyfans"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "fan.subscribed": {
            "post": {
                "requestBody": {
                    "description": "Fan subscribed to model",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "example": "fan.subscribed"},
                                    "timestamp": {"type": "string", "format": "date-time"},
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "fan_id": {"type": "string", "format": "uuid"},
                                            "model_id": {"type": "string", "format": "uuid"},
                                            "subscription_price": {"type": "number", "example": 9.99},
                                            "platform": {"type": "string", "example": "onlyfans"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "report.completed": {
            "post": {
                "requestBody": {
                    "description": "Report generation completed",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "example": "report.completed"},
                                    "timestamp": {"type": "string", "format": "date-time"},
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "report_id": {"type": "string", "format": "uuid"},
                                            "template_name": {"type": "string", "example": "Monthly Revenue Report"},
                                            "status": {"type": "string", "example": "completed"},
                                            "download_url": {"type": "string", "format": "uri"},
                                            "expires_at": {"type": "string", "format": "date-time"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    if "webhooks" not in schema:
        schema["webhooks"] = webhooks


def setup_api_docs(app: FastAPI):
    """Setup custom API documentation endpoints."""
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_ui_parameters={
                "persistAuthorization": True,
                "displayRequestDuration": True,
                "docExpansion": "none",
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
                "displayOperationId": False,
                "defaultModelsExpandDepth": 2,
                "defaultModelExpandDepth": 2,
                "tryItOutEnabled": True
            }
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
            with_google_fonts=True
        )