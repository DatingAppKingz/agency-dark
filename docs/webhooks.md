# Webhook Integration Guide

## Overview

AgencyDark provides a robust webhook system that allows you to receive real-time notifications about events happening in your agency. This enables you to integrate with external systems, automate workflows, and build custom integrations.

## Available Events

### Message Events
- `message.received` - Triggered when a fan sends a message
- `message.sent` - Triggered when a model sends a message
- `message.read` - Triggered when a message is marked as read

### Fan Events
- `fan.subscribed` - Triggered when a new fan subscribes
- `fan.unsubscribed` - Triggered when a fan unsubscribes
- `fan.updated` - Triggered when fan profile data is updated

### Payment Events
- `payment.received` - Triggered when a payment is successfully processed
- `payment.failed` - Triggered when a payment fails
- `payment.refunded` - Triggered when a payment is refunded

### Model Events
- `model.online` - Triggered when a model goes online
- `model.offline` - Triggered when a model goes offline
- `model.updated` - Triggered when model profile is updated

### Analytics Events
- `analytics.daily_summary` - Triggered daily with analytics summary
- `analytics.milestone` - Triggered when milestones are reached

## Setting Up Webhooks

### Create a Webhook

```bash
curl -X POST https://api.agencydark.com/api/v1/webhooks \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook",
    "events": ["message.received", "payment.received"],
    "description": "Production webhook",
    "is_active": true,
    "retry_enabled": true,
    "max_retries": 3
  }'
```

### Webhook Payload Structure

All webhook payloads follow this structure:

```json
{
  "event": "message.received",
  "event_id": "unique-event-id",
  "timestamp": "2025-01-27T12:00:00Z",
  "data": {
    // Event-specific data
  }
}
```

### Example Payloads

#### Message Received
```json
{
  "event": "message.received",
  "event_id": "msg_123456",
  "timestamp": "2025-01-27T12:00:00Z",
  "data": {
    "message_id": "123e4567-e89b-12d3-a456-426614174000",
    "model_id": "123e4567-e89b-12d3-a456-426614174001",
    "fan_id": "123e4567-e89b-12d3-a456-426614174002",
    "content": "Hello!",
    "sender": "fan",
    "created_at": "2025-01-27T12:00:00Z",
    "media_count": 0,
    "has_media": false
  }
}
```

#### Payment Received
```json
{
  "event": "payment.received",
  "event_id": "pay_123456",
  "timestamp": "2025-01-27T12:00:00Z",
  "data": {
    "payment_id": "123e4567-e89b-12d3-a456-426614174000",
    "model_id": "123e4567-e89b-12d3-a456-426614174001",
    "fan_id": "123e4567-e89b-12d3-a456-426614174002",
    "amount": 50.00,
    "currency": "USD",
    "payment_type": "tip",
    "status": "completed",
    "created_at": "2025-01-27T12:00:00Z"
  }
}
```

## Webhook Security

### Signature Verification

All webhooks are signed using HMAC-SHA256. You should verify the signature to ensure the webhook is legitimate.

#### Python Example
```python
import hmac
import hashlib

def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your webhook handler
@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature")
    
    if not verify_webhook_signature(payload.decode(), signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook...
```

#### Node.js Example
```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
    const expected = 'sha256=' + crypto
        .createHmac('sha256', secret)
        .update(payload)
        .digest('hex');
    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(signature)
    );
}

// In your webhook handler
app.post('/webhook', (req, res) => {
    const signature = req.headers['x-webhook-signature'];
    const payload = JSON.stringify(req.body);
    
    if (!verifyWebhookSignature(payload, signature, webhookSecret)) {
        return res.status(401).send('Invalid signature');
    }
    
    // Process webhook...
});
```

## Webhook Headers

Each webhook request includes these headers:

- `X-Webhook-ID` - The webhook configuration ID
- `X-Webhook-Signature` - HMAC signature for verification
- `X-Webhook-Timestamp` - Unix timestamp of when the webhook was sent
- `Content-Type` - Always `application/json`
- `User-Agent` - `AgencyDark-Webhook/1.0`

## Retry Logic

If your webhook endpoint doesn't respond with a 2xx status code, we'll retry the delivery:

- **Retry Schedule**: Exponential backoff (1 min, 2 min, 4 min, etc.)
- **Max Retries**: Configurable (default: 3)
- **Max Retry Delay**: 1 hour
- **Timeout**: Configurable (default: 30 seconds)

## Best Practices

1. **Respond Quickly**: Return a 200 status as soon as possible, process the webhook asynchronously
2. **Verify Signatures**: Always verify webhook signatures in production
3. **Handle Duplicates**: Use the `event_id` to handle potential duplicate deliveries
4. **Monitor Failures**: Check webhook delivery history regularly
5. **Use HTTPS**: Always use HTTPS endpoints for security

## Testing Webhooks

### Test a Webhook Endpoint
```bash
curl -X POST https://api.agencydark.com/api/v1/webhooks/{webhook_id}/test \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### View Delivery History
```bash
curl https://api.agencydark.com/api/v1/webhooks/{webhook_id}/deliveries \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Webhook Management API

### List Webhooks
```bash
GET /api/v1/webhooks
```

### Get Webhook Details
```bash
GET /api/v1/webhooks/{webhook_id}
```

### Update Webhook
```bash
PUT /api/v1/webhooks/{webhook_id}
```

### Delete Webhook
```bash
DELETE /api/v1/webhooks/{webhook_id}
```

### Get Event Documentation
```bash
GET /api/v1/webhooks/docs/events
```

### Get Signature Verification Documentation
```bash
GET /api/v1/webhooks/docs/signature
```

## Error Handling

If webhook delivery fails, you can:

1. Check delivery history to see error details
2. Test your endpoint using the test endpoint
3. Review your endpoint logs
4. Ensure your endpoint responds within the timeout period
5. Verify your endpoint returns a 2xx status code

## Rate Limits

- Maximum 10 webhooks per agency
- Maximum 1000 deliveries per webhook per hour
- Webhooks with >90% failure rate may be automatically disabled

## Support

For webhook-related issues:
1. Check the delivery history for error messages
2. Use the test endpoint to debug
3. Review this documentation
4. Contact support with your webhook ID and event IDs
