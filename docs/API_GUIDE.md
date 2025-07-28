# AgencyDark API Developer Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Webhooks](#webhooks)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Best Practices](#best-practices)
8. [Code Examples](#code-examples)

## Getting Started

### Base URLs
- Production: `https://api.agencydark.com`
- Staging: `https://staging-api.agencydark.com`
- Development: `http://localhost:8000`

### API Version
Current version: `v1`

All endpoints are prefixed with `/api/v1/`

### Content Type
All requests and responses use `application/json` unless otherwise specified.

## Authentication

### Login Flow

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "remember_me": true
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "display_name": "John Doe",
    "role": "admin"
  }
}
```

### Using Tokens

Include the access token in all authenticated requests:

```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Refreshing Tokens

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### MFA Flow

If MFA is enabled:

```bash
POST /api/v1/auth/verify-mfa
Content-Type: application/json

{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "code": "123456"
}
```

## API Endpoints

### Analytics

#### Get Model Analytics
```bash
GET /api/v1/analytics/models/{model_id}?date_from=2024-01-01&date_to=2024-01-31
```

Response:
```json
{
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
      "messages": 1000.00
    },
    "fans": {
      "total": 500,
      "new": 150,
      "churned": 50,
      "active": 450
    },
    "engagement": {
      "messages_sent": 2000,
      "messages_received": 1500,
      "avg_response_time": 3.5
    }
  }
}
```

#### Get Revenue Trends
```bash
GET /api/v1/analytics/revenue/trends?model_id={model_id}&period=daily&days=30
```

### Messaging

#### Create Bulk Message Campaign
```bash
POST /api/v1/messaging/bulk
Content-Type: application/json

{
  "campaign_name": "Weekend Special",
  "model_id": "123e4567-e89b-12d3-a456-426614174000",
  "message_template": "Hey {{display_name}}! Special offer: {{offer_details}}",
  "recipient_filters": {
    "subscription_status": ["active"],
    "spent_min": 100,
    "tags": ["vip", "high-value"]
  },
  "template_variables": {
    "offer_details": "50% off all PPV content this weekend!"
  },
  "platform": "onlyfans",
  "schedule_time": "2024-02-01T18:00:00Z"
}
```

#### Get AI Response Suggestions
```bash
POST /api/v1/messaging/ai/suggestions
Content-Type: application/json

{
  "message_content": "I love your content! When do you post new stuff?",
  "model_id": "123e4567-e89b-12d3-a456-426614174000",
  "fan_id": "456e7890-e89b-12d3-a456-426614174000",
  "conversation_context": [
    {
      "role": "fan",
      "content": "Hey beautiful!",
      "timestamp": "2024-01-31T10:00:00Z"
    },
    {
      "role": "model",
      "content": "Hi there! Thanks for subscribing 💕",
      "timestamp": "2024-01-31T10:05:00Z"
    }
  ]
}
```

Response:
```json
{
  "suggestions": [
    {
      "response": "Thank you so much! 🥰 I post new content every Monday, Wednesday, and Friday!",
      "confidence": 0.95,
      "tone": "friendly",
      "intent": "information"
    },
    {
      "response": "Aww thanks babe! 💕 New content drops 3x a week - you won't want to miss it!",
      "confidence": 0.88,
      "tone": "flirty",
      "intent": "information"
    }
  ],
  "sentiment_analysis": {
    "score": 0.8,
    "label": "positive"
  }
}
```

### Financial

#### Get Transaction Summary
```bash
GET /api/v1/financial/transactions/summary?model_id={model_id}&date_from=2024-01-01&date_to=2024-01-31
```

#### Process Payout
```bash
POST /api/v1/financial/payouts
Content-Type: application/json

{
  "model_id": "123e4567-e89b-12d3-a456-426614174000",
  "amount": 5000.00,
  "currency": "USD",
  "payment_method": "bank_transfer",
  "notes": "January 2024 earnings"
}
```

### Reporting

#### Create Custom Report Template
```bash
POST /api/v1/reporting/templates
Content-Type: application/json

{
  "name": "Weekly Performance Report",
  "description": "Comprehensive weekly performance metrics",
  "report_type": "comprehensive",
  "layout": {
    "columns": 2,
    "rows": 4
  },
  "widgets": [
    {
      "type": "metric",
      "title": "Total Revenue",
      "config": {
        "metric_type": "revenue",
        "show_comparison": true,
        "comparison_period": "previous_week"
      },
      "position": 0,
      "size": "medium"
    },
    {
      "type": "chart",
      "title": "Daily Revenue",
      "config": {
        "chart_type": "bar",
        "data_source": "revenue",
        "group_by": "day"
      },
      "position": 1,
      "size": "large"
    },
    {
      "type": "table",
      "title": "Top Fans",
      "config": {
        "table_type": "top_fans",
        "limit": 10,
        "sort_by": "total_spent"
      },
      "position": 2,
      "size": "medium"
    }
  ]
}
```

