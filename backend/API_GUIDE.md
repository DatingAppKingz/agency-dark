# API Guide

Comprehensive guide for using the AgencyDark API.

## 🔑 Authentication

### Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using Tokens
All authenticated requests must include the Authorization header:
```bash
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Refresh Token
```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "YOUR_REFRESH_TOKEN"
}
```

## 📋 Common Endpoints

### User Management

#### Get Current User
```bash
GET /api/v1/users/me
Authorization: Bearer YOUR_TOKEN

Response:
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "agency_owner",
  "agency_id": "uuid",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### Update Profile
```bash
PUT /api/v1/users/me
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890"
}
```

### Agency Operations

#### Get Agency Details
```bash
GET /api/v1/agencies/current
Authorization: Bearer YOUR_TOKEN

Response:
{
  "id": "uuid",
  "name": "Elite Models Agency",
  "owner_id": "uuid",
  "subscription_tier": "premium",
  "model_count": 25,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Model Management

#### List Models
```bash
GET /api/v1/models?page=1&limit=20&status=active
Authorization: Bearer YOUR_TOKEN

Response:
{
  "items": [
    {
      "id": "uuid",
      "stage_name": "ModelName",
      "platform": "onlyfans",
      "status": "active",
      "total_earnings": 50000.00
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 20,
  "pages": 5
}
```

#### Create Model
```bash
POST /api/v1/models
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "user_email": "model@example.com",
  "stage_name": "ModelName",
  "platform": "onlyfans",
  "platform_username": "modelusername",
  "categories": ["fitness", "lifestyle"]
}
```

### Chat & Messaging

#### Send Message
```bash
POST /api/v1/chat/messages
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "conversation_id": "uuid",
  "content": "Hello!",
  "message_type": "text"
}
```

#### Upload Media
```bash
POST /api/v1/media/upload
Authorization: Bearer YOUR_TOKEN
Content-Type: multipart/form-data

file: (binary)
type: "image"
entity_type: "message"
entity_id: "uuid"
```

### Financial Operations

#### Get Revenue Report
```bash
GET /api/v1/reports/revenue?start_date=2024-01-01&end_date=2024-01-31
Authorization: Bearer YOUR_TOKEN

Response:
{
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "metrics": {
    "total_revenue": 125000.00,
    "net_revenue": 100000.00,
    "transaction_count": 1523
  },
  "daily_breakdown": [...]
}
```

#### Export Report as PDF
```bash
POST /api/v1/enhanced-reports/export
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "report_type": "revenue",
  "format": "pdf",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "include_charts": true
}

Response:
{
  "file_id": "report_abc123",
  "download_url": "/api/v1/enhanced-reports/download/report_abc123.pdf",
  "expires_at": "2024-02-01T00:00:00Z"
}
```

### External API Management

#### Validate API Credentials
```bash
POST /api/v1/external-api/validate
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "provider": "stripe",
  "credentials": {
    "api_key": "sk_test_..."
  }
}

Response:
{
  "is_valid": true,
  "provider": "stripe",
  "metadata": {
    "account_id": "acct_xxx",
    "account_name": "Your Business"
  }
}
```

#### List Stored Credentials
```bash
GET /api/v1/external-api/credentials?page=1&limit=10
Authorization: Bearer YOUR_TOKEN

Response:
{
  "items": [...],
  "total": 3,
  "page": 1,
  "limit": 10
}
```

### Task Scheduling

#### Create Scheduled Task
```bash
POST /api/v1/schedule/tasks
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "name": "Daily Revenue Report",
  "task_type": "report_generation",
  "cron_expression": "0 9 * * *",
  "parameters": {
    "report_type": "revenue",
    "recipients": ["owner@agency.com"]
  }
}
```

#### Validate Cron Expression
```bash
POST /api/v1/schedule/validate-cron
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "expression": "0 9 * * *",
  "timezone": "America/New_York"
}

Response:
{
  "valid": true,
  "description": "At 09:00 AM",
  "next_runs": [
    "2024-01-02T09:00:00-05:00",
    "2024-01-03T09:00:00-05:00"
  ]
}
```

## 🔍 Search & Filtering

### Global Search
```bash
GET /api/v1/search?q=john&types=users,models&limit=10
Authorization: Bearer YOUR_TOKEN

Response:
{
  "results": {
    "users": [...],
    "models": [...]
  },
  "total": 15
}
```

### Advanced Filtering
Most list endpoints support advanced filtering:

```bash
GET /api/v1/models?
  status=active&
  platform=onlyfans&
  min_earnings=10000&
  categories=fitness,lifestyle&
  sort_by=total_earnings&
  sort_order=desc
```

## 📊 Real-time Updates

### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'YOUR_ACCESS_TOKEN'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Subscribe to Events
```javascript
// Subscribe to chat messages
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'chat',
  conversation_id: 'uuid'
}));

// Subscribe to notifications
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'notifications'
}));
```

## 🚨 Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Common Error Codes
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/expired token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

## 📈 Rate Limiting

### Headers
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1640995200
```

### Tiers
- Anonymous: 10 requests/minute
- Authenticated: 100 requests/minute
- Premium: 1000 requests/minute

## 🔧 Advanced Features

### Bulk Operations
```bash
POST /api/v1/bulk/users/invite
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "emails": [
    "user1@example.com",
    "user2@example.com"
  ],
  "role": "model",
  "send_email": true
}
```

### Batch Requests
```bash
POST /api/v1/batch
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "requests": [
    {
      "method": "GET",
      "url": "/api/v1/users/me"
    },
    {
      "method": "GET",
      "url": "/api/v1/models"
    }
  ]
}
```

### Webhooks
```bash
POST /api/v1/webhooks
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "url": "https://your-domain.com/webhook",
  "events": ["model.created", "payment.received"],
  "secret": "your_webhook_secret"
}
```

## 📱 SDK Examples

### Python
```python
import httpx

class AgencyDarkAPI:
    def __init__(self, base_url, token):
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"}
        )
    
    async def get_models(self, page=1, limit=20):
        response = await self.client.get(
            "/api/v1/models",
            params={"page": page, "limit": limit}
        )
        return response.json()
```

### JavaScript/TypeScript
```typescript
class AgencyDarkAPI {
  constructor(
    private baseURL: string,
    private token: string
  ) {}

  async getModels(page = 1, limit = 20) {
    const response = await fetch(
      `${this.baseURL}/api/v1/models?page=${page}&limit=${limit}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );
    return response.json();
  }
}
```

## 🧪 Testing Endpoints

Use the provided Postman collection or test with curl:

```bash
# Set variables
export BASE_URL="http://localhost:8000"
export TOKEN="your_access_token"

# Test authentication
curl -X GET "$BASE_URL/api/v1/users/me" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# Test with data
curl -X POST "$BASE_URL/api/v1/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage_name": "TestModel", "platform": "onlyfans"}' | jq '.'
```

## 📚 Additional Resources

- [OpenAPI Schema](/docs)
- [Postman Collection](https://api.agencydark.com/postman)
- [API Changelog](/api/v1/changelog)
- [Status Page](https://status.agencydark.com)