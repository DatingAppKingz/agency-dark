# Celery Background Job Processing Setup

## Overview

AgencyDark uses Celery for handling background tasks including:
- Media file processing (images, videos)
- Data exports (CSV, JSON, Excel)
- Email and SMS notifications
- Scheduled maintenance tasks
- Analytics processing
- Financial report generation

## Architecture

### Queues

The system uses multiple queues for different task priorities and types:

1. **default** - General purpose tasks
2. **high_priority** - Urgent tasks requiring immediate processing
3. **media** - Media file processing (images, videos)
4. **sync** - Platform synchronization tasks
5. **notifications** - Email, SMS, and push notifications
6. **analytics** - Analytics calculations and aggregations
7. **long_running** - Tasks that may take extended time
8. **export** - Data export operations

### Workers

Different worker configurations for optimal performance:

1. **General Worker** - Handles default, high_priority, analytics, notifications
2. **Media Worker** - Dedicated to media processing with fewer concurrent tasks
3. **Long Running Worker** - Handles exports and maintenance with single concurrency

## Setup Instructions

### 1. Environment Variables

Add to your `.env` file:

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_ALWAYS_EAGER=False  # Set to True for testing without Celery
TIMEZONE=UTC

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TLS=True
EMAIL_FROM=noreply@agencydark.com

# AWS S3 (for media storage)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=agencydark-media

# Twilio (for SMS)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Flower (Celery monitoring)
FLOWER_USER=admin
FLOWER_PASSWORD=secure-password
```

### 2. Start Workers

#### Development (Single Machine)

```bash
# Terminal 1: Start Celery worker
cd backend
celery -A celery_worker worker --loglevel=info

# Terminal 2: Start Celery beat (scheduler)
cd backend
celery -A celery_worker beat --loglevel=info

# Terminal 3: Start Flower (monitoring)
cd backend
celery -A celery_worker flower --port=5555
```

#### Production (Docker Compose)

```bash
# Start all Celery services
docker-compose -f docker-compose.yml -f docker-compose.celery.yml up -d

# Scale workers as needed
docker-compose -f docker-compose.yml -f docker-compose.celery.yml up -d --scale celery-worker=3
```

#### Production (Supervisor)

```bash
# Install supervisor
sudo apt-get install supervisor

# Copy configuration
sudo cp supervisord.conf /etc/supervisor/conf.d/agencydark.conf

# Start services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

## Task Examples

### 1. Export Agency Data

```python
from tasks.export_tasks import export_agency_data

# Create export task
task = export_agency_data.delay(
    agency_id="123",
    user_id="456",
    export_options={
        "format": "json",
        "include_media": False,
        "date_from": "2024-01-01",
        "date_to": "2024-12-31"
    }
)

# Check status
print(f"Task ID: {task.id}")
print(f"Status: {task.status}")
```

### 2. Process Media File

```python
from tasks.media_tasks import process_image

# Process uploaded image
task = process_image.delay(
    media_id="789",
    processing_options={
        "watermark": True,
        "optimize": True
    }
)
```

### 3. Send Email Notification

```python
from tasks.notification_tasks import send_email

# Send email
task = send_email.delay(
    to_email="user@example.com",
    subject="Welcome to AgencyDark",
    template_name="welcome",
    context={
        "user_name": "John Doe",
        "agency_name": "My Agency"
    }
)
```

## Monitoring

### Flower Dashboard

Access the Flower dashboard at `http://localhost:5555` to:
- Monitor active tasks
- View task history
- Check worker status
- Inspect queue lengths
- View task details and results

### API Endpoints

The application provides REST endpoints for task management:

```bash
# List tasks
GET /api/v1/tasks

# Get task status
GET /api/v1/tasks/{task_id}

# Cancel task
DELETE /api/v1/tasks/{task_id}

# Get task statistics
GET /api/v1/tasks/stats/summary
```

## Scheduled Tasks

The following tasks run automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| cleanup-expired-shares | Every hour | Remove expired media share links |
| process-pending-media | Every 5 minutes | Process uploaded media files |
| sync-health-check | Every 10 minutes | Check sync service health |
| daily-analytics-report | Daily at 1 AM | Generate analytics reports |
| cleanup-old-notifications | Daily at 2 AM | Remove old notifications |
| update-storage-quotas | Every 30 minutes | Update storage usage |
| retry-failed-tasks | Every 15 minutes | Retry failed tasks |
| weekly-summary | Monday at 9 AM | Send weekly summaries |

## Best Practices

### 1. Task Design

- Keep tasks idempotent (can be safely retried)
- Use soft time limits to handle timeouts gracefully
- Store task IDs in database for tracking
- Return structured results for easy processing

### 2. Error Handling

```python
@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600
)
def my_task(self, param):
    try:
        # Task logic here
        pass
    except SoftTimeLimitExceeded:
        # Handle timeout gracefully
        cleanup()
        raise
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

### 3. Performance

- Use appropriate queue for task type
- Set concurrency based on task requirements
- Monitor memory usage for media processing
- Use connection pooling for external services

## Troubleshooting

### Common Issues

1. **Tasks not processing**
   - Check Redis connection
   - Verify worker is running
   - Check queue routing

2. **Memory issues with media processing**
   - Reduce worker concurrency
   - Increase worker memory limits
   - Process large files in chunks

3. **Email/SMS not sending**
   - Verify credentials in environment
   - Check service quotas/limits
   - Review error logs

### Useful Commands

```bash
# Check active workers
celery -A celery_worker inspect active

# Check scheduled tasks
celery -A celery_worker inspect scheduled

# Purge all tasks from queue
celery -A celery_worker purge

# Check queue lengths
celery -A celery_worker inspect stats
```

## Security Considerations

1. **Task Results** - Contains sensitive data, ensure Redis is secured
2. **File Processing** - Always validate and scan uploaded files
3. **API Keys** - Store securely in environment variables
4. **Export Files** - Implement access controls and expiration

## Scaling

### Horizontal Scaling

1. Add more workers for increased throughput
2. Use separate workers for different task types
3. Consider RabbitMQ for high-volume scenarios

### Vertical Scaling

1. Increase worker concurrency for I/O bound tasks
2. Reduce concurrency for CPU/memory intensive tasks
3. Monitor and adjust based on metrics