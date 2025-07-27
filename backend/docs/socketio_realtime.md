# Socket.IO Real-time Communication Documentation

## Overview

The Socket.IO implementation provides real-time bidirectional communication for:
- Live payment tracking and updates
- Instant notifications for important events
- Real-time dashboard metrics
- Chat messaging between models and fans
- Financial transaction monitoring

## Architecture

### Namespaces

The system is organized into specialized namespaces:

1. **Main Namespace** (`/`) - Authentication and general events
2. **Chat Namespace** (`/chat`) - Fan messaging and chat management
3. **Notifications Namespace** (`/notifications`) - System notifications and alerts
4. **Dashboard Namespace** (`/dashboard`) - Live dashboard updates
5. **Financial Namespace** (`/financial`) - Payment tracking and financial events

### Authentication

All connections require JWT authentication:

```javascript
const socket = io('http://localhost:8000', {
  auth: {
    token: 'your-jwt-token'
  }
});
```

## Financial Namespace Features

### 1. Payment Tracking

Track individual payment status in real-time:

```javascript
// Connect to financial namespace
const financial = io('/financial', {
  auth: { token: authToken }
});

// Start tracking a payment
financial.emit('track_payment', {
  transaction_id: 'transaction-uuid'
});

// Listen for updates
financial.on('payment_status_update', (data) => {
  console.log('Payment status:', data.status);
  console.log('Amount:', data.amount, data.currency);
  console.log('Processed at:', data.processed_at);
});

// Stop tracking
financial.emit('stop_tracking_payment', {
  transaction_id: 'transaction-uuid'
});
```

### 2. Payout Notifications

Subscribe to payout status updates:

```javascript
// Subscribe to model payouts
financial.emit('subscribe_payouts', {
  model_id: 'model-uuid'
});

// Listen for payout updates
financial.on('payout_update', (data) => {
  console.log('Payout:', data.payout_id);
  console.log('Status:', data.status);
  console.log('Amount:', data.amount);
});
```

### 3. Payment Statistics

Get real-time payment statistics:

```javascript
// Request stats
financial.emit('get_payment_stats', {
  period: 'today', // 'today', 'week', 'month'
  model_id: 'model-uuid' // optional
});

// Receive stats
financial.on('payment_stats', (stats) => {
  console.log('Total transactions:', stats.total_transactions);
  console.log('Completed amount:', stats.completed_amount);
  console.log('Pending amount:', stats.pending_amount);
});
```

## Notifications Namespace Features

### 1. Metric Subscriptions

Subscribe to real-time metrics:

```javascript
const notifications = io('/notifications', {
  auth: { token: authToken }
});

// Subscribe to metrics
notifications.emit('subscribe_metrics', {
  model_id: 'model-uuid',
  metrics: [
    'revenue_today',
    'active_subscribers',
    'messages_today',
    'online_chatters',
    'unclaimed_fans'
  ],
  interval: 5 // seconds
});

// Receive updates
notifications.on('metrics_update', (data) => {
  console.log('Model:', data.model_id);
  console.log('Metrics:', data.data);
  console.log('Timestamp:', data.timestamp);
});

// Unsubscribe
notifications.emit('unsubscribe_metrics', {
  model_id: 'model-uuid'
});
```

### 2. Event Subscriptions

Subscribe to real-time events:

```javascript
// Subscribe to events
notifications.emit('subscribe_events', {
  event_types: [
    'new_subscriber',
    'tip_received',
    'payment_confirmed'
  ],
  model_ids: ['model-uuid-1', 'model-uuid-2'] // optional
});

// Event handlers
notifications.on('new_subscriber', (data) => {
  console.log('New subscriber:', data.username);
});

notifications.on('tip_received', (data) => {
  console.log('Tip amount:', data.amount);
  console.log('From:', data.from);
});

notifications.on('payment_confirmed', (data) => {
  console.log('Payment confirmed:', data.transaction_id);
});
```

## Dashboard Namespace

Get dashboard summaries:

```javascript
const dashboard = io('/dashboard', {
  auth: { token: authToken }
});

// Request summary
dashboard.emit('request_summary', {
  period: 'today' // 'today', 'week', 'month'
});

// Receive summary
dashboard.on('dashboard_summary', (summary) => {
  console.log('Period:', summary.period);
  console.log('Total models:', summary.total_models);
  console.log('Agency revenue:', summary.agency_revenue);
});
```

## Room Structure

### Automatic Room Assignment

Users are automatically joined to rooms based on their role and associations:

