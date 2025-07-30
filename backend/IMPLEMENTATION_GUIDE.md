# Implementation Guide for Secondary Features

## Quick Start for Each Feature

### 1. API Key Management (Continuing Work)

**Current Issues to Fix:**
```python
# In api_key_service.py, update list_api_keys to return proper response
async def list_api_keys(db: AsyncSession, user_id: str, agency_id: Optional[str] = None):
    # Add proper response formatting
    # Handle the case where agency_id is None
```

**Missing Endpoints:**
```python
# Add to api/v1/endpoints/api_keys.py
@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    update_data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update API key details (name, description, scopes)."""
    # Implementation needed
```

### 2. Session Management

**Create Service:**
```python
# core/application/session_service.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import Session
from core.redis import redis_client

class SessionService:
    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: int,
        ip_address: str,
        user_agent: str
    ) -> Session:
        """Create a new session."""
        pass
    
    @staticmethod
    async def list_user_sessions(
        db: AsyncSession,
        user_id: int
    ) -> List[Session]:
        """List all active sessions for a user."""
        pass
    
    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        session_id: str,
        user_id: int
    ) -> bool:
        """Revoke a specific session."""
        pass
```

**Create Endpoints:**
```python
# api/v1/endpoints/sessions.py
from fastapi import APIRouter, Depends
from core.dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active sessions."""
    pass
```

### 3. Bulk Operations

**Create Service:**
```python
# core/application/bulk_service.py
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from celery import group

class BulkOperationService:
    @staticmethod
    async def send_bulk_messages(
        db: AsyncSession,
        message_data: Dict[str, Any],
        recipient_ids: List[int]
    ) -> Dict[str, Any]:
        """Send messages in bulk."""
        # Use Celery for async processing
        pass
```

### 4. Media Upload

**Create Service:**
```python
# core/application/media_service.py
import boto3
from typing import Dict, Any

class MediaUploadService:
    def __init__(self):
        self.s3_client = boto3.client('s3')
    
    async def generate_upload_url(
        self,
        file_name: str,
        file_type: str,
        file_size: int
    ) -> Dict[str, Any]:
        """Generate presigned URL for upload."""
        # Validate file type and size
        # Generate presigned URL
        pass
```

### 5. Reports

**Fix Existing Service:**
```python
# In core/reporting/report_builder.py
# Fix the parameter order issue (line 317)
async def get_report_data(
    self,
    report: Report,
    session: AsyncSession,
    parameters: Optional[Dict[str, Any]] = None  # parameters should be last
) -> pd.DataFrame:
```

### 6. ML Analytics

**Create Service:**
```python
# core/application/ml_service.py
from typing import Dict, Any, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class MLAnalyticsService:
    @staticmethod
    async def analyze_conversation_insights(
        conversation_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Extract insights from conversation."""
        # Topic modeling
        # Engagement analysis
        pass
```

### 7. Fraud Detection

**Create Service:**
```python
# core/application/fraud_service.py
from typing import Dict, Any
import asyncio
from datetime import datetime

class FraudDetectionService:
    @staticmethod
    async def check_transaction(
        transaction_data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Check transaction for fraud indicators."""
        # Velocity checks
        # Pattern matching
        # ML scoring
        pass
```

### 8. Rate Limiting

**Create Service:**
```python
# core/application/rate_limit_service.py
from core.redis import redis_client
from typing import Optional

class RateLimitService:
    @staticmethod
    async def check_rate_limit(
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, int]:
        """Check if rate limit exceeded."""
        # Use Redis for distributed rate limiting
        pass
```

### 9. Push Notifications

**Create Service:**
```python
# core/application/notification_service.py
from firebase_admin import messaging
from typing import List, Dict, Any

class PushNotificationService:
    @staticmethod
    async def register_device(
        user_id: int,
        device_token: str,
        platform: str
    ) -> bool:
        """Register device for push notifications."""
        pass
```

### 10. Monitoring

**Create Service:**
```python
# core/application/monitoring_service.py
from prometheus_client import Counter, Histogram, Gauge
import psutil

class MonitoringService:
    # Metrics
    request_count = Counter('http_requests_total', 'Total HTTP requests')
    request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
    
    @staticmethod
    async def collect_metrics() -> Dict[str, Any]:
        """Collect system and application metrics."""
        pass
```

## Common Patterns

### Error Handling
```python
from core.exceptions import NotFoundError, ValidationError

try:
    result = await service_method()
except NotFoundError:
    raise HTTPException(status_code=404, detail="Resource not found")
except ValidationError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### Authentication
```python
from core.dependencies import get_current_user, require_role

# Basic auth
current_user: User = Depends(get_current_user)

# Role-based auth
current_user: User = Depends(require_role(UserRole.ADMIN))
```

### Database Transactions
```python
async with db.begin():
    # Multiple operations in transaction
    await db.execute(stmt1)
    await db.execute(stmt2)
    # Auto-commit on success, rollback on error
```

### Caching
```python
from core.redis import redis_client

# Cache result
await redis_client.setex(
    f"report:{report_id}",
    3600,  # 1 hour TTL
    json.dumps(report_data)
)

# Get cached result
cached = await redis_client.get(f"report:{report_id}")
if cached:
    return json.loads(cached)
```

### Background Tasks
```python
from celery import current_app

# Queue background task
task = current_app.send_task(
    'tasks.process_bulk_messages',
    args=[message_ids]
)
```

## Testing Each Feature

### Unit Tests
```python
# tests/test_api_keys.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/api-keys/",
        json={"name": "Test Key", "scopes": ["read"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    assert "key" in response.json()
```

### Integration Tests
```python
# tests/integration/test_session_flow.py
@pytest.mark.asyncio
async def test_session_lifecycle(client: AsyncClient):
    # Login
    # List sessions
    # Revoke session
    # Verify revoked
    pass
```

## Deployment Considerations

### Environment Variables
```env
# Add to .env
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_BUCKET_NAME=agency-dark-media
FCM_SERVER_KEY=xxx
REDIS_URL=redis://localhost:6379/0
```

### Database Migrations
```bash
# Create migration for new models
alembic revision --autogenerate -m "Add session tracking"
alembic upgrade head
```

### Docker Updates
```dockerfile
# Add new dependencies to requirements.txt
boto3==1.26.137
firebase-admin==6.1.0
prometheus-client==0.16.0
scikit-learn==1.2.2
```

## Monitoring Progress

### Metrics to Track
- Endpoint response times
- Error rates per endpoint
- API key usage patterns
- Session duration and activity
- Bulk operation success rates

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Structured logging
logger.info(
    "api_key_created",
    extra={
        "user_id": user_id,
        "key_id": key_id,
        "scopes": scopes
    }
)
```