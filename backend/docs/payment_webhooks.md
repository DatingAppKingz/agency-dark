# Payment Webhook Documentation

## Overview

The payment webhook system handles real-time payment status updates from cryptocurrency payment providers (Coinbase Commerce and BitPay). This enables automatic transaction status updates, commission calculations, and real-time notifications.

## Webhook Endpoints

### Coinbase Commerce Webhook
```
POST /api/v1/payments/webhooks/coinbase
Headers:
  - X-CC-Webhook-Signature: {signature}
```

Handles events:
- `charge:confirmed` - Payment confirmed on blockchain
- `charge:failed` - Payment failed
- `charge:delayed` - Payment processing delayed
- `charge:resolved` - Payment resolved after delay

### BitPay Webhook
```
POST /api/v1/payments/webhooks/bitpay
```

Handles events:
- `invoice_confirmed` - Payment confirmed
- `invoice_completed` - Payment fully completed
- `invoice_expired` - Invoice expired
- `invoice_invalid` - Invoice invalid/failed

### Future Webhooks (Placeholders)
- `/api/v1/payments/webhooks/stripe` - Reserved for Stripe integration
- `/api/v1/payments/webhooks/paypal` - Reserved for PayPal integration

## Security

### Signature Verification

All webhooks implement signature verification to ensure authenticity:

1. **Coinbase Commerce**: Uses HMAC-SHA256 signature verification
   - Signature sent in `X-CC-Webhook-Signature` header
   - Verified against raw request body

2. **BitPay**: Uses webhook notification system
   - Future: Implement BitPay's signature verification

### Implementation Example
```python
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Webhook Flow

1. **Payment Initiated**: Transaction created with `PENDING` status
2. **Webhook Received**: Payment provider sends status update
3. **Signature Verified**: Webhook authenticity confirmed
4. **Transaction Updated**: Status changed based on event type
5. **Notification Sent**: Real-time notification via Socket.IO
6. **Commission Calculated**: If payment confirmed, commission auto-calculated

## Event Handling

### Payment Confirmation
When a payment is confirmed:
1. Transaction status → `COMPLETED`
2. `processed_at` timestamp set
3. Metadata updated with confirmation details
4. Real-time notification sent
5. Commission calculation triggered (if configured)

### Payment Failure
When a payment fails:
1. Transaction status → `FAILED`
2. Failure reason stored in metadata
3. Real-time notification sent
4. User notified of failure

### Payment Delays
When a payment is delayed:
1. Delay notification stored in metadata
2. Transaction remains `PENDING`
3. Real-time notification sent
4. System waits for resolution

## Real-time Notifications

Webhooks trigger real-time notifications via Redis pub/sub:

```python
await send_notification(
    "payment_confirmed",
    {
        "transaction_id": str(transaction.id),
        "model_id": str(transaction.model_id),
        "amount": float(amount),
        "currency": currency,
        "provider": provider
    }
)
```

Notification types:
- `payment_confirmed` - Payment successfully confirmed
- `payment_failed` - Payment failed
- `payment_delayed` - Payment processing delayed
- `payment_expired` - Payment window expired

## Testing Webhooks

### Local Development
Use ngrok or similar tool to expose local endpoints:
```bash
ngrok http 8000
```

Configure webhook URL in payment provider:
```
https://your-ngrok-url.ngrok.io/api/v1/payments/webhooks/coinbase
```

### Test Payloads

#### Coinbase Test Payload
```json
{
  "event": {
    "type": "charge:confirmed",
    "data": {
      "code": "CHARGE_CODE",
      "pricing": {
        "local": {
          "amount": "100.00",
          "currency": "USD"
        }
      }
    }
  }
}
```

#### BitPay Test Payload
```json
{
  "event": {
    "name": "invoice_confirmed"
  },
  "data": {
    "id": "INVOICE_ID",
    "price": 100.00,
    "currency": "USD",
    "status": "confirmed"
  }
}
```

## Error Handling

The webhook system implements robust error handling:

1. **Invalid Signature**: Returns 401 Unauthorized
2. **Processing Errors**: Returns 500 but logs details
3. **Missing Transaction**: Logs warning, returns success
4. **Database Errors**: Automatic rollback, error logged

## Monitoring

Monitor webhook processing via logs:
- Successful processing: INFO level
- Missing transactions: WARNING level
- Processing errors: ERROR level

Key metrics to monitor:
- Webhook processing time
- Signature verification failures
- Transaction update success rate
- Notification delivery rate

## Configuration

### Environment Variables
```env
# Coinbase Commerce
COINBASE_WEBHOOK_SECRET=your_webhook_secret

# BitPay
BITPAY_WEBHOOK_SECRET=your_webhook_secret
```

### Database Requirements
- Transaction must have `external_reference` matching payment ID
- Transaction status must be updateable
- Metadata field for storing webhook data

## Best Practices

1. **Idempotency**: Webhooks may be sent multiple times
   - Check transaction status before updating
   - Use external_reference as unique identifier

2. **Async Processing**: For high-volume webhooks
   - Queue webhook payloads
   - Process asynchronously

3. **Retry Logic**: Handle temporary failures
   - Implement exponential backoff
   - Set maximum retry attempts

4. **Logging**: Comprehensive logging for debugging
   - Log all webhook receipts
   - Log signature verification results
   - Log transaction updates

5. **Security**: Never trust webhook data
   - Always verify signatures
   - Validate data integrity
   - Check transaction ownership