#### Schedule Report
```bash
POST /api/v1/reporting/schedules
Content-Type: application/json

{
  "name": "Weekly Revenue Report",
  "template_id": "789e0123-e89b-12d3-a456-426614174000",
  "schedule_type": "weekly",
  "timezone": "America/New_York",
  "parameters": {
    "date_range_type": "last_7_days",
    "model_id": "123e4567-e89b-12d3-a456-426614174000"
  },
  "delivery_method": "email",
  "delivery_config": {
    "recipients": ["reports@agency.com", "cfo@agency.com"]
  }
}
```

## Webhooks

### Registering a Webhook

```bash
POST /api/v1/webhooks
Content-Type: application/json

{
  "url": "https://your-app.com/webhooks/agencydark",
  "events": [
    "transaction.created",
    "fan.subscribed",
    "fan.unsubscribed",
    "message.received",
    "report.completed"
  ],
  "secret": "your-webhook-secret",
  "is_active": true
}
```

### Webhook Payload Structure

All webhook payloads follow this structure:

```json
{
  "event": "transaction.created",
  "timestamp": "2024-01-31T15:30:00Z",
  "webhook_id": "webhook_123",
  "data": {
    // Event-specific data
  }
}
```

### Verifying Webhook Signatures

Webhooks include a signature header for verification:

```
X-AgencyDark-Signature: sha256=abcdef123456...
```

Verify in your application:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## Error Handling

### Error Response Format

```json
{
  "detail": "Detailed error message",
  "code": "ERROR_CODE",
  "field": "field_name",  // For validation errors
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

## Rate Limiting

### Default Limits
- Standard endpoints: 100 requests/minute
- Analytics endpoints: 50 requests/minute
- Bulk operations: 10 requests/minute
- Export operations: 5 requests/minute

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706721600
```

### Handling Rate Limits

```python
import time
import requests

def make_request_with_retry(url, headers):
    response = requests.get(url, headers=headers)
    
    if response.status_code == 429:
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        wait_time = max(reset_time - time.time(), 1)
        time.sleep(wait_time)
        return make_request_with_retry(url, headers)
    
    return response
```

## Best Practices

### 1. Pagination

Always use pagination for list endpoints:

```bash
GET /api/v1/fans?skip=0&limit=50&sort_by=created_at&order=desc
```

### 2. Field Selection

Optimize responses by selecting only needed fields:

```bash
GET /api/v1/models/{id}?fields=id,username,display_name,metrics.revenue.total
```

### 3. Batch Operations

Use batch endpoints when available:

```bash
POST /api/v1/fans/batch
Content-Type: application/json

{
  "fan_ids": ["id1", "id2", "id3"],
  "operation": "tag",
  "data": {
    "tags": ["vip", "high-value"]
  }
}
```

### 4. Webhook Retry Logic

Implement exponential backoff for failed webhooks:

```python
import time

def process_webhook_with_retry(webhook_data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = send_to_webhook(webhook_data)
            if response.status_code == 200:
                return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    return False
```

### 5. Caching

Use ETags for caching:

```bash
GET /api/v1/analytics/models/{id}
If-None-Match: "123456789"

Response:
HTTP/1.1 304 Not Modified
ETag: "123456789"
```

## Code Examples

### Python SDK Example

```python
from agencydark import AgencyDarkClient
from datetime import datetime, timedelta

# Initialize client
client = AgencyDarkClient(
    api_key="your-api-key",
    base_url="https://api.agencydark.com"
)

# Get analytics
analytics = client.analytics.get_model_analytics(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    date_from=datetime.now() - timedelta(days=30),
    date_to=datetime.now()
)

# Send bulk message
campaign = client.messaging.create_bulk_campaign(
    campaign_name="Weekend Special",
    model_id="123e4567-e89b-12d3-a456-426614174000",
    message_template="Hey {{display_name}}! Check out my weekend special!",
    recipient_filters={
        "subscription_status": ["active"],
        "spent_min": 50
    }
)

# Generate report
report = client.reporting.generate_report(
    template_id="789e0123-e89b-12d3-a456-426614174000",
    format="pdf",
    parameters={
        "date_from": "2024-01-01",
        "date_to": "2024-01-31"
    }
)
```

### JavaScript/TypeScript Example

```typescript
import { AgencyDarkClient } from '@agencydark/sdk';

const client = new AgencyDarkClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.agencydark.com'
});

// Get AI response suggestions
const suggestions = await client.messaging.getAISuggestions({
  messageContent: "I love your content!",
  modelId: "123e4567-e89b-12d3-a456-426614174000",
  fanId: "456e7890-e89b-12d3-a456-426614174000"
});

// Create scheduled report
const schedule = await client.reporting.createSchedule({
  name: "Daily Revenue Report",
  templateId: "789e0123-e89b-12d3-a456-426614174000",
  scheduleType: "daily",
  deliveryMethod: "email",
  deliveryConfig: {
    recipients: ["reports@agency.com"]
  }
});
```

### cURL Examples

```bash
# Get fan analytics
curl -X GET "https://api.agencydark.com/api/v1/analytics/fans/segments" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"

# Export data
curl -X POST "https://api.agencydark.com/api/v1/reporting/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "revenue",
    "format": "excel",
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  }'
```

## Support

- Documentation: https://docs.agencydark.com
- API Status: https://status.agencydark.com
- Support Email: api-support@agencydark.com
- Developer Forum: https://forum.agencydark.com