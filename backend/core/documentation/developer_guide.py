"""
Developer guide generation and management
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import markdown
import json

from core.logging import logger


class DeveloperGuide:
    """Generate and manage developer documentation"""
    
    def __init__(self, output_dir: Path = Path("docs/api")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_quickstart_guide(self) -> str:
        """Generate quickstart guide for developers"""
        guide = """
# Agency API Quickstart Guide

Welcome to the Agency API! This guide will help you get started quickly.

## Getting Started

### 1. Authentication

First, obtain your API credentials:

```bash
curl -X POST https://api.agency.com/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
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
curl -X GET https://api.agency.com/api/v1/users/me \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Common Operations

#### Create Content
```bash
curl -X POST https://api.agency.com/api/v1/content \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "My First Post",
    "content": "Hello, World!",
    "status": "draft"
  }'
```

#### Get Analytics
```bash
curl -X GET https://api.agency.com/api/v1/analytics/overview \\
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
"""
        
        # Save guide
        guide_path = self.output_dir / "quickstart.md"
        guide_path.write_text(guide)
        
        return guide
    
    def generate_authentication_guide(self) -> str:
        """Generate authentication guide"""
        guide = """
# Authentication Guide

## Overview

The Agency API uses JWT (JSON Web Tokens) for authentication. This guide covers all authentication methods and best practices.

## Authentication Methods

### 1. Email/Password Authentication

The standard authentication flow:

```python
import requests

# Login
response = requests.post(
    "https://api.agency.com/api/v1/auth/login",
    json={"email": "user@example.com", "password": "secure-password"}
)
token = response.json()["access_token"]

# Use token in requests
headers = {"Authorization": f"Bearer {token}"}
user = requests.get(
    "https://api.agency.com/api/v1/users/me",
    headers=headers
).json()
```

### 2. API Key Authentication

For server-to-server communication:

```python
headers = {"X-API-Key": "your-api-key"}
response = requests.get(
    "https://api.agency.com/api/v1/analytics",
    headers=headers
)
```

### 3. OAuth 2.0

We support OAuth 2.0 for third-party integrations:

#### Authorization Code Flow

1. Redirect user to authorization URL:
```
https://api.agency.com/oauth/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  scope=read write&
  state=RANDOM_STATE
```

2. Exchange code for token:
```python
response = requests.post(
    "https://api.agency.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": "AUTH_CODE",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uri": "YOUR_REDIRECT_URI"
    }
)
```

### 4. Service Accounts

For automated systems and CI/CD:

```python
# Create service account token
response = requests.post(
    "https://api.agency.com/api/v1/auth/service-account",
    json={
        "service_account_id": "sa_123",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----..."
    }
)
```

## Token Management

### Token Expiration

- Access tokens expire after 1 hour
- Refresh tokens expire after 30 days
- Service account tokens expire after 90 days

### Refreshing Tokens

```python
response = requests.post(
    "https://api.agency.com/api/v1/auth/refresh",
    json={"refresh_token": "your-refresh-token"}
)
new_token = response.json()["access_token"]
```

### Token Revocation

```python
requests.post(
    "https://api.agency.com/api/v1/auth/revoke",
    json={"token": "token-to-revoke"},
    headers={"Authorization": f"Bearer {admin_token}"}
)
```

## Security Best Practices

### 1. Token Storage

- **Never** store tokens in source code
- Use environment variables or secure vaults
- Implement token encryption at rest

### 2. Token Transmission

- Always use HTTPS
- Include tokens in Authorization header, not URL
- Implement request signing for sensitive operations

### 3. Token Rotation

- Rotate API keys regularly
- Implement automatic token refresh
- Monitor token usage for anomalies

### 4. Scope Management

Request minimal scopes:

```python
# Good - specific scopes
scopes = ["users:read", "content:write"]

# Bad - overly broad
scopes = ["admin"]
```

## Multi-Factor Authentication (MFA)

### Enabling MFA

```python
# Enable TOTP
response = requests.post(
    "https://api.agency.com/api/v1/auth/mfa/enable",
    json={"type": "totp"},
    headers=headers
)
qr_code = response.json()["qr_code"]
```

### Authentication with MFA

```python
# Login with MFA
response = requests.post(
    "https://api.agency.com/api/v1/auth/login",
    json={
        "email": "user@example.com",
        "password": "password",
        "mfa_code": "123456"
    }
)
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check token expiration
   - Verify token format
   - Ensure correct Authorization header

2. **403 Forbidden**
   - Check token scopes
   - Verify resource permissions
   - Check rate limits

3. **Invalid Token**
   - Token may be corrupted
   - Check for extra whitespace
   - Verify token hasn't been revoked

### Debug Headers

Include debug headers for detailed error info:

```python
headers = {
    "Authorization": f"Bearer {token}",
    "X-Debug-Mode": "true"
}
```

## Code Examples

### Python SDK
```python
from agency_sdk import Client

client = Client(api_key="your-api-key")
user = client.users.get_current()
```

### Node.js SDK
```javascript
const { AgencyClient } = require('@agency/sdk');

const client = new AgencyClient({
  apiKey: 'your-api-key'
});

const user = await client.users.getCurrent();
```

### Go SDK
```go
import "github.com/agency/agency-go"

client := agency.NewClient("your-api-key")
user, err := client.Users.GetCurrent()
```

## Additional Resources

- [OAuth 2.0 Specification](https://oauth.net/2/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [API Security Checklist](https://github.com/shieldfy/API-Security-Checklist)
"""
        
        # Save guide
        guide_path = self.output_dir / "authentication.md"
        guide_path.write_text(guide)
        
        return guide
    
    def generate_best_practices_guide(self) -> str:
        """Generate API best practices guide"""
        guide = """
# API Best Practices

## Request Optimization

### 1. Use Field Selection

Request only the fields you need:

```bash
# Good - specific fields
GET /api/v1/users/123?fields=id,name,email

# Bad - all fields
GET /api/v1/users/123
```

### 2. Pagination

Always paginate list requests:

```python
# Good - paginated request
page = 1
while True:
    response = requests.get(
        f"/api/v1/content?page={page}&limit=100"
    )
    data = response.json()
    process_items(data["items"])
    
    if page >= data["pages"]:
        break
    page += 1
```

### 3. Batch Operations

Use batch endpoints when available:

```python
# Good - single batch request
requests.post("/api/v1/users/batch", json={
    "operations": [
        {"method": "POST", "data": {"name": "User 1"}},
        {"method": "POST", "data": {"name": "User 2"}},
        {"method": "POST", "data": {"name": "User 3"}}
    ]
})

# Bad - multiple individual requests
for user in users:
    requests.post("/api/v1/users", json=user)
```

## Error Handling

### 1. Implement Retry Logic

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)

# Apply to session
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
```

### 2. Handle Rate Limits

```python
def make_request_with_rate_limit(url, headers):
    response = requests.get(url, headers=headers)
    
    if response.status_code == 429:
        # Get retry after header
        retry_after = int(response.headers.get("Retry-After", 60))
        time.sleep(retry_after)
        return make_request_with_rate_limit(url, headers)
    
    return response
```

### 3. Graceful Degradation

```python
def get_user_with_fallback(user_id):
    try:
        # Try to get fresh data
        return api_client.get(f"/users/{user_id}")
    except APIError:
        # Fall back to cache
        return cache.get(f"user:{user_id}")
```

## Performance Optimization

### 1. Connection Pooling

```python
# Reuse connections
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}"})

# Make multiple requests with same session
for endpoint in endpoints:
    response = session.get(endpoint)
```

### 2. Async Requests

```python
import asyncio
import aiohttp

async def fetch_multiple(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_one(session, url):
    async with session.get(url) as response:
        return await response.json()
```

### 3. Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_response(endpoint, params_hash):
    return requests.get(endpoint, params=params).json()

# Use cache
params = {"filter": "active", "sort": "created_at"}
params_hash = hashlib.md5(
    json.dumps(params, sort_keys=True).encode()
).hexdigest()
data = get_cached_response("/api/v1/users", params_hash)
```

## Security Best Practices

### 1. Input Validation

```python
# Validate all inputs
def create_user(data):
    # Sanitize inputs
    data["email"] = data["email"].lower().strip()
    data["name"] = bleach.clean(data["name"])
    
    # Validate format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
        raise ValueError("Invalid email format")
    
    return api_client.post("/users", json=data)
```

### 2. Secure Token Handling

```python
import os
from cryptography.fernet import Fernet

# Encrypt tokens at rest
key = os.environ["ENCRYPTION_KEY"].encode()
cipher = Fernet(key)

def store_token(token):
    encrypted = cipher.encrypt(token.encode())
    save_to_secure_storage(encrypted)

def retrieve_token():
    encrypted = load_from_secure_storage()
    return cipher.decrypt(encrypted).decode()
```

### 3. Request Signing

```python
import hmac
import hashlib

def sign_request(method, path, body, secret):
    # Create signature
    message = f"{method}\\n{path}\\n{body}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature

