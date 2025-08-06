# Security Testing Guide

## Overview

This guide provides comprehensive instructions for testing the security features of the Agency Dark platform. It covers unit tests, integration tests, penetration testing, and compliance verification.

## Table of Contents

1. [Test Environment Setup](#test-environment-setup)
2. [Unit Testing](#unit-testing)
3. [Integration Testing](#integration-testing)
4. [Penetration Testing](#penetration-testing)
5. [Performance Testing](#performance-testing)
6. [Compliance Testing](#compliance-testing)
7. [Security Regression Testing](#security-regression-testing)
8. [Test Data Management](#test-data-management)
9. [CI/CD Security Testing](#cicd-security-testing)
10. [Test Reports](#test-reports)

## Test Environment Setup

### Prerequisites

```bash
# Install testing dependencies
pip install -r requirements-test.txt

# Testing tools
pip install pytest pytest-asyncio pytest-cov
pip install locust  # Load testing
pip install safety bandit  # Security scanning
pip install faker factory-boy  # Test data generation
```

### Environment Configuration

```bash
# Create test environment file
cat > .env.test << EOF
# Test Database
DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/agencydark_test
REDIS_URL=redis://localhost:6379/1

# Test Security Settings
JWT_SECRET_KEY=test_secret_key_for_testing_only
ENCRYPTION_KEY=test_encryption_key
API_KEY_SALT=test_salt

# Disable external services in tests
DISABLE_EXTERNAL_SERVICES=true
DISABLE_RATE_LIMITING=false  # Keep enabled for testing
DISABLE_AUDIT_LOGGING=false

# Test specific settings
TEST_MODE=true
LOG_LEVEL=DEBUG
EOF
```

### Test Database Setup

```sql
-- Create test database
CREATE DATABASE agencydark_test;

-- Create test user
CREATE USER test_user WITH PASSWORD 'test_pass';
GRANT ALL PRIVILEGES ON DATABASE agencydark_test TO test_user;

-- Run migrations
alembic -c alembic.test.ini upgrade head
```

## Unit Testing

### Permission System Tests

```python
# tests/unit/security/test_permissions.py
import pytest
from datetime import datetime, timedelta
from models.user import User, UserRole
from models.feature_permission import FeaturePermission, FeatureType
from core.security.feature_permissions.service import feature_permission_service

class TestPermissionEvaluation:
    @pytest.fixture
    def admin_user(self):
        return User(
            id=uuid.uuid4(),
            email="admin@test.com",
            role=UserRole.ADMIN
        )
    
    @pytest.fixture
    def basic_user(self):
        return User(
            id=uuid.uuid4(),
            email="user@test.com",
            role=UserRole.USER
        )
    
    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self, admin_user, mock_db):
        """Test that admin users have all permissions."""
        permission = FeaturePermission(
            feature_type=FeatureType.REPORTS,
            allowed_actions=["*"],
            role_id=admin_user.primary_role_id
        )
        
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[permission]
        ):
            allowed, reason = await feature_permission_service.check_feature_permission(
                db=mock_db,
                user=admin_user,
                feature_type=FeatureType.REPORTS,
                action="any_action"
            )
            
            assert allowed is True
            assert reason is None
    
    @pytest.mark.asyncio
    async def test_time_based_access_restriction(self, basic_user, mock_db):
        """Test time-based access restrictions."""
        # Create permission with time restriction (9 AM - 5 PM)
        permission = FeaturePermission(
            feature_type=FeatureType.REPORTS,
            user_id=basic_user.id,
            allowed_actions=["view_report"],
            access_start_time="09:00",
            access_end_time="17:00",
            access_timezone="UTC"
        )
        
        # Mock current time as 8 AM (before allowed time)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 8, 0, 0)
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 8, 0, 0)
            
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[permission]
            ):
                allowed, reason = await feature_permission_service.check_feature_permission(
                    db=mock_db,
                    user=basic_user,
                    feature_type=FeatureType.REPORTS,
                    action="view_report"
                )
                
                assert allowed is False
                assert "outside allowed hours" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_data_sensitivity_check(self, basic_user, mock_db):
        """Test data sensitivity level restrictions."""
        permission = FeaturePermission(
            feature_type=FeatureType.EXPORTS,
            user_id=basic_user.id,
            allowed_actions=["export_data"],
            max_data_sensitivity=DataSensitivity.INTERNAL
        )
        
        # Test export of confidential data (should fail)
        context = {
            "data_sensitivity": DataSensitivity.CONFIDENTIAL,
            "export_format": "csv"
        }
        
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[permission]
        ):
            allowed, reason = await feature_permission_service.check_feature_permission(
                db=mock_db,
                user=basic_user,
                feature_type=FeatureType.EXPORTS,
                action="export_data",
                request_context=context
            )
            
            assert allowed is False
            assert "data sensitivity" in reason.lower()
```

### Rate Limiting Tests

```python
# tests/unit/security/test_rate_limiting.py
import pytest
from core.rate_limit.service import DynamicRateLimitService
from core.rate_limit.algorithms import TokenBucketAlgorithm
from models.rate_limit import RateLimitConfig, RateLimitAlgorithm

class TestRateLimiting:
    @pytest.fixture
    def rate_limiter(self):
        return DynamicRateLimitService()
    
    @pytest.mark.asyncio
    async def test_token_bucket_algorithm(self, mock_redis):
        """Test token bucket rate limiting algorithm."""
        algorithm = TokenBucketAlgorithm(mock_redis)
        
        # Configure: 10 requests per minute, burst of 5
        limit = 10
        window = 60
        burst = 5
        
        # Should allow first 5 requests (burst)
        for i in range(5):
            allowed, info = await algorithm.check_and_update(
                key="test_key",
                limit=limit,
                window_seconds=window,
                burst_size=burst
            )
            assert allowed is True
            assert info["remaining"] == burst - i - 1
        
        # 6th request should fail (burst exhausted)
        allowed, info = await algorithm.check_and_update(
            key="test_key",
            limit=limit,
            window_seconds=window,
            burst_size=burst
        )
        assert allowed is False
        assert info["retry_after"] > 0
    
    @pytest.mark.asyncio
    async def test_cost_based_rate_limiting(self, rate_limiter, mock_db):
        """Test cost-based rate limiting."""
        # Create cost-based rate limit config
        config = RateLimitConfig(
            name="API Cost Limit",
            cost_per_minute=100.0,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        
        with patch.object(
            rate_limiter,
            '_get_applicable_configs',
            return_value=[config]
        ):
            # First request with cost 50 (should succeed)
            with patch.object(
                rate_limiter,
                '_calculate_request_cost',
                return_value=50.0
            ):
                allowed, info = await rate_limiter.check_rate_limit(
                    db=mock_db,
                    identifier="user123",
                    identifier_type="user",
                    endpoint="/api/v1/expensive"
                )
                assert allowed is True
                assert info["remaining_cost"] == 50.0
            
            # Second request with cost 60 (should fail - exceeds budget)
            with patch.object(
                rate_limiter,
                '_calculate_request_cost',
                return_value=60.0
            ):
                allowed, info = await rate_limiter.check_rate_limit(
                    db=mock_db,
                    identifier="user123",
                    identifier_type="user",
                    endpoint="/api/v1/expensive"
                )
                assert allowed is False
                assert "cost limit" in info.get("reason", "").lower()
```

### API Key Security Tests

```python
# tests/unit/security/test_api_keys.py
import pytest
from core.security.api_key_manager import SecureAPIKeyManager

class TestAPIKeySecurity:
    @pytest.fixture
    def api_key_manager(self):
        return SecureAPIKeyManager()
    
    @pytest.mark.asyncio
    async def test_api_key_generation_uniqueness(self, api_key_manager):
        """Test that generated API keys are unique."""
        keys = set()
        for _ in range(100):
            key = api_key_manager._generate_secure_key()
            assert key not in keys
            keys.add(key)
            
            # Check format
            assert key.startswith("sk_")
            assert len(key) == 35  # sk_ + 32 chars
    
    @pytest.mark.asyncio
    async def test_api_key_hashing(self, api_key_manager):
        """Test API key hashing and verification."""
        raw_key = "sk_test_1234567890abcdef"
        
        # Hash the key
        key_hash = api_key_manager._hash_api_key(raw_key)
        
        # Verify properties
        assert key_hash != raw_key  # Not storing plaintext
        assert len(key_hash) == 64  # SHA-256 hex length
        
        # Same key should produce same hash
        key_hash2 = api_key_manager._hash_api_key(raw_key)
        assert key_hash == key_hash2
        
        # Different key should produce different hash
        different_key = "sk_test_different123456"
        different_hash = api_key_manager._hash_api_key(different_key)
        assert different_hash != key_hash
    
    @pytest.mark.asyncio
    async def test_api_key_rotation_reminder(self, api_key_manager, mock_db):
        """Test API key rotation reminders."""
        # Create key that needs rotation (>90 days old)
        old_key = APIKey(
            id=uuid.uuid4(),
            created_at=datetime.utcnow() - timedelta(days=100),
            last_rotated=datetime.utcnow() - timedelta(days=100)
        )
        
        needs_rotation = api_key_manager._needs_rotation(old_key)
        assert needs_rotation is True
        
        # Recent key shouldn't need rotation
        new_key = APIKey(
            id=uuid.uuid4(),
            created_at=datetime.utcnow() - timedelta(days=30),
            last_rotated=datetime.utcnow() - timedelta(days=30)
        )
        
        needs_rotation = api_key_manager._needs_rotation(new_key)
        assert needs_rotation is False
```

## Integration Testing

### Full Security Flow Test

```python
# tests/integration/security/test_security_flow.py
import pytest
from httpx import AsyncClient
from core.security.test_utils import create_test_user, create_test_permissions

class TestSecurityIntegration:
    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, test_client: AsyncClient):
        """Test complete authentication and authorization flow."""
        # 1. Register user
        register_response = await test_client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "password": "SecurePass123!",
            "role": "user"
        })
        assert register_response.status_code == 201
        
        # 2. Login
        login_response = await test_client.post("/api/v1/auth/login", json={
            "email": "newuser@test.com",
            "password": "SecurePass123!"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        # 3. Access protected endpoint
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        protected_response = await test_client.get(
            "/api/v1/users/me",
            headers=headers
        )
        assert protected_response.status_code == 200
        
        # 4. Refresh token
        refresh_response = await test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        })
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        # 5. Logout
        logout_response = await test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
        )
        assert logout_response.status_code == 200
        
        # 6. Verify old token is invalid
        invalid_response = await test_client.get(
            "/api/v1/users/me",
            headers=headers
        )
        assert invalid_response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_permission_enforcement(self, test_client: AsyncClient, test_db):
        """Test permission enforcement across different endpoints."""
        # Create users with different roles
        admin_user = await create_test_user(role=UserRole.ADMIN)
        manager_user = await create_test_user(role=UserRole.MANAGER)
        basic_user = await create_test_user(role=UserRole.USER)
        
        # Create permissions
        await create_test_permissions(test_db)
        
        # Test cases: (user, endpoint, expected_status)
        test_cases = [
            (admin_user, "/api/v1/admin/users", 200),
            (manager_user, "/api/v1/admin/users", 403),
            (basic_user, "/api/v1/admin/users", 403),
            
            (admin_user, "/api/v1/reports/financial", 200),
            (manager_user, "/api/v1/reports/financial", 200),
            (basic_user, "/api/v1/reports/financial", 403),
            
            (admin_user, "/api/v1/export/all-users", 200),
            (manager_user, "/api/v1/export/all-users", 403),
            (basic_user, "/api/v1/export/all-users", 403),
        ]
        
        for user, endpoint, expected_status in test_cases:
            # Login as user
            login_response = await test_client.post("/api/v1/auth/login", json={
                "email": user.email,
                "password": "TestPass123!"
            })
            token = login_response.json()["access_token"]
            
            # Access endpoint
            response = await test_client.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == expected_status, \
                f"User {user.role} accessing {endpoint} - expected {expected_status}, got {response.status_code}"
```

### Rate Limiting Integration Test

```python
# tests/integration/security/test_rate_limiting_integration.py
import pytest
import asyncio
from httpx import AsyncClient

class TestRateLimitingIntegration:
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, test_client: AsyncClient, auth_headers):
        """Test that rate limits are enforced correctly."""
        # Make requests up to the limit
        responses = []
        for i in range(12):  # Assuming limit is 10 per minute
            response = await test_client.get(
                "/api/v1/reports/summary",
                headers=auth_headers
            )
            responses.append(response)
            
            if i < 10:
                assert response.status_code == 200
                assert "X-RateLimit-Remaining" in response.headers
                assert int(response.headers["X-RateLimit-Remaining"]) == 9 - i
            else:
                # Should be rate limited
                assert response.status_code == 429
                assert "X-RateLimit-Retry-After" in response.headers
    
    @pytest.mark.asyncio
    async def test_cost_based_rate_limiting(self, test_client: AsyncClient, auth_headers):
        """Test cost-based rate limiting for expensive operations."""
        # Make a cheap request
        cheap_response = await test_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        assert cheap_response.status_code == 200
        initial_budget = float(cheap_response.headers.get("X-RateLimit-Cost-Remaining", "100"))
        
        # Make an expensive request
        expensive_response = await test_client.post(
            "/api/v1/ml/analyze",
            headers=auth_headers,
            json={"data": "large dataset"}
        )
        assert expensive_response.status_code == 200
        remaining_budget = float(expensive_response.headers.get("X-RateLimit-Cost-Remaining", "0"))
        
        # Verify cost was deducted
        assert remaining_budget < initial_budget
        
        # Exhaust budget
        while remaining_budget > 0:
            response = await test_client.post(
                "/api/v1/ml/analyze",
                headers=auth_headers,
                json={"data": "large dataset"}
            )
            if response.status_code == 429:
                break
            remaining_budget = float(response.headers.get("X-RateLimit-Cost-Remaining", "0"))
        
        # Next request should be rate limited
        limited_response = await test_client.post(
            "/api/v1/ml/analyze",
            headers=auth_headers,
            json={"data": "large dataset"}
        )
        assert limited_response.status_code == 429
```

## Penetration Testing

### SQL Injection Testing

```python
# tests/security/penetration/test_sql_injection.py
import pytest
from httpx import AsyncClient

class TestSQLInjection:
    SQL_INJECTION_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "admin'--",
        "' OR 1=1--",
        "' OR 'a'='a",
        "'; exec xp_cmdshell('dir'); --",
        "' AND 1=(SELECT COUNT(*) FROM users); --"
    ]
    
    @pytest.mark.asyncio
    async def test_login_sql_injection(self, test_client: AsyncClient):
        """Test SQL injection in login endpoint."""
        for payload in self.SQL_INJECTION_PAYLOADS:
            response = await test_client.post("/api/v1/auth/login", json={
                "email": payload,
                "password": "password"
            })
            
            # Should return 400 or 401, never 500 (server error)
            assert response.status_code in [400, 401]
            
            # Check response doesn't leak information
            assert "syntax error" not in response.text.lower()
            assert "sql" not in response.text.lower()
    
    @pytest.mark.asyncio
    async def test_search_sql_injection(self, test_client: AsyncClient, auth_headers):
        """Test SQL injection in search parameters."""
        for payload in self.SQL_INJECTION_PAYLOADS:
            response = await test_client.get(
                f"/api/v1/users/search?q={payload}",
                headers=auth_headers
            )
            
            # Should handle gracefully
            assert response.status_code in [200, 400]
            
            # Verify no database errors exposed
            if response.status_code == 400:
                error = response.json()
                assert "database" not in str(error).lower()
                assert "syntax" not in str(error).lower()
```

### XSS Testing

```python
# tests/security/penetration/test_xss.py
import pytest
from httpx import AsyncClient

class TestXSSPrevention:
    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='javascript:alert(\"XSS\")'></iframe>",
        "<input type='text' value='x' onmouseover='alert(\"XSS\")'>"
    ]
    
    @pytest.mark.asyncio
    async def test_user_input_sanitization(self, test_client: AsyncClient, auth_headers):
        """Test XSS prevention in user inputs."""
        for payload in self.XSS_PAYLOADS:
            # Test in user profile update
            response = await test_client.put("/api/v1/users/me", 
                headers=auth_headers,
                json={
                    "display_name": payload,
                    "bio": payload
                }
            )
            
            if response.status_code == 200:
                # Verify payload was sanitized
                user_data = response.json()
                assert "<script>" not in user_data.get("display_name", "")
                assert "javascript:" not in user_data.get("bio", "")
                
                # Fetch and verify
                get_response = await test_client.get(
                    "/api/v1/users/me",
                    headers=auth_headers
                )
                user_data = get_response.json()
                
                # Check sanitization
                for field in ["display_name", "bio"]:
                    value = user_data.get(field, "")
                    assert "<script>" not in value
                    assert "onerror=" not in value
                    assert "javascript:" not in value
```

### Authentication Bypass Testing

```python
# tests/security/penetration/test_auth_bypass.py
import pytest
import jwt
from httpx import AsyncClient

class TestAuthenticationBypass:
    @pytest.mark.asyncio
    async def test_jwt_algorithm_confusion(self, test_client: AsyncClient):
        """Test JWT algorithm confusion attack."""
        # Get a valid token first
        login_response = await test_client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        valid_token = login_response.json()["access_token"]
        
        # Decode without verification
        decoded = jwt.decode(valid_token, options={"verify_signature": False})
        
        # Try to create token with 'none' algorithm
        try:
            forged_token = jwt.encode(decoded, None, algorithm="none")
            response = await test_client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {forged_token}"}
            )
            assert response.status_code == 401
        except:
            pass  # Good - library prevents this
        
        # Try to use HS256 instead of RS256
        forged_token = jwt.encode(decoded, "secret", algorithm="HS256")
        response = await test_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {forged_token}"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_session_fixation(self, test_client: AsyncClient):
        """Test session fixation attack prevention."""
        # Create a session
        session_id = "attacker-controlled-session-id"
        
        # Try to login with fixed session ID
        response = await test_client.post("/api/v1/auth/login", 
            json={
                "email": "test@example.com",
                "password": "TestPass123!"
            },
            cookies={"session_id": session_id}
        )
        
        # Verify new session ID was generated
        if "session_id" in response.cookies:
            assert response.cookies["session_id"] != session_id
```

## Performance Testing

### Security Performance Tests

```python
# tests/performance/test_security_performance.py
import pytest
import asyncio
import time
from statistics import mean, stdev

class TestSecurityPerformance:
    @pytest.mark.asyncio
    async def test_permission_check_performance(self, mock_db, create_users):
        """Test permission check performance under load."""
        # Create 100 users with various permissions
        users = await create_users(100)
        
        # Measure permission check times
        check_times = []
        
        for user in users:
            start = time.time()
            
            allowed, reason = await feature_permission_service.check_feature_permission(
                db=mock_db,
                user=user,
                feature_type=FeatureType.REPORTS,
                action="view_report"
            )
            
            check_times.append((time.time() - start) * 1000)  # ms
        
        # Analyze results
        avg_time = mean(check_times)
        std_dev = stdev(check_times)
        max_time = max(check_times)
        
        print(f"Permission Check Performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Std Dev: {std_dev:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        
        # Performance assertions
        assert avg_time < 10  # Average under 10ms
        assert max_time < 50  # Max under 50ms
    
    @pytest.mark.asyncio
    async def test_concurrent_auth_performance(self, test_client: AsyncClient):
        """Test authentication system under concurrent load."""
        async def authenticate_user(email: str, password: str):
            start = time.time()
            response = await test_client.post("/api/v1/auth/login", json={
                "email": email,
                "password": password
            })
            return time.time() - start, response.status_code
        
        # Create test users
        users = [
            (f"user{i}@test.com", "TestPass123!")
            for i in range(50)
        ]
        
        # Run concurrent authentications
        tasks = [
            authenticate_user(email, password)
            for email, password in users
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Analyze results
        times = [r[0] for r in results]
        success_count = sum(1 for r in results if r[1] == 200)
        
        avg_time = mean(times)
        max_time = max(times)
        
        print(f"Concurrent Authentication Performance:")
        print(f"  Users: {len(users)}")
        print(f"  Success: {success_count}/{len(users)}")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
        
        # Performance assertions
        assert success_count == len(users)  # All should succeed
        assert avg_time < 1.0  # Average under 1 second
```

### Load Testing with Locust

```python
# tests/load/locustfile.py
from locust import HttpUser, task, between

class SecurityLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get auth token."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@example.com",
            "password": "LoadTest123!"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def check_permissions(self):
        """Test permission checks."""
        self.client.get("/api/v1/users/me/permissions", headers=self.headers)
    
    @task(2)
    def access_report(self):
        """Test report access."""
        self.client.get("/api/v1/reports/summary", headers=self.headers)
    
    @task(1)
    def refresh_token(self):
        """Test token refresh."""
        response = self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": self.token
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
```

## Compliance Testing

### GDPR Compliance Tests

```python
# tests/compliance/test_gdpr_compliance.py
import pytest
from datetime import datetime, timedelta

class TestGDPRCompliance:
    @pytest.mark.asyncio
    async def test_right_to_access(self, test_client, auth_headers):
        """Test GDPR right to access personal data."""
        response = await test_client.get(
            "/api/v1/gdpr/my-data",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields are present
        assert "personal_data" in data
        assert "processing_purposes" in data
        assert "data_categories" in data
        assert "retention_periods" in data
        assert "third_party_sharing" in data
    
    @pytest.mark.asyncio
    async def test_right_to_erasure(self, test_client, auth_headers):
        """Test GDPR right to erasure (right to be forgotten)."""
        # Request deletion
        response = await test_client.post(
            "/api/v1/gdpr/delete-my-data",
            headers=auth_headers,
            json={"confirm": True, "reason": "user_request"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "scheduled"
        assert "deletion_date" in result
        
        # Verify audit log
        audit_response = await test_client.get(
            "/api/v1/gdpr/deletion-request-status",
            headers=auth_headers
        )
        assert audit_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_consent_management(self, test_client, auth_headers):
        """Test GDPR consent management."""
        # Update consent
        response = await test_client.put(
            "/api/v1/gdpr/consent",
            headers=auth_headers,
            json={
                "marketing_emails": False,
                "data_analytics": True,
                "third_party_sharing": False
            }
        )
        
        assert response.status_code == 200
        
        # Verify consent is recorded
        consent_response = await test_client.get(
            "/api/v1/gdpr/consent",
            headers=auth_headers
        )
        
        assert consent_response.status_code == 200
        consent = consent_response.json()
        assert consent["marketing_emails"] is False
        assert consent["data_analytics"] is True
        assert "consent_date" in consent
```

### SOX Compliance Tests

```python
# tests/compliance/test_sox_compliance.py
import pytest

class TestSOXCompliance:
    @pytest.mark.asyncio
    async def test_financial_data_access_logging(self, test_client, auth_headers, test_db):
        """Test that all financial data access is logged."""
        # Access financial report
        response = await test_client.get(
            "/api/v1/reports/financial/revenue",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify audit log was created
        audit_logs = await test_db.execute(
            "SELECT * FROM audit_logs WHERE action = 'FINANCIAL_DATA_ACCESS' ORDER BY timestamp DESC LIMIT 1"
        )
        log = audit_logs.first()
        
        assert log is not None
        assert log.resource_type == "financial_report"
        assert log.details["report_type"] == "revenue"
        assert log.ip_address is not None
    
    @pytest.mark.asyncio
    async def test_change_management_controls(self, test_client, admin_headers):
        """Test SOX change management controls."""
        # Attempt to modify financial settings
        response = await test_client.put(
            "/api/v1/admin/financial-settings",
            headers=admin_headers,
            json={
                "revenue_recognition_method": "accrual",
                "fiscal_year_start": "2024-01-01"
            }
        )
        
        # Should require approval
        assert response.status_code == 202  # Accepted but pending approval
        result = response.json()
        assert result["status"] == "pending_approval"
        assert "approval_required_by" in result
        assert "change_ticket_id" in result
```

## Security Regression Testing

### Regression Test Suite

```python
# tests/regression/test_security_regression.py
import pytest
from pathlib import Path
import json

class TestSecurityRegression:
    """Test for security regressions using known vulnerabilities."""
    
    @pytest.fixture
    def vulnerability_database(self):
        """Load known vulnerabilities for regression testing."""
        vuln_file = Path("tests/regression/known_vulnerabilities.json")
        with open(vuln_file) as f:
            return json.load(f)
    
    @pytest.mark.asyncio
    async def test_known_vulnerabilities(self, test_client, vulnerability_database):
        """Test that known vulnerabilities remain fixed."""
        for vuln in vulnerability_database:
            print(f"Testing {vuln['id']}: {vuln['description']}")
            
            # Execute test based on vulnerability type
            if vuln["type"] == "sql_injection":
                await self._test_sql_injection_vuln(test_client, vuln)
            elif vuln["type"] == "auth_bypass":
                await self._test_auth_bypass_vuln(test_client, vuln)
            elif vuln["type"] == "privilege_escalation":
                await self._test_privilege_escalation_vuln(test_client, vuln)
    
    async def _test_sql_injection_vuln(self, client, vuln):
        """Test specific SQL injection vulnerability."""
        response = await client.request(
            method=vuln["method"],
            url=vuln["endpoint"],
            **vuln["payload"]
        )
        
        # Vulnerability should be fixed
        assert response.status_code != 500
        assert vuln["indicator"] not in response.text
```

## Test Data Management

### Security Test Fixtures

```python
# tests/fixtures/security_fixtures.py
import pytest
from faker import Faker
from factory import Factory, Sequence, SubFactory
from models.user import User, UserRole
from models.feature_permission import FeaturePermission

fake = Faker()

class UserFactory(Factory):
    class Meta:
        model = User
    
    id = Factory.LazyFunction(lambda: uuid.uuid4())
    email = Factory.LazyFunction(lambda: fake.email())
    role = Factory.Iterator([role for role in UserRole])
    is_active = True
    mfa_enabled = Factory.LazyFunction(lambda: fake.boolean(chance_of_getting_true=30))

class PermissionFactory(Factory):
    class Meta:
        model = FeaturePermission
    
    id = Factory.LazyFunction(lambda: uuid.uuid4())
    name = Factory.LazyFunction(lambda: fake.sentence(nb_words=3))
    feature_type = Factory.Iterator([ft for ft in FeatureType])
    allowed_actions = Factory.LazyFunction(lambda: fake.random_elements(
        elements=["view", "create", "update", "delete"],
        length=fake.random_int(min=1, max=4)
    ))
    priority = Factory.LazyFunction(lambda: fake.random_int(min=1, max=100))

@pytest.fixture
async def create_test_users_with_permissions():
    """Create test users with various permission configurations."""
    async def _create(count: int = 10):
        users = []
        for i in range(count):
            user = UserFactory()
            
            # Create permissions for user
            permission_count = fake.random_int(min=1, max=5)
            for _ in range(permission_count):
                perm = PermissionFactory(user_id=user.id)
                await db.save(perm)
            
            users.append(user)
        
        return users
    
    return _create
```

### Test Data Security

```python
# tests/utils/test_data_security.py
import hashlib
from typing import Dict, Any

class TestDataSanitizer:
    """Sanitize sensitive data in test outputs."""
    
    SENSITIVE_FIELDS = [
        "password", "token", "secret", "api_key",
        "ssn", "credit_card", "bank_account"
    ]
    
    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive fields in dictionary."""
        sanitized = {}
        
        for key, value in data.items():
            if any(field in key.lower() for field in cls.SENSITIVE_FIELDS):
                # Hash sensitive data
                if isinstance(value, str):
                    sanitized[key] = f"REDACTED_{hashlib.md5(value.encode()).hexdigest()[:8]}"
                else:
                    sanitized[key] = "REDACTED"
            elif isinstance(value, dict):
                sanitized[key] = cls.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    cls.sanitize_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
```

## CI/CD Security Testing

### GitHub Actions Security Workflow

```yaml
# .github/workflows/security-tests.yml
name: Security Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  security-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
    
    - name: Run security tests
      run: |
        pytest tests/security/ -v --cov=core.security --cov-report=xml
    
    - name: Run Bandit security scan
      run: |
        bandit -r app/ -f json -o bandit-report.json
    
    - name: Run Safety check
      run: |
        safety check --json > safety-report.json
    
    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: security-test-results
        path: |
          coverage.xml
          bandit-report.json
          safety-report.json
    
    - name: Comment PR with results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          const coverage = fs.readFileSync('coverage.xml', 'utf8');
          // Parse and format results
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: '## Security Test Results\n...'
          });
```

### Docker Security Testing

```dockerfile
# Dockerfile.security-test
FROM python:3.11-slim

# Install security testing tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nmap \
    nikto \
    sqlmap \
    && rm -rf /var/lib/apt/lists/*

# Install Python security tools
RUN pip install \
    pytest \
    pytest-asyncio \
    safety \
    bandit \
    requests \
    httpx

# Copy test files
COPY tests/security /tests/security
COPY scripts/security-scan.sh /scripts/

# Run security tests
CMD ["/scripts/security-scan.sh"]
```

## Test Reports

### Security Test Report Template

```python
# tests/utils/security_report_generator.py
from datetime import datetime
from jinja2 import Template

SECURITY_REPORT_TEMPLATE = """
# Security Test Report

**Generated**: {{ timestamp }}
**Environment**: {{ environment }}
**Test Suite Version**: {{ version }}

## Summary

- **Total Tests**: {{ total_tests }}
- **Passed**: {{ passed_tests }}
- **Failed**: {{ failed_tests }}
- **Security Issues Found**: {{ security_issues }}

## Test Results

### Authentication Tests
{{ auth_test_results }}

### Authorization Tests
{{ authz_test_results }}

### Vulnerability Tests
{{ vuln_test_results }}

### Performance Tests
{{ perf_test_results }}

## Security Issues

{% for issue in issues %}
### {{ issue.title }}
- **Severity**: {{ issue.severity }}
- **Category**: {{ issue.category }}
- **Description**: {{ issue.description }}
- **Recommendation**: {{ issue.recommendation }}
{% endfor %}

## Recommendations

{{ recommendations }}

## Next Steps

{{ next_steps }}
"""

def generate_security_report(test_results, output_path):
    """Generate comprehensive security test report."""
    template = Template(SECURITY_REPORT_TEMPLATE)
    
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "environment": test_results["environment"],
        "version": test_results["version"],
        "total_tests": test_results["total"],
        "passed_tests": test_results["passed"],
        "failed_tests": test_results["failed"],
        "security_issues": len(test_results["issues"]),
        "auth_test_results": format_test_results(test_results["auth"]),
        "authz_test_results": format_test_results(test_results["authz"]),
        "vuln_test_results": format_test_results(test_results["vuln"]),
        "perf_test_results": format_test_results(test_results["perf"]),
        "issues": test_results["issues"],
        "recommendations": generate_recommendations(test_results),
        "next_steps": generate_next_steps(test_results)
    }
    
    report = template.render(**report_data)
    
    with open(output_path, 'w') as f:
        f.write(report)
    
    return report
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clean State**: Reset database/cache between tests
3. **Realistic Data**: Use production-like test data
4. **Coverage Goals**: Aim for >90% coverage of security code
5. **Regular Updates**: Update test cases for new threats
6. **Performance Baselines**: Track performance over time
7. **Security Fixtures**: Reusable security test components
8. **Continuous Testing**: Run security tests in CI/CD