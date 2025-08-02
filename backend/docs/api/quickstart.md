
# Agency API Quickstart Guide

Welcome to the Agency API! This guide will help you get started quickly.

## Getting Started

### 1. Authentication

First, obtain your API credentials:

```bash
curl -X POST https://api.agency.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "your-password"}'
```

This will return an access token:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 2. Making Your First Request

Use the access token to make authenticated requests:

```bash
curl -X GET https://api.agency.com/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Common Operations

#### Create Content
```bash
curl -X POST https://api.agency.com/api/v1/content \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Post",
    "content": "Hello, World!",
    "status": "draft"
  }'
```

#### Get Analytics
```bash
curl -X GET https://api.agency.com/api/v1/analytics/overview \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## SDKs and Libraries

We provide official SDKs for popular languages:

- **Python**: `pip install agency-sdk`
- **JavaScript/Node**: `npm install @agency/sdk`
- **Go**: `go get github.com/agency/agency-go`
- **Ruby**: `gem install agency-sdk`

## Rate Limiting

API requests are rate-limited based on your subscription:

| Tier | Requests/Hour | Burst |
|------|--------------|--------|
| Free | 100 | 10/min |
| Basic | 1,000 | 100/min |
| Pro | 10,000 | 1,000/min |
| Enterprise | Unlimited | Custom |

## Error Handling

The API uses standard HTTP status codes:

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error

Error responses include detailed information:

```json
{
  "detail": "Invalid authentication credentials",
  "status_code": 401,
  "error_code": "AUTH_INVALID_CREDENTIALS",
  "timestamp": "2024-01-28T12:00:00Z"
}
```

## Next Steps

- [API Reference](/api/v1/docs)
- [Authentication Guide](/docs/authentication)
- [Webhook Integration](/docs/webhooks)
- [Best Practices](/docs/best-practices)

## Support

- Email: api@agency.com
- Discord: [Join our community](https://discord.gg/agency)
- GitHub: [Report issues](https://github.com/agency/api/issues)
