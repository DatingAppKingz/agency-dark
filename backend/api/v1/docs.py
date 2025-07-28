"""
API documentation endpoints and examples.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

router = APIRouter(prefix="/docs", tags=["Documentation"])


class EndpointExample(BaseModel):
    """Example request/response for an endpoint."""
    title: str
    description: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    
    
class EndpointDocumentation(BaseModel):
    """Complete documentation for an endpoint."""
    path: str
    method: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]] = []
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Any] = {}
    examples: List[EndpointExample] = []
    

# Authentication Examples
AUTH_EXAMPLES = {
    "login": EndpointDocumentation(
        path="/api/v1/auth/login",
        method="POST",
        summary="User login",
        description="Authenticate user and receive JWT tokens",
        request_body={
            "schema": "LoginRequest",
            "required": True
        },
        responses={
            "200": {
                "description": "Successful login",
                "schema": "TokenResponse"
            },
            "401": {
                "description": "Invalid credentials"
            },
            "422": {
                "description": "Validation error"
            }
        },
        examples=[
            EndpointExample(
                title="Standard login",
                description="Login with email and password",
                request={
                    "email": "user@example.com",
                    "password": "SecurePass123!"
                },
                response={
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 3600
                }
            ),
            EndpointExample(
                title="Login with remember me",
                description="Extended session duration",
                request={
                    "email": "user@example.com",
                    "password": "SecurePass123!",
                    "remember_me": True
                },
                response={
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 604800  # 7 days
                }
            )
        ]
    ),
    "mfa": EndpointDocumentation(
        path="/api/v1/auth/verify-mfa",
        method="POST",
        summary="Verify MFA code",
        description="Complete authentication with MFA verification",
        request_body={
            "schema": "MFAVerifyRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="TOTP verification",
                description="Verify with TOTP code",
                request={
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "code": "123456",
                    "method": "totp"
                },
                response={
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer"
                }
            )
        ]
    )
}

# Analytics Examples
ANALYTICS_EXAMPLES = {
    "model_analytics": EndpointDocumentation(
        path="/api/v1/analytics/models/{model_id}",
        method="GET",
        summary="Get model analytics",
        description="Retrieve comprehensive analytics for a specific model",
        parameters=[
            {
                "name": "model_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"}
            },
            {
                "name": "date_from",
                "in": "query",
                "required": False,
                "schema": {"type": "string", "format": "date"}
            },
            {
                "name": "date_to",
                "in": "query",
                "required": False,
                "schema": {"type": "string", "format": "date"}
            }
        ],
        examples=[
            EndpointExample(
                title="Monthly analytics",
                description="Get analytics for the last month",
                request={},
                response={
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "period": {
                        "from": "2024-01-01",
                        "to": "2024-01-31"
                    },
                    "metrics": {
                        "revenue": {
                            "total": 15000.00,
                            "subscriptions": 8000.00,
                            "tips": 4000.00,
                            "ppv": 2000.00,
                            "messages": 1000.00,
                            "change_percent": 15.5
                        },
                        "fans": {
                            "total": 500,
                            "new": 150,
                            "churned": 50,
                            "active": 450,
                            "retention_rate": 90.0
                        },
                        "engagement": {
                            "messages_sent": 2000,
                            "messages_received": 1500,
                            "avg_response_time": 3.5,
                            "response_rate": 75.0
                        },
                        "content": {
                            "posts": 45,
                            "stories": 120,
                            "avg_likes": 250,
                            "avg_comments": 50
                        }
                    },
                    "top_fans": [
                        {
                            "fan_id": "456e7890-e89b-12d3-a456-426614174000",
                            "username": "bigspender123",
                            "total_spent": 2500.00,
                            "message_count": 150
                        }
                    ]
                }
            )
        ]
    ),
    "revenue_trends": EndpointDocumentation(
        path="/api/v1/analytics/revenue/trends",
        method="GET",
        summary="Get revenue trends",
        description="Analyze revenue trends over time with various groupings",
        parameters=[
            {
                "name": "model_id",
                "in": "query",
                "required": False,
                "schema": {"type": "string", "format": "uuid"}
            },
            {
                "name": "period",
                "in": "query",
                "required": False,
                "schema": {"type": "string", "enum": ["hourly", "daily", "weekly", "monthly"]}
            },
            {
                "name": "days",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "default": 30}
            }
        ],
        examples=[
            EndpointExample(
                title="Daily revenue trends",
                description="Get daily revenue for the last 30 days",
                request={},
                response={
                    "period": "daily",
                    "data": [
                        {
                            "date": "2024-01-01",
                            "revenue": {
                                "total": 500.00,
                                "subscriptions": 300.00,
                                "tips": 100.00,
                                "ppv": 75.00,
                                "messages": 25.00
                            },
                            "transactions": 25
                        },
                        {
                            "date": "2024-01-02",
                            "revenue": {
                                "total": 650.00,
                                "subscriptions": 350.00,
                                "tips": 150.00,
                                "ppv": 100.00,
                                "messages": 50.00
                            },
                            "transactions": 32
                        }
                    ],
                    "summary": {
                        "total_revenue": 15000.00,
                        "avg_daily_revenue": 500.00,
                        "best_day": {
                            "date": "2024-01-15",
                            "revenue": 1200.00
                        },
                        "growth_rate": 15.5
                    }
                }
            )
        ]
    )
}

# Messaging Examples
MESSAGING_EXAMPLES = {
    "bulk_message": EndpointDocumentation(
        path="/api/v1/messaging/bulk",
        method="POST",
        summary="Create bulk message campaign",
        description="Send personalized messages to multiple fans with advanced filtering",
        request_body={
            "schema": "BulkMessageCreate",
            "required": True
        },
        examples=[
            EndpointExample(
                title="VIP campaign with personalization",
                description="Target high-value fans with personalized offers",
                request={
                    "campaign_name": "VIP Weekend Special",
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "message_template": "Hey {{display_name}}! 🎉 As one of my top supporters (you've been amazing for {{months_subscribed}} months!), I have a special treat just for you: {{special_offer}}",
                    "recipient_filters": {
                        "subscription_status": ["active"],
                        "spent_min": 200,
                        "tags": ["vip"],
                        "last_activity_days": 7
                    },
                    "template_variables": {
                        "special_offer": "50% off all exclusive content this weekend only!"
                    },
                    "platform": "onlyfans",
                    "schedule_time": "2024-02-03T20:00:00Z",
                    "rate_limit": {
                        "messages_per_minute": 30,
                        "delay_between_messages": 2
                    }
                },
                response={
                    "campaign_id": "789e0123-e89b-12d3-a456-426614174000",
                    "campaign_name": "VIP Weekend Special",
                    "status": "scheduled",
                    "total_recipients": 150,
                    "estimated_cost": 0.00,
                    "scheduled_for": "2024-02-03T20:00:00Z",
                    "preview": {
                        "sample_message": "Hey John! 🎉 As one of my top supporters (you've been amazing for 6 months!), I have a special treat just for you: 50% off all exclusive content this weekend only!",
                        "variables_used": ["display_name", "months_subscribed", "special_offer"]
                    }
                }
            ),
            EndpointExample(
                title="Re-engagement campaign",
                description="Win back inactive fans",
                request={
                    "campaign_name": "We Miss You!",
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "message_template": "Hey {{display_name}}, I noticed you haven't been around lately 🥺 I miss chatting with you! Here's a special welcome back gift: {{promo_code}} for 30% off your next month!",
                    "recipient_filters": {
                        "subscription_status": ["expired", "cancelled"],
                        "last_activity_days_min": 30,
                        "last_activity_days_max": 90,
                        "total_spent_min": 50
                    },
                    "template_variables": {
                        "promo_code": "COMEBACK30"
                    },
                    "platform": "onlyfans"
                },
                response={
                    "campaign_id": "890e1234-e89b-12d3-a456-426614174000",
                    "campaign_name": "We Miss You!",
                    "status": "processing",
                    "total_recipients": 275,
                    "sent_count": 0,
                    "failed_count": 0,
                    "created_at": "2024-02-01T10:00:00Z"
                }
            )
        ]
    ),
    "ai_suggestions": EndpointDocumentation(
        path="/api/v1/messaging/ai/suggestions",
        method="POST",
        summary="Get AI response suggestions",
        description="Generate contextually appropriate response suggestions using AI",
        request_body={
            "schema": "AIResponseRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="Flirty response suggestions",
                description="AI suggestions for a compliment",
                request={
                    "message_content": "You look absolutely stunning in your latest post! 😍",
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "fan_id": "456e7890-e89b-12d3-a456-426614174000",
                    "conversation_context": [
                        {
                            "role": "fan",
                            "content": "Just subscribed! Can't wait to see more",
                            "timestamp": "2024-02-01T09:00:00Z"
                        },
                        {
                            "role": "model",
                            "content": "Welcome aboard! 💕 You're going to love what I have planned",
                            "timestamp": "2024-02-01T09:15:00Z"
                        }
                    ],
                    "fan_data": {
                        "subscription_tier": "vip",
                        "total_spent": 250.00,
                        "interaction_count": 15
                    },
                    "preferred_tone": "flirty",
                    "num_suggestions": 3
                },
                response={
                    "suggestions": [
                        {
                            "response": "Aww you're making me blush! 🥰 Wait until you see what I'm posting tonight... it's going to be even better 😉",
                            "confidence": 0.92,
                            "tone": "flirty",
                            "intent": "tease",
                            "follow_up_suggestions": [
                                "Want a sneak peek? 👀",
                                "I might need your help picking the outfit 😏"
                            ]
                        },
                        {
                            "response": "Thank you baby! 💋 You always know just what to say to make my day. That post was especially for my VIPs like you!",
                            "confidence": 0.88,
                            "tone": "appreciative",
                            "intent": "acknowledge_status"
                        },
                        {
                            "response": "You're too sweet! 😘 I put extra effort into that one... maybe I should do a behind-the-scenes video of the photoshoot? Would you like that?",
                            "confidence": 0.85,
                            "tone": "engaging",
                            "intent": "upsell"
                        }
                    ],
                    "sentiment_analysis": {
                        "score": 0.95,
                        "label": "very_positive",
                        "topics": ["appearance", "content appreciation"]
                    },
                    "recommended_actions": [
                        {
                            "action": "send_ppv",
                            "reason": "High engagement and positive sentiment"
                        },
                        {
                            "action": "add_tag",
                            "tag": "engaged_fan",
                            "reason": "Multiple positive interactions"
                        }
                    ]
                }
            )
        ]
    )
}

# Financial Examples
FINANCIAL_EXAMPLES = {
    "commission_calculation": EndpointDocumentation(
        path="/api/v1/financial/commissions/calculate",
        method="POST",
        summary="Calculate commission",
        description="Calculate commission based on tier and custom rules",
        request_body={
            "schema": "CommissionCalculateRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="Tiered commission calculation",
                description="Calculate commission with performance bonuses",
                request={
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "revenue_amount": 10000.00,
                    "revenue_type": "total",
                    "period": {
                        "from": "2024-01-01",
                        "to": "2024-01-31"
                    }
                },
                response={
                    "base_commission": {
                        "rate": 0.20,
                        "amount": 2000.00,
                        "tier": "standard"
                    },
                    "bonuses": [
                        {
                            "type": "performance",
                            "description": "Revenue target exceeded",
                            "amount": 500.00
                        },
                        {
                            "type": "retention",
                            "description": "90% fan retention rate",
                            "amount": 200.00
                        }
                    ],
                    "deductions": [],
                    "total_commission": 2700.00,
                    "net_payout": 7300.00,
                    "breakdown": {
                        "subscriptions": {
                            "revenue": 6000.00,
                            "commission": 1200.00
                        },
                        "tips": {
                            "revenue": 2500.00,
                            "commission": 500.00
                        },
                        "ppv": {
                            "revenue": 1000.00,
                            "commission": 200.00
                        },
                        "messages": {
                            "revenue": 500.00,
                            "commission": 100.00
                        }
                    }
                }
            )
        ]
    ),
    "payout_processing": EndpointDocumentation(
        path="/api/v1/financial/payouts",
        method="POST",
        summary="Process payout",
        description="Initiate payout to model or agency",
        request_body={
            "schema": "PayoutRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="Monthly model payout",
                description="Process monthly earnings payout",
                request={
                    "model_id": "123e4567-e89b-12d3-a456-426614174000",
                    "amount": 7300.00,
                    "currency": "USD",
                    "payment_method": "bank_transfer",
                    "bank_details": {
                        "account_number": "****1234",
                        "routing_number": "****5678",
                        "account_type": "checking"
                    },
                    "period": {
                        "from": "2024-01-01",
                        "to": "2024-01-31"
                    },
                    "notes": "January 2024 earnings",
                    "breakdown": {
                        "gross_revenue": 10000.00,
                        "agency_commission": 2000.00,
                        "bonuses": 700.00,
                        "deductions": 0.00,
                        "net_amount": 7300.00
                    }
                },
                response={
                    "payout_id": "pay_123e4567-e89b-12d3-a456",
                    "status": "processing",
                    "amount": 7300.00,
                    "currency": "USD",
                    "payment_method": "bank_transfer",
                    "estimated_arrival": "2024-02-05",
                    "reference_number": "PAYOUT-2024-01-001234",
                    "created_at": "2024-02-01T15:00:00Z",
                    "invoice_url": "https://api.agencydark.com/invoices/inv_123456.pdf"
                }
            )
        ]
    )
}

# Reporting Examples
REPORTING_EXAMPLES = {
    "custom_report": EndpointDocumentation(
        path="/api/v1/reporting/generate",
        method="POST",
        summary="Generate custom report",
        description="Generate a report from a custom template",
        request_body={
            "schema": "ReportGenerateRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="Comprehensive monthly report",
                description="Generate full monthly performance report",
                request={
                    "template_id": "tpl_123e4567-e89b-12d3-a456",
                    "parameters": {
                        "date_from": "2024-01-01",
                        "date_to": "2024-01-31",
                        "model_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                        "include_projections": True,
                        "compare_previous_period": True
                    },
                    "format": "pdf",
                    "delivery": {
                        "method": "email",
                        "recipients": ["reports@agency.com"]
                    }
                },
                response={
                    "report_id": "rpt_789e0123-e89b-12d3-a456",
                    "status": "generating",
                    "template_name": "Comprehensive Monthly Report",
                    "estimated_completion": "2024-02-01T10:05:00Z",
                    "format": "pdf",
                    "delivery_status": "pending",
                    "preview_data": {
                        "total_revenue": 45000.00,
                        "total_fans": 1500,
                        "top_performing_model": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "name": "ModelName",
                            "revenue": 15000.00
                        },
                        "period_comparison": {
                            "revenue_change": "+15.5%",
                            "fan_change": "+8.2%"
                        }
                    }
                }
            )
        ]
    ),
    "export_data": EndpointDocumentation(
        path="/api/v1/reporting/export",
        method="POST",
        summary="Export data",
        description="Export analytics data in various formats",
        request_body={
            "schema": "ExportRequest",
            "required": True
        },
        examples=[
            EndpointExample(
                title="Export fan data to Excel",
                description="Export detailed fan analytics with filters",
                request={
                    "export_type": "fans",
                    "format": "excel",
                    "filters": {
                        "model_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                        "date_from": "2024-01-01",
                        "date_to": "2024-01-31",
                        "subscription_status": ["active", "expired"],
                        "spent_min": 100,
                        "tags": ["vip", "high-value"]
                    },
                    "columns": [
                        "fan_id",
                        "username",
                        "display_name",
                        "subscription_status",
                        "total_spent",
                        "lifetime_value",
                        "message_count",
                        "last_activity",
                        "tags",
                        "subscription_date",
                        "churn_risk_score"
                    ],
                    "include_charts": True,
                    "group_by": "subscription_status"
                },
                response={
                    "export_id": "exp_456e7890-e89b-12d3-a456",
                    "status": "processing",
                    "format": "excel",
                    "estimated_size": "2.5 MB",
                    "record_count": 450,
                    "created_at": "2024-02-01T11:00:00Z",
                    "download_url": "https://api.agencydark.com/exports/exp_456e7890-e89b-12d3-a456/download",
                    "expires_at": "2024-02-08T11:00:00Z"
                }
            )
        ]
    )
}


@router.get("/examples", response_model=Dict[str, Any])
async def get_api_examples():
    """Get all API examples organized by category."""
    return {
        "authentication": AUTH_EXAMPLES,
        "analytics": ANALYTICS_EXAMPLES,
        "messaging": MESSAGING_EXAMPLES,
        "financial": FINANCIAL_EXAMPLES,
        "reporting": REPORTING_EXAMPLES
    }


@router.get("/examples/{category}", response_model=Dict[str, EndpointDocumentation])
async def get_category_examples(category: str):
    """Get examples for a specific API category."""
    categories = {
        "authentication": AUTH_EXAMPLES,
        "analytics": ANALYTICS_EXAMPLES,
        "messaging": MESSAGING_EXAMPLES,
        "financial": FINANCIAL_EXAMPLES,
        "reporting": REPORTING_EXAMPLES
    }
    
    if category not in categories:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category}' not found. Available categories: {list(categories.keys())}"
        )
    
    return categories[category]


@router.get("/postman-collection")
async def get_postman_collection():
    """Generate Postman collection for API testing."""
    return {
        "info": {
            "name": "AgencyDark API",
            "description": "Complete API collection for AgencyDark platform",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{access_token}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "base_url",
                "value": "https://api.agencydark.com",
                "type": "string"
            },
            {
                "key": "access_token",
                "value": "",
                "type": "string"
            }
        ],
        "item": [
            # Collection items would be generated here
        ]
    }


@router.get("/openapi-extensions")
async def get_openapi_extensions():
    """Get OpenAPI specification extensions for code generation."""
    return {
        "x-readme": {
            "explorer-enabled": True,
            "proxy-enabled": True,
            "samples-enabled": True,
            "samples-languages": ["python", "javascript", "curl", "go", "ruby", "php"]
        },
        "x-logo": {
            "url": "https://agencydark.com/logo.png",
            "altText": "AgencyDark Logo"
        },
        "x-code-samples": {
            "languages": ["python", "javascript", "curl"],
            "customTemplates": True
        }
    }