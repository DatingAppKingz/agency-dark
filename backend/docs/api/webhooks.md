
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
