# Notification System Documentation

## Overview

AgencyDark's notification system provides multi-channel communication capabilities including email, SMS, push notifications, in-app notifications, and webhooks. The system features user preferences, templates, scheduling, and comprehensive tracking.

## Architecture

### Components

1. **Notification Service** - Core service for sending notifications
2. **Celery Tasks** - Background processing for async delivery
3. **Database Models** - Storage for notifications, templates, and preferences
4. **REST API** - Endpoints for managing notifications
5. **Frontend Components** - UI for notification center and preferences

### Notification Types

- **Email** - HTML/text emails via SMTP
- **SMS** - Text messages via Twilio
- **Push** - Mobile push notifications (FCM/APNS)
- **In-App** - Real-time notifications via WebSocket
- **Webhook** - HTTP callbacks to external services

### Features

- Template-based notifications
- Bulk notification sending
- User preference management
- Quiet hours support
- Digest notifications
- Retry logic with exponential backoff
- Delivery tracking and analytics
- Multi-language support (when combined with i18n)

## Setup Instructions

### 1. Environment Configuration

Add to your `.env` file:

```bash
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=True
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@agencydark.com

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Push Notifications (optional)
FCM_SERVER_KEY=your-fcm-key
APNS_CERT_PATH=/path/to/cert.pem
APNS_KEY_PATH=/path/to/key.pem
```

### 2. Email Provider Setup

#### Gmail
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use app password in SMTP_PASSWORD

#### SendGrid
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

#### AWS SES
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-ses-smtp-username
SMTP_PASSWORD=your-ses-smtp-password
```

### 3. SMS Provider Setup (Twilio)

1. Create Twilio account
2. Get Account SID and Auth Token
3. Purchase phone number
4. Configure webhook URLs for delivery status

### 4. Database Migration

```bash
cd backend
alembic upgrade notifications_001
```

### 5. Start Notification Workers

```bash
# Start notification worker
celery -A celery_worker worker --queues=notifications --loglevel=info

# Or with supervisor
[program:celery-notifications]
command=celery -A celery_worker worker --queues=notifications --loglevel=info
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
```

## Usage

### 1. Sending Notifications

#### Simple Email
```python
from tasks.notification_tasks import send_email

send_email.delay(
    to_email="user@example.com",
    subject="Welcome to AgencyDark",
    content="Thanks for signing up!",
    html_content="<h1>Thanks for signing up!</h1>"
)
```

#### Using Templates
```python
from schemas.notification import NotificationCreate
from services.notification_service import NotificationService

notification_data = NotificationCreate(
    type="email",
    user_id=user_id,
    template_id=template_id,
    template_data={
        "user_name": "John Doe",
        "activation_link": "https://..."
    }
)

notification = await service.create_notification(
    notification_data,
    agency_id
)
```

#### Bulk Notifications
```python
from schemas.notification import BulkNotificationCreate

bulk_data = BulkNotificationCreate(
    type="email",
    subject="New Feature Announcement",
    content="Check out our new features...",
    user_filters={"is_active": True, "role": "agency_admin"}
)

result = await service.create_bulk_notifications(
    bulk_data,
    agency_id
)
```

### 2. Notification Templates

Templates use Jinja2 syntax:

```html
<!-- welcome.html -->
<h1>Welcome {{ user_name }}!</h1>
<p>Your account has been created.</p>
<a href="{{ activation_link }}">Activate Account</a>
```

Create template via API:
```bash
POST /api/v1/notifications/templates
{
  "name": "welcome_email",
  "type": "email",
  "subject_template": "Welcome to {{ agency_name }}",
  "content_template": "Hello {{ user_name }}...",
  "html_template": "<h1>Hello {{ user_name }}</h1>...",
  "variables_schema": {
    "user_name": {"type": "string", "required": true},
    "agency_name": {"type": "string", "required": true}
  }
}
```

### 3. User Preferences

Users can configure:
- Channel preferences (email, SMS, push, in-app)
- Category preferences (marketing, transactions, etc.)
- Digest settings (daily, weekly, monthly)
- Quiet hours
- Preferred contact methods

```javascript
// Update preferences
await notificationApi.updatePreferences({
  email_enabled: true,
  sms_enabled: false,
  categories: {
    marketing: false,
    transactions: true,
    security: true
  },
  digest_enabled: true,
  digest_frequency: 'weekly',
  quiet_hours_enabled: true,
  quiet_hours_start: '22:00',
  quiet_hours_end: '08:00',
  timezone: 'America/New_York'
});
```

### 4. Scheduled Notifications

Schedule notifications for future delivery:

```python
notification_data = NotificationCreate(
    type="email",
    user_id=user_id,
    subject="Reminder",
    content="Don't forget about...",
    scheduled_at=datetime.utcnow() + timedelta(days=1)
)
```

### 5. Tracking and Analytics

Track notification events:
- Sent
- Delivered
- Opened
- Clicked
- Bounced
- Failed

```javascript
// Track click
await notificationApi.trackClick(notificationId, clickedLink);