- `user:{user_id}` - Personal notifications
- `agency:{agency_id}` - Agency-wide notifications
- `role:{role}` - Role-based broadcasts
- `financial:agency:{agency_id}` - Financial updates for agency
- `financial:all` - Global financial updates (super admin only)
- `payouts:model:{model_id}` - Model-specific payout updates

### Broadcasting Events

Server-side broadcasting to rooms:

```python
# Send to specific agency
await sio.emit(
    'payment_update',
    data,
    room=f'financial:agency:{agency_id}',
    namespace='/financial'
)

# Send to all super admins
await sio.emit(
    'system_alert',
    data,
    room='role:super_admin'
)
```

## Client Implementation Examples

### React Hook Example

```javascript
import { useEffect, useState } from 'react';
import io from 'socket.io-client';

export function usePaymentTracking(transactionId) {
  const [status, setStatus] = useState(null);
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    const financialSocket = io('/financial', {
      auth: { token: getAuthToken() }
    });

    financialSocket.on('connect', () => {
      financialSocket.emit('track_payment', { transaction_id: transactionId });
    });

    financialSocket.on('payment_status_update', (data) => {
      if (data.transaction_id === transactionId) {
        setStatus(data);
      }
    });

    setSocket(financialSocket);

    return () => {
      financialSocket.emit('stop_tracking_payment', { transaction_id: transactionId });
      financialSocket.disconnect();
    };
  }, [transactionId]);

  return status;
}
```

### Vue.js Example

```javascript
export default {
  data() {
    return {
      socket: null,
      metrics: {}
    };
  },
  
  mounted() {
    this.socket = io('/notifications', {
      auth: { token: this.$store.state.auth.token }
    });
    
    this.socket.emit('subscribe_metrics', {
      model_id: this.modelId,
      metrics: ['revenue_today', 'active_subscribers'],
      interval: 10
    });
    
    this.socket.on('metrics_update', (data) => {
      this.metrics = data.data;
    });
  },
  
  beforeDestroy() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
};
```

## Error Handling

All namespaces emit error events:

```javascript
socket.on('error', (error) => {
  console.error('Socket error:', error.message);
});
```

Common errors:
- `Access denied` - Insufficient permissions
- `Transaction not found` - Invalid transaction ID
- `Model not found` - Invalid model ID
- `Authentication failed` - Invalid or expired token

## Performance Considerations

### Connection Management
- Reuse socket connections across components
- Properly disconnect when components unmount
- Use namespace-specific connections only when needed

### Subscription Management
- Unsubscribe from events when no longer needed
- Use appropriate update intervals for metrics
- Batch multiple subscriptions when possible

### Scaling
- Redis adapter enables horizontal scaling
- Events are distributed across multiple servers
- Room-based broadcasting ensures efficient message delivery

## Security

### Authentication
- All connections require valid JWT tokens
- Tokens are validated on each connection
- Sessions are terminated on invalid tokens

### Authorization
- Room access is role-based
- Financial data requires agency membership
- Model data requires proper permissions

### Data Validation
- All incoming events are validated
- SQL injection prevention
- XSS protection on message content

## Monitoring

The system includes performance monitoring:

```python
# Server logs metrics every 5 minutes
Socket.IO Metrics - Connections: 45, Sent: 1523, Received: 892, Errors: 2
```

Monitor:
- Active connections per namespace
- Message throughput
- Error rates
- Room membership

## Testing

### Unit Testing
```python
# Test namespace logic
async def test_payment_tracking():
    namespace = FinancialNamespace()
    await namespace.on_track_payment(sid, data)
    assert transaction_id in namespace.payment_trackers[sid]
```

### Integration Testing
```python
# Test full flow
async def test_payment_notification_flow():
    client = socketio.AsyncClient()
    await client.connect(url, auth={'token': token})
    
    received = []
    @client.on('payment_update')
    def on_update(data):
        received.append(data)
    
    # Trigger payment update
    await notify_payment_status(transaction, sio)
    
    assert len(received) > 0
```

## Troubleshooting

### Connection Issues
1. Check authentication token validity
2. Verify CORS settings
3. Ensure Redis is running (for multi-server setup)
4. Check firewall/proxy settings

### Missing Events
1. Verify namespace subscription
2. Check room membership
3. Ensure proper permissions
4. Review server logs for errors

### Performance Issues
1. Reduce metric update frequency
2. Limit concurrent subscriptions
3. Use connection pooling
4. Enable compression