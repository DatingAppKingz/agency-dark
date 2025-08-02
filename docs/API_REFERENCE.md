# AgencyDark API Documentation

## Overview

AgencyDark provides a RESTful API for managing OnlyFans marketing agencies. The API is built with FastAPI and supports both synchronous HTTP requests and real-time WebSocket connections.

## Base URL

```
Production: https://api.agencydark.com
Staging: https://staging-api.agencydark.com
Development: http://localhost:8000
```

## Authentication

AgencyDark uses JWT (JSON Web Token) authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Authentication Endpoints

#### Register User
```http
POST /api/v1/auth/register
```

Request body:
```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "SecurePass123",
  "role": "chatter",
  "agency_id": "uuid"
}
```

#### Login
```http
POST /api/v1/auth/login
```

Request body:
```json
{
  "username": "username",
  "password": "password"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
```

Request body:
```json
{
  "refresh_token": "eyJ..."
}
```

#### Get Current User
```http
GET /api/v1/auth/me
```

## Core Resources

### Agencies

#### List Agencies (Super Admin only)
```http
GET /api/v1/agencies
```

Query parameters:
- `page` (int): Page number (default: 1)
- `per_page` (int): Items per page (default: 20)

### Models

#### List Models
```http
GET /api/v1/models
```

Query parameters:
- `agency_id` (uuid): Filter by agency
- `status` (string): active, inactive
- `page` (int): Page number
- `per_page` (int): Items per page

#### Create Model
```http
POST /api/v1/models
```

Request body:
```json
{
  "stage_name": "ModelName",
  "onlyfans_username": "username",
  "inflow_id": "inflow_123",
  "onlyfans_id": "of_123",
  "commission_rate": 0.7
}
```

### Fans

#### List Fans
```http
GET /api/v1/fans
```

Query parameters:
- `model_id` (uuid): Filter by model
- `claimed_by` (uuid): Filter by chatter
- `is_subscriber` (bool): Filter subscribers
- `search` (string): Search by username

#### Claim Fan
```http
POST /api/v1/fans/{fan_id}/claim
```

#### Release Fan
```http
POST /api/v1/fans/{fan_id}/release
```

### Analytics

#### Get Analytics Summary
```http
GET /api/v1/analytics/summary
```

Query parameters:
- `model_id` (uuid): Filter by model
- `start_date` (date): Start date
- `end_date` (date): End date

Response:
```json
{
  "revenue": {
    "total": 50000,
    "subscriptions": 30000,
    "tips": 15000,
    "ppv": 5000
  },
  "subscribers": {
    "total": 1000,
    "new": 150,
    "churned": 50
  },
  "engagement": {
    "messages_sent": 5000,
    "messages_received": 3000,
    "response_rate": 0.85
  }
}
```

#### Get Time Series Data
```http
GET /api/v1/analytics/timeseries/{metric}
```

Metrics:
- `revenue`
- `subscribers`
- `messages`
- `tips`
- `ppv_sales`

Query parameters:
- `model_id` (uuid): Filter by model
- `interval` (string): hour, day, week, month
- `start_date` (date): Start date
- `end_date` (date): End date

### Financial

#### Get Billing Summary
```http
GET /api/v1/financial/billing/summary
```

#### List Invoices
```http
GET /api/v1/financial/invoices
```

#### Process Payout
```http
POST /api/v1/financial/payouts
```

Request body:
```json
{
  "model_id": "uuid",
  "amount": 1000.00,
  "currency": "USD",
  "payment_method": "crypto",
  "wallet_address": "0x..."
}
```

### White-Label

#### Get Theme Configuration
```http
GET /api/v1/whitelabel/theme
```

#### Update Theme
```http
PUT /api/v1/whitelabel/theme
```

Request body:
```json
{
  "default_mode": "dark",
  "light_theme": {
    "primary": "#007bff",
    "background": "#ffffff"
  },
  "dark_theme": {
    "primary": "#0d6efd",
    "background": "#212529"
  }
}
```

#### Upload Logo
```http
POST /api/v1/whitelabel/assets
```

Form data:
- `file`: Image file
- `asset_type`: agency_logo, model_logo, favicon

## WebSocket API

### Connection
```javascript
const socket = io('wss://api.agencydark.com', {
  auth: {
    token: 'Bearer <access_token>'
  }
});
```

### Events

#### Fan Claimed
```javascript
socket.on('fan_claimed', (data) => {
  console.log('Fan claimed:', data);
});
```

#### New Message
```javascript
socket.on('new_message', (data) => {
  console.log('New message:', data);
});
```

#### Send Message
```javascript
socket.emit('send_message', {
  fan_id: 'uuid',
  content: 'Hello!',
  media_urls: []
});
```

## Rate Limiting

API rate limits:
- Authentication: 5 requests/minute
- General API: 100 requests/minute
- Analytics: 20 requests/minute
- File uploads: 10 requests/minute

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Error Responses

Standard error response format:
```json
{
  "detail": "Error message",
  "status_code": 400,
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

Common status codes:
- `400` Bad Request
- `401` Unauthorized
- `403` Forbidden
- `404` Not Found
- `429` Too Many Requests
- `500` Internal Server Error

## Pagination

Paginated responses include:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

## Webhooks

Configure webhooks for real-time updates:

```http
POST /api/v1/webhooks
```

Request body:
```json
{
  "url": "https://your-app.com/webhook",
  "events": ["fan.new_subscriber", "payment.completed"],
  "secret": "webhook_secret"
}
```

Webhook payload:
```json
{
  "event": "fan.new_subscriber",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "fan_id": "uuid",
    "model_id": "uuid",
    "subscription_price": 9.99
  }
}
```

## API Keys

For automated integrations, use API keys instead of JWT tokens:

```
X-API-Key: agdk_your_api_key_here
```

Create API keys in the dashboard or via API:
```http
POST /api/v1/api-keys
```

## SDK Examples

### Python
```python
from agencydark import AgencyDarkClient

client = AgencyDarkClient(
    api_key="agdk_your_api_key",
    base_url="https://api.agencydark.com"
)

# Get analytics
analytics = client.analytics.get_summary(
    model_id="uuid",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

### JavaScript
```javascript
import { AgencyDark } from '@agencydark/sdk';

const client = new AgencyDark({
  apiKey: 'agdk_your_api_key',
  baseUrl: 'https://api.agencydark.com'
});

// Get models
const models = await client.models.list({
  agencyId: 'uuid',
  status: 'active'
});
```

## OpenAPI Specification

The complete OpenAPI specification is available at:
- JSON: `/api/openapi.json`
- Interactive docs: `/api/docs`
- ReDoc: `/api/redoc`