# Use signature
signature = sign_request("POST", "/api/v1/transfer", body, secret)
headers["X-Signature"] = signature
```

## Monitoring and Logging

### 1. Request Tracking

```python
import uuid
import logging

def make_tracked_request(endpoint, **kwargs):
    request_id = str(uuid.uuid4())
    
    # Add tracking header
    headers = kwargs.get("headers", {})
    headers["X-Request-ID"] = request_id
    kwargs["headers"] = headers
    
    # Log request
    logging.info(f"API Request: {request_id} - {endpoint}")
    
    try:
        response = requests.get(endpoint, **kwargs)
        logging.info(f"API Response: {request_id} - {response.status_code}")
        return response
    except Exception as e:
        logging.error(f"API Error: {request_id} - {str(e)}")
        raise
```

### 2. Performance Monitoring

```python
import time
from contextlib import contextmanager

@contextmanager
def monitor_api_call(operation):
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        metrics.record("api.call.duration", duration, tags={
            "operation": operation
        })
```

### 3. Error Tracking

```python
def track_api_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            # Track error metrics
            metrics.increment("api.errors", tags={
                "status_code": e.status_code,
                "error_code": e.error_code,
                "endpoint": e.endpoint
            })
            
            # Send to error tracking service
            sentry.capture_exception(e)
            raise
    return wrapper
```

## Testing

### 1. Mock API Responses

```python
from unittest.mock import patch

@patch('requests.get')
def test_get_user(mock_get):
    # Mock response
    mock_get.return_value.json.return_value = {
        "id": 1,
        "name": "Test User"
    }
    
    # Test code
    user = get_user(1)
    assert user["name"] == "Test User"
```

### 2. Integration Testing

```python
import pytest

@pytest.mark.integration
def test_user_workflow():
    # Create user
    user = api_client.create_user({
        "name": "Test User",
        "email": "test@example.com"
    })
    
    # Update user
    updated = api_client.update_user(user["id"], {
        "name": "Updated Name"
    })
    
    # Verify update
    assert updated["name"] == "Updated Name"
    
    # Cleanup
    api_client.delete_user(user["id"])
```

### 3. Load Testing

```python
import concurrent.futures
import statistics

def load_test_endpoint(endpoint, concurrent_requests=10):
    def make_request():
        start = time.time()
        response = requests.get(endpoint)
        return time.time() - start
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        response_times = list(executor.map(
            lambda _: make_request(),
            range(concurrent_requests)
        ))
    
    print(f"Average response time: {statistics.mean(response_times):.2f}s")
    print(f"95th percentile: {statistics.quantiles(response_times, n=20)[18]:.2f}s")
```

## Versioning Strategy

### 1. Version Headers

```python
# Specify version in header
headers = {
    "API-Version": "v2",
    "Accept": "application/vnd.agency.v2+json"
}
```

### 2. Graceful Migration

```python
def get_user_compatible(user_id, version="v1"):
    if version == "v1":
        # Old format
        user = api_client.get(f"/api/v1/users/{user_id}")
        return {
            "id": user["id"],
            "name": user["full_name"]  # v1 field name
        }
    else:
        # New format
        user = api_client.get(f"/api/v2/users/{user_id}")
        return {
            "id": user["id"],
            "name": f"{user['first_name']} {user['last_name']}"  # v2 fields
        }
```

## Additional Resources

- [RESTful API Design](https://restfulapi.net/)
- [API Design Patterns](https://www.oreilly.com/library/view/api-design-patterns/9781617295850/)
- [The Web API Checklist](https://mathieu.fenniak.net/the-api-checklist/)
"""
        
        # Save guide
        guide_path = self.output_dir / "best-practices.md"
        guide_path.write_text(guide)
        
        return guide
    
    def generate_webhook_guide(self) -> str:
        """Generate webhook integration guide"""
        guide = """
# Webhook Integration Guide

## Overview

Webhooks allow you to receive real-time notifications when events occur in the Agency platform.

## Setting Up Webhooks

### 1. Register Webhook Endpoint

```python
webhook = api_client.webhooks.create({
    "url": "https://your-app.com/webhooks/agency",
    "events": ["user.created", "content.published", "payment.completed"],
    "secret": "your-webhook-secret"
})
```

### 2. Webhook Events

Available events:

| Event | Description | Payload |
|-------|-------------|---------|
| `user.created` | New user registered | User object |
| `user.updated` | User profile updated | User object + changes |
| `user.deleted` | User account deleted | User ID |
| `content.created` | New content created | Content object |
| `content.published` | Content published | Content object |
| `content.deleted` | Content deleted | Content ID |
| `payment.completed` | Payment processed | Payment object |
| `subscription.created` | New subscription | Subscription object |
| `subscription.cancelled` | Subscription cancelled | Subscription object |

### 3. Webhook Security

#### Signature Verification

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

# In your webhook handler
@app.post("/webhooks/agency")
def handle_webhook(request):
    signature = request.headers.get("X-Agency-Signature")
    
    if not verify_webhook_signature(
        request.body,
        signature,
        webhook_secret
    ):
        return {"error": "Invalid signature"}, 401
    
    # Process webhook
    return {"status": "ok"}, 200
```