// Get statistics
const stats = await notificationApi.getStats({
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});
```

## Frontend Integration

### 1. Notification Center

```jsx
import { NotificationCenter } from '@/components/notifications/NotificationCenter';

// Add to header/navbar
<NotificationCenter />
```

### 2. Preferences Page

```jsx
import { NotificationPreferences } from '@/components/notifications/NotificationPreferences';

// Preferences page
<NotificationPreferences />
```

### 3. Real-time Notifications

WebSocket integration for in-app notifications:

```javascript
// Subscribe to notifications
socket.on('notification', (data) => {
  // Show notification toast
  toast({
    title: data.subject,
    description: data.content,
  });
  
  // Update notification count
  updateUnreadCount();
});
```

## Email Templates

### Available Templates

1. **welcome.html** - New user welcome
2. **daily_summary.html** - Daily performance summary
3. **alert.html** - System alerts
4. **password_reset.html** - Password reset
5. **payment_receipt.html** - Payment confirmations
6. **new_message.html** - New message notifications

### Creating Custom Templates

1. Create HTML file in `/backend/templates/emails/`
2. Extend base template
3. Use template variables
4. Test with preview endpoint

```html
{% extends "base.html" %}

{% block title %}Custom Notification{% endblock %}

{% block content %}
<h2>{{ title }}</h2>
<p>{{ message }}</p>

{% if items %}
<ul>
  {% for item in items %}
  <li>{{ item.name }} - {{ item.value }}</li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}
```

## Best Practices

### 1. Template Design
- Use responsive HTML
- Include plain text version
- Test across email clients
- Keep subject lines concise
- Use preheader text

### 2. Delivery Optimization
- Authenticate domains (SPF, DKIM)
- Monitor sender reputation
- Handle bounces properly
- Respect unsubscribe requests
- Use proper from addresses

### 3. User Experience
- Allow granular preferences
- Provide unsubscribe links
- Send at appropriate times
- Batch similar notifications
- Use clear CTAs

### 4. Performance
- Queue notifications asynchronously
- Batch bulk sends
- Implement rate limiting
- Monitor delivery rates
- Handle retries properly

## Troubleshooting

### Common Issues

1. **Emails not sending**
   - Check SMTP credentials
   - Verify firewall settings
   - Check spam folders
   - Review email logs

2. **SMS failures**
   - Verify Twilio credentials
   - Check phone number format
   - Review Twilio logs
   - Check account balance

3. **Push notifications not received**
   - Verify device tokens
   - Check certificate validity
   - Review platform logs
   - Test with debug tools

4. **High bounce rates**
   - Verify email addresses
   - Check content for spam triggers
   - Review sender reputation
   - Implement email validation

### Debug Commands

```bash
# Test email sending
python -m pytest tests/test_notifications.py::test_email_sending

# Check Celery tasks
celery -A celery_worker inspect active

# View notification logs
tail -f logs/notifications.log

# Test SMTP connection
python scripts/test_smtp.py
```

## Security Considerations

1. **Email Security**
   - Use TLS for SMTP
   - Implement DKIM/SPF
   - Validate email addresses
   - Sanitize template inputs

2. **SMS Security**
   - Validate phone numbers
   - Rate limit sends
   - Monitor for abuse
   - Use secure webhooks

3. **Data Privacy**
   - Encrypt sensitive data
   - Respect user preferences
   - Implement data retention
   - Log appropriately

4. **API Security**
   - Authenticate requests
   - Rate limit endpoints
   - Validate inputs
   - Monitor usage

## Monitoring

### Metrics to Track

1. **Delivery Metrics**
   - Send rate
   - Delivery rate
   - Bounce rate
   - Open rate
   - Click rate

2. **Performance Metrics**
   - Queue length
   - Processing time
   - Error rate
   - Retry count

3. **User Metrics**
   - Preference changes
   - Unsubscribe rate
   - Engagement rate
   - Channel preferences

### Alerts to Configure

- High bounce rate (>5%)
- Low delivery rate (<95%)
- Queue backup (>1000 items)
- Provider errors
- Rate limit exceeded