## Handling Webhooks

### 1. Basic Handler

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/webhooks/agency", methods=["POST"])
def webhook_handler():
    # Verify signature
    if not verify_signature(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Parse event
    event = request.json
    event_type = event["type"]
    
    # Handle event
    if event_type == "user.created":
        handle_user_created(event["data"])
    elif event_type == "content.published":
        handle_content_published(event["data"])
    
    # Always return 200 to acknowledge receipt
    return jsonify({"status": "received"}), 200

def handle_user_created(user_data):
    # Send welcome email
    send_welcome_email(user_data["email"])
    
    # Add to CRM
    crm.create_contact({
        "email": user_data["email"],
        "name": user_data["name"]
    })

def handle_content_published(content_data):
    # Post to social media
    social_media.post({
        "title": content_data["title"],
        "url": content_data["url"]
    })
    
    # Update search index
    search.index_content(content_data)
```

### 2. Async Processing

```python
from celery import Celery

celery = Celery("webhooks", broker="redis://localhost:6379")

@app.route("/webhooks/agency", methods=["POST"])
def webhook_handler():
    # Quick validation
    if not verify_signature(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Queue for async processing
    process_webhook.delay(request.json)
    
    # Return immediately
    return jsonify({"status": "queued"}), 200

@celery.task
def process_webhook(event):
    event_type = event["type"]
    handlers = {
        "user.created": handle_user_created,
        "content.published": handle_content_published,
        "payment.completed": handle_payment_completed
    }
    
    handler = handlers.get(event_type)
    if handler:
        handler(event["data"])
```

### 3. Error Handling

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@app.route("/webhooks/agency", methods=["POST"])
def webhook_handler():
    try:
        # Process webhook
        event = request.json
        process_event(event)
        
        return jsonify({"status": "success"}), 200
        
    except ValueError as e:
        # Bad request
        logger.error(f"Invalid webhook data: {e}")
        return jsonify({"error": "Invalid data"}), 400
        
    except Exception as e:
        # Internal error - return 500 so Agency retries
        logger.error(f"Webhook processing failed: {e}")
        return jsonify({"error": "Internal error"}), 500
```

## Webhook Retry Logic

Agency will retry failed webhooks with exponential backoff:

- 1st retry: 1 minute
- 2nd retry: 5 minutes
- 3rd retry: 30 minutes
- 4th retry: 2 hours
- 5th retry: 12 hours

### Handling Duplicates

```python
import redis

redis_client = redis.Redis()

def is_duplicate_event(event_id):
    # Check if we've seen this event
    key = f"webhook:event:{event_id}"
    
    # Set with 24 hour expiration
    return not redis_client.set(key, 1, ex=86400, nx=True)

@app.route("/webhooks/agency", methods=["POST"])
def webhook_handler():
    event = request.json
    
    # Check for duplicate
    if is_duplicate_event(event["id"]):
        logger.info(f"Duplicate event received: {event['id']}")
        return jsonify({"status": "duplicate"}), 200
    
    # Process event
    process_event(event)
    return jsonify({"status": "success"}), 200
```

## Testing Webhooks

### 1. Webhook Testing Tool

```python
# Use Agency's webhook testing tool
test_event = api_client.webhooks.test(
    webhook_id="wh_123",
    event_type="user.created"
)
```

### 2. Local Development

Use ngrok for local webhook development:

```bash
# Start ngrok
ngrok http 5000

# Register webhook with ngrok URL
api_client.webhooks.create({
    "url": "https://abc123.ngrok.io/webhooks/agency",
    "events": ["*"]  # All events for testing
})
```

### 3. Webhook Logs

```python
# View webhook delivery logs
logs = api_client.webhooks.get_logs(
    webhook_id="wh_123",
    limit=100
)

for log in logs:
    print(f"{log['timestamp']}: {log['status']} - {log['event_type']}")
    if log['status'] == 'failed':
        print(f"Error: {log['error']}")
```

## Advanced Patterns

### 1. Event Sourcing

```python
class EventStore:
    def __init__(self):
        self.events = []
    
    def store_event(self, event):
        self.events.append({
            "id": event["id"],
            "type": event["type"],
            "data": event["data"],
            "timestamp": event["timestamp"],
            "processed_at": datetime.utcnow()
        })
    
    def replay_events(self, from_timestamp=None):
        events = self.events
        if from_timestamp:
            events = [e for e in events if e["timestamp"] > from_timestamp]
        
        for event in events:
            process_event(event)
```

### 2. Webhook Transformations

```python
def transform_webhook_payload(event):
    # Transform Agency format to your internal format
    transformers = {
        "user.created": transform_user,
        "content.published": transform_content
    }
    
    transformer = transformers.get(event["type"])
    if transformer:
        return transformer(event["data"])
    
    return event["data"]

def transform_user(agency_user):
    return {
        "id": agency_user["id"],
        "email": agency_user["email"],
        "full_name": agency_user["name"],
        "created": agency_user["created_at"],
        "source": "agency"
    }
```

### 3. Webhook Monitoring

```python
from prometheus_client import Counter, Histogram

webhook_received = Counter(
    "webhooks_received_total",
    "Total webhooks received",
    ["event_type"]
)

webhook_processing_time = Histogram(
    "webhook_processing_seconds",
    "Webhook processing time",
    ["event_type"]
)

@app.route("/webhooks/agency", methods=["POST"])
def webhook_handler():
    event = request.json
    event_type = event["type"]
    
    # Track metrics
    webhook_received.labels(event_type=event_type).inc()
    
    with webhook_processing_time.labels(event_type=event_type).time():
        process_event(event)
    
    return jsonify({"status": "success"}), 200
```

## Troubleshooting

### Common Issues

1. **Webhook not receiving events**
   - Verify endpoint is publicly accessible
   - Check webhook is active
   - Confirm events are subscribed

2. **Signature verification failing**
   - Ensure using raw request body
   - Check secret matches
   - Verify signature algorithm

3. **Duplicate events**
   - Implement idempotency
   - Track processed event IDs
   - Handle gracefully

### Debug Mode

```python
# Enable webhook debug mode
api_client.webhooks.update(
    webhook_id="wh_123",
    debug=True  # Adds debug headers
)

# Debug headers in webhook:
# X-Agency-Debug: true
# X-Agency-Retry-Count: 2
# X-Agency-First-Attempt: 2024-01-28T12:00:00Z
```

## Best Practices

1. **Always return 200 quickly** - Process async if needed
2. **Implement idempotency** - Handle duplicate events
3. **Verify signatures** - Ensure webhook authenticity
4. **Log everything** - Track all webhook activity
5. **Monitor performance** - Track processing times
6. **Handle errors gracefully** - Don't lose events
7. **Test thoroughly** - Use webhook testing tools

## Additional Resources

- [Webhook Specification](https://www.standardwebhooks.com/)
- [Webhook Best Practices](https://docs.svix.com/receiving/best-practices)
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html)
"""
        
        # Save guide
        guide_path = self.output_dir / "webhooks.md"
        guide_path.write_text(guide)
        
        return guide
    
    def generate_all_guides(self) -> Dict[str, str]:
        """Generate all developer guides"""
        guides = {
            "quickstart": self.generate_quickstart_guide(),
            "authentication": self.generate_authentication_guide(),
            "best-practices": self.generate_best_practices_guide(),
            "webhooks": self.generate_webhook_guide()
        }
        
        # Generate index
        index = """
# Agency API Developer Documentation

Welcome to the Agency API developer documentation. These guides will help you integrate with our API effectively.

## Guides

### Getting Started
- [Quickstart Guide](quickstart.md) - Get up and running quickly
- [Authentication Guide](authentication.md) - All authentication methods explained

### Integration
- [Webhook Integration](webhooks.md) - Real-time event notifications
- [Best Practices](best-practices.md) - Optimize your API usage

### References
- [API Reference](/api/v1/docs) - Interactive API documentation
- [OpenAPI Spec](/api/v1/openapi.json) - Machine-readable API specification

## Support

- **Email**: api@agency.com
- **Discord**: [Join our community](https://discord.gg/agency)
- **GitHub**: [Report issues](https://github.com/agency/api/issues)

## Status

Check our [status page](https://status.agency.com) for real-time API health information.
"""
        
        index_path = self.output_dir / "index.md"
        index_path.write_text(index)
        
        logger.info(f"Generated {len(guides)} developer guides in {self.output_dir}")
        
        return guides