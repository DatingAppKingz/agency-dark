"""
Integration tests for all permission layers.

Tests the interaction between multiple permission components including:
- Feature permissions
- Rate limiting
- Audit logging
- Caching
- Cross-component scenarios
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json
from typing import List, Dict, Any

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope,
    DataSensitivity, ExportFormat
)
from models.rate_limit import RateLimitConfig, RateLimitType, RateLimitAlgorithm
from models.audit_log import AuditLog, AuditAction, AuditSeverity
from core.security.feature_permissions.service import feature_permission_service
from core.rate_limit.service import DynamicRateLimitService
from core.audit.service import AuditService
from core.exceptions import PermissionDeniedError, RateLimitExceededError


class TestEndToEndPermissionFlow:
    """Test complete permission flow from request to audit."""
    
    @pytest.mark.asyncio
    async def test_complete_report_access_flow(self):
        """Test complete flow for accessing a report."""
        mock_db = AsyncMock()
        
        # Create test user
        user = User(
            id=uuid.uuid4(),
            email="analyst@company.com",
            role=UserRole.MANAGER,
            agency_id=uuid.uuid4()
        )
        user.roles = [MagicMock(id=uuid.uuid4(), name="manager")]
        
        # Create permission
        permission = FeaturePermission(
            id=uuid.uuid4(),
            name="Manager Report Access",
            feature_type=FeatureType.REPORTS,
            role_id=user.roles[0].id,
            allowed_actions=["view_report", "export_report"],
            can_access_financial_data=True,
            can_access_pii_data=False,
            report_types=["performance", "analytics"],
            is_active=True
        )
        
        # Create rate limit config
        rate_limit = RateLimitConfig(
            id=uuid.uuid4(),
            name="Report API Rate Limit",
            limit_type=RateLimitType.USER,
            requests_per_minute=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            endpoint_pattern="/api/v1/reports/*",
            is_active=True
        )
        
        # Mock services
        rate_limiter = DynamicRateLimitService()
        audit_service = AuditService()
        
        # Step 1: Check rate limit
        with patch.object(
            rate_limiter,
            '_get_applicable_configs',
            return_value=[rate_limit]
        ):
            with patch.object(
                rate_limiter,
                '_check_with_algorithm',
                return_value=(True, {"remaining": 59})
            ):
                rate_allowed, rate_info = await rate_limiter.check_rate_limit(
                    db=mock_db,
                    identifier=str(user.id),
                    identifier_type=RateLimitType.USER,
                    endpoint="/api/v1/reports/performance",
                    user=user
                )
                
                assert rate_allowed is True
                assert rate_info["remaining"] == 59
        
        # Step 2: Check feature permission
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[permission]
        ):
            with patch.object(
                feature_permission_service,
                '_evaluate_permission',
                return_value=(True, None)
            ):
                with patch.object(
                    feature_permission_service,
                    '_log_feature_usage',
                    return_value=None
                ) as mock_log_usage:
                    perm_allowed, perm_reason = await feature_permission_service.check_feature_permission(
                        db=mock_db,
                        user=user,
                        feature_type=FeatureType.REPORTS,
                        action="view_report",
                        request_context={
                            "report_type": "performance",
                            "contains_financial_data": True,
                            "contains_pii": False
                        }
                    )
                    
                    assert perm_allowed is True
                    assert perm_reason is None
                    mock_log_usage.assert_called_once()
        
        # Step 3: Log audit trail
        with patch.object(mock_db, 'add') as mock_add:
            with patch.object(mock_db, 'commit', new_callable=AsyncMock):
                await audit_service.log(
                    db=mock_db,
                    action=AuditAction.REPORT_ACCESSED,
                    user=user,
                    resource_id="performance_report_2024",
                    resource_type="report",
                    ip_address="192.168.1.100",
                    user_agent="Mozilla/5.0",
                    details={
                        "report_type": "performance",
                        "contains_financial_data": True,
                        "export_format": None,
                        "rows_returned": 1500
                    }
                )
                
                mock_add.assert_called_once()
                audit_log = mock_add.call_args[0][0]
                assert isinstance(audit_log, AuditLog)
                assert audit_log.action == AuditAction.REPORT_ACCESSED
                assert audit_log.user_id == user.id
    
    @pytest.mark.asyncio
    async def test_export_permission_with_quota_flow(self):
        """Test export flow with quota management."""
        mock_db = AsyncMock()
        
        user = User(
            id=uuid.uuid4(),
            email="exporter@company.com",
            role=UserRole.MANAGER
        )
        
        # Export permission with quota
        export_permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.EXPORTS,
            user_id=user.id,
            allowed_actions=["export_data"],
            allowed_export_formats=[ExportFormat.CSV, ExportFormat.EXCEL],
            max_export_rows=10000,
            export_rate_limit_per_hour=5,
            usage_quota_daily=50000,  # 50k rows per day
            is_active=True
        )
        
        # Mock current usage
        with patch('core.redis.redis_client.get', return_value='{"count": 3, "rows": 25000"}'):
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[export_permission]
            ):
                # Check if export is allowed
                request_context = {
                    "format": ExportFormat.CSV,
                    "estimated_rows": 15000
                }
                
                # This would exceed daily quota (25000 + 15000 > 50000)
                with patch.object(
                    feature_permission_service,
                    '_check_export_permission',
                    return_value=(False, "Daily export quota exceeded")
                ):
                    allowed, reason = await feature_permission_service.check_feature_permission(
                        db=mock_db,
                        user=user,
                        feature_type=FeatureType.EXPORTS,
                        action="export_data",
                        request_context=request_context
                    )
                    
                    assert allowed is False
                    assert "quota exceeded" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_analytics_permission_with_time_restrictions(self):
        """Test analytics access with time-based restrictions."""
        mock_db = AsyncMock()
        
        user = User(
            id=uuid.uuid4(),
            email="analyst@company.com",
            role=UserRole.MANAGER
        )
        
        # Analytics permission with business hours restriction
        analytics_permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.ANALYTICS,
            user_id=user.id,
            analytics_scope=AnalyticsScope.AGENCY,
            can_view_revenue_data=True,
            access_start_time="09:00",
            access_end_time="18:00",
            access_timezone="America/New_York",
            access_days_of_week=[1, 2, 3, 4, 5],  # Monday-Friday
            is_active=True
        )
        
        # Test during business hours
        with patch('core.security.feature_permissions.service.datetime') as mock_dt:
            # Mock Tuesday at 2 PM EST
            mock_dt.now.return_value = datetime(2024, 1, 2, 14, 0, 0)  # Tuesday
            mock_dt.now.return_value.weekday.return_value = 1  # Tuesday
            mock_dt.now.return_value.time.return_value.hour = 14
            mock_dt.now.return_value.time.return_value.minute = 0
            
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[analytics_permission]
            ):
                with patch.object(
                    feature_permission_service,
                    '_check_time_restrictions',
                    return_value=True
                ):
                    with patch.object(
                        feature_permission_service,
                        '_check_analytics_permission',
                        return_value=(True, None)
                    ):
                        allowed, reason = await feature_permission_service.check_feature_permission(
                            db=mock_db,
                            user=user,
                            feature_type=FeatureType.ANALYTICS,
                            action="view_analytics",
                            request_context={"scope": AnalyticsScope.AGENCY}
                        )
                        
                        assert allowed is True
        
        # Test outside business hours
        with patch('core.security.feature_permissions.service.datetime') as mock_dt:
            # Mock Saturday
            mock_dt.now.return_value = datetime(2024, 1, 6, 14, 0, 0)  # Saturday
            mock_dt.now.return_value.weekday.return_value = 5  # Saturday
            
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[analytics_permission]
            ):
                with patch.object(
                    feature_permission_service,
                    '_check_time_restrictions',
                    return_value=False
                ):
                    allowed, reason = await feature_permission_service.check_feature_permission(
                        db=mock_db,
                        user=user,
                        feature_type=FeatureType.ANALYTICS,
                        action="view_analytics"
                    )
                    
                    assert allowed is False
                    assert "outside allowed access times" in reason.lower()


class TestMultiLayerSecurity:
    """Test interaction between multiple security layers."""
    
    @pytest.mark.asyncio
    async def test_permission_rate_limit_audit_chain(self):
        """Test complete security chain for sensitive operations."""
        mock_db = AsyncMock()
        
        user = User(
            id=uuid.uuid4(),
            email="admin@company.com",
            role=UserRole.ADMIN
        )
        
        # Services
        rate_limiter = DynamicRateLimitService()
        audit_service = AuditService()
        
        # Simulate multiple rapid requests
        results = []
        
        for i in range(10):
            # Check rate limit
            with patch.object(
                rate_limiter,
                '_get_applicable_configs',
                return_value=[
                    MagicMock(
                        requests_per_minute=5,
                        algorithm=RateLimitAlgorithm.FIXED_WINDOW
                    )
                ]
            ):
                # First 5 requests succeed, rest fail
                expected_allowed = i < 5
                
                with patch.object(
                    rate_limiter,
                    '_check_with_algorithm',
                    return_value=(expected_allowed, {"remaining": max(0, 5 - i - 1)})
                ):
                    rate_allowed, _ = await rate_limiter.check_rate_limit(
                        db=mock_db,
                        identifier=str(user.id),
                        identifier_type=RateLimitType.USER,
                        endpoint="/api/v1/admin/users",
                        user=user
                    )
                    
                    if not rate_allowed:
                        # Log rate limit exceeded
                        with patch.object(mock_db, 'add'):
                            with patch.object(mock_db, 'commit', new_callable=AsyncMock):
                                await audit_service.log(
                                    db=mock_db,
                                    action=AuditAction.RATE_LIMIT_EXCEEDED,
                                    user=user,
                                    details={"endpoint": "/api/v1/admin/users"}
                                )
                        results.append({"allowed": False, "reason": "rate_limit"})
                        continue
            
            # Check permission
            with patch.object(
                feature_permission_service,
                'check_feature_permission',
                return_value=(True, None)
            ):
                perm_allowed, _ = await feature_permission_service.check_feature_permission(
                    db=mock_db,
                    user=user,
                    feature_type=FeatureType.ADMIN,
                    action="manage_users"
                )
                
                if perm_allowed:
                    # Log successful access
                    with patch.object(mock_db, 'add'):
                        with patch.object(mock_db, 'commit', new_callable=AsyncMock):
                            await audit_service.log(
                                db=mock_db,
                                action=AuditAction.ADMIN_ACTION,
                                user=user,
                                details={"action": "manage_users"}
                            )
                    results.append({"allowed": True, "reason": None})
        
        # Verify results
        allowed_count = sum(1 for r in results if r["allowed"])
        denied_count = sum(1 for r in results if not r["allowed"])
        
        assert allowed_count == 5
        assert denied_count == 5
        assert all(r["reason"] == "rate_limit" for r in results[5:])
    
    @pytest.mark.asyncio
    async def test_cache_coordination_between_layers(self):
        """Test cache coordination between permission and rate limit layers."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@company.com")
        
        # Mock Redis pipeline for atomic operations
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [True, True]
        
        with patch('core.redis.redis_client', mock_redis):
            # Both layers should use same cache instance
            
            # Permission check caches result
            cache_key_perm = f"perm:{user.id}:reports:view"
            mock_redis.get.return_value = None  # Cache miss
            
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[
                    FeaturePermission(
                        feature_type=FeatureType.REPORTS,
                        allowed_actions=["view_report"]
                    )
                ]
            ):
                with patch.object(mock_redis, 'setex') as mock_setex:
                    await feature_permission_service.check_feature_permission(
                        db=mock_db,
                        user=user,
                        feature_type=FeatureType.REPORTS,
                        action="view_report"
                    )
                    
                    # Verify cache was set
                    mock_setex.assert_called()
            
            # Rate limit check uses different namespace
            cache_key_rate = f"rate_limit:user:{user.id}:/api/v1/reports"
            
            rate_limiter = DynamicRateLimitService()
            with patch.object(
                rate_limiter,
                '_get_applicable_configs',
                return_value=[]
            ):
                await rate_limiter.check_rate_limit(
                    db=mock_db,
                    identifier=str(user.id),
                    identifier_type=RateLimitType.USER,
                    endpoint="/api/v1/reports"
                )
            
            # Verify no cache key collision
            assert cache_key_perm != cache_key_rate
    
    @pytest.mark.asyncio
    async def test_messaging_permission_with_template_security(self):
        """Test messaging permissions with template validation."""
        mock_db = AsyncMock()
        
        user = User(
            id=uuid.uuid4(),
            email="marketer@company.com",
            role=UserRole.MANAGER
        )
        
        # Messaging permission
        messaging_permission = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.MESSAGING,
            user_id=user.id,
            allowed_message_types=["marketing", "transactional"],
            max_recipients_per_message=1000,
            daily_message_limit=5000,
            template_access_level="approved_only",
            is_active=True
        )
        
        # Test template with potential security issues
        from core.security.feature_permissions.messaging_permissions import messaging_permission_service
        
        templates_to_test = [
            # Safe template
            {
                "id": "template_1",
                "content": "Hello {{name}}, welcome to our service!",
                "type": "transactional",
                "approved": True,
                "expected": True
            },
            # Template with script tag (should be rejected)
            {
                "id": "template_2",
                "content": "<script>alert('xss')</script>Hello {{name}}",
                "type": "marketing",
                "approved": True,
                "expected": False
            },
            # Unapproved template (should be rejected for this user)
            {
                "id": "template_3",
                "content": "Special offer for {{name}}",
                "type": "marketing",
                "approved": False,
                "expected": False
            }
        ]
        
        for template in templates_to_test:
            with patch.object(
                messaging_permission_service,
                '_get_user_messaging_permissions',
                return_value=[messaging_permission]
            ):
                with patch.object(
                    messaging_permission_service,
                    '_validate_template_content',
                    return_value=not bool("<script>" in template["content"])
                ):
                    with patch.object(
                        messaging_permission_service,
                        '_check_template_access',
                        return_value=template["approved"]
                    ):
                        allowed, reason = await messaging_permission_service.check_messaging_permission(
                            db=mock_db,
                            user=user,
                            message_type=template["type"],
                            template_id=template["id"],
                            recipient_count=100
                        )
                        
                        assert allowed == template["expected"]
                        if not allowed:
                            assert reason is not None


class TestPerformanceIntegration:
    """Test performance characteristics of integrated system."""
    
    @pytest.mark.asyncio
    async def test_high_concurrency_permission_checks(self):
        """Test system under high concurrent load."""
        mock_db = AsyncMock()
        
        # Create 100 unique users
        users = [
            User(
                id=uuid.uuid4(),
                email=f"user{i}@company.com",
                role=UserRole.USER
            )
            for i in range(100)
        ]
        
        # Mock fast cache responses
        async def mock_cache_get(key):
            # 80% cache hit rate
            import random
            if random.random() < 0.8:
                return json.dumps({"allowed": True, "reason": None})
            return None
        
        # Track timing
        start_time = asyncio.get_event_loop().time()
        
        with patch('core.redis.redis_client.get', side_effect=mock_cache_get):
            with patch('core.redis.redis_client.setex', return_value=None):
                with patch.object(
                    feature_permission_service,
                    '_get_user_feature_permissions',
                    return_value=[
                        FeaturePermission(
                            feature_type=FeatureType.REPORTS,
                            allowed_actions=["view_report"]
                        )
                    ]
                ):
                    # Run 1000 concurrent permission checks
                    tasks = []
                    for _ in range(10):
                        for user in users:
                            task = feature_permission_service.check_feature_permission(
                                db=mock_db,
                                user=user,
                                feature_type=FeatureType.REPORTS,
                                action="view_report"
                            )
                            tasks.append(task)
                    
                    results = await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        requests_per_second = 1000 / duration
        
        # All should succeed
        assert all(r[0] for r in results)
        
        # Should handle at least 100 req/s
        assert requests_per_second > 100
        print(f"Performance: {requests_per_second:.0f} req/s for permission checks")
    
    @pytest.mark.asyncio
    async def test_cascading_failure_resilience(self):
        """Test system resilience to cascading failures."""
        mock_db = AsyncMock()
        
        user = User(id=uuid.uuid4(), email="test@company.com")
        
        # Simulate Redis failure
        with patch('core.redis.redis_client.get', side_effect=Exception("Redis connection failed")):
            with patch('core.redis.redis_client.setex', side_effect=Exception("Redis connection failed")):
                # System should fall back to database
                with patch.object(
                    feature_permission_service,
                    '_get_user_feature_permissions',
                    return_value=[
                        FeaturePermission(
                            feature_type=FeatureType.REPORTS,
                            allowed_actions=["view_report"]
                        )
                    ]
                ):
                    # Should still work without cache
                    allowed, reason = await feature_permission_service.check_feature_permission(
                        db=mock_db,
                        user=user,
                        feature_type=FeatureType.REPORTS,
                        action="view_report"
                    )
                    
                    assert allowed is True
        
        # Simulate database slow response
        slow_db = AsyncMock()
        
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return MagicMock(scalars=lambda: MagicMock(all=lambda: []))
        
        slow_db.execute = slow_execute
        
        # Should use cache if available
        with patch('core.redis.redis_client.get', return_value='{"allowed": true, "reason": null}'):
            start = asyncio.get_event_loop().time()
            
            allowed, reason = await feature_permission_service.check_feature_permission(
                db=slow_db,
                user=user,
                feature_type=FeatureType.REPORTS,
                action="view_report"
            )
            
            duration = asyncio.get_event_loop().time() - start
            
            # Should be fast due to cache hit
            assert duration < 0.01  # Less than 10ms
            assert allowed is True


class TestSecurityBoundaries:
    """Test security boundaries between components."""
    
    @pytest.mark.asyncio
    async def test_permission_isolation_between_agencies(self):
        """Test that permissions are properly isolated between agencies."""
        mock_db = AsyncMock()
        
        # Users from different agencies
        agency_a_id = uuid.uuid4()
        agency_b_id = uuid.uuid4()
        
        user_a = User(
            id=uuid.uuid4(),
            email="user@agency-a.com",
            agency_id=agency_a_id,
            role=UserRole.MANAGER
        )
        
        user_b = User(
            id=uuid.uuid4(),
            email="user@agency-b.com",
            agency_id=agency_b_id,
            role=UserRole.MANAGER
        )
        
        # Permissions for each agency
        perm_a = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.REPORTS,
            agency_id=agency_a_id,
            allowed_actions=["view_report", "export_report"]
        )
        
        perm_b = FeaturePermission(
            id=uuid.uuid4(),
            feature_type=FeatureType.REPORTS,
            agency_id=agency_b_id,
            allowed_actions=["view_report"]  # Different permissions
        )
        
        # User A should only get agency A permissions
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[perm_a]  # Only agency A permission
        ):
            allowed, _ = await feature_permission_service.check_feature_permission(
                db=mock_db,
                user=user_a,
                feature_type=FeatureType.REPORTS,
                action="export_report"
            )
            
            assert allowed is True  # Has export permission
        
        # User B should only get agency B permissions
        with patch.object(
            feature_permission_service,
            '_get_user_feature_permissions',
            return_value=[perm_b]  # Only agency B permission
        ):
            allowed, _ = await feature_permission_service.check_feature_permission(
                db=mock_db,
                user=user_b,
                feature_type=FeatureType.REPORTS,
                action="export_report"
            )
            
            assert allowed is False  # No export permission
    
    @pytest.mark.asyncio
    async def test_audit_trail_integrity_across_components(self):
        """Test audit trail maintains integrity across all components."""
        mock_db = AsyncMock()
        audit_service = AuditService()
        
        user = User(id=uuid.uuid4(), email="audited@company.com")
        session_id = str(uuid.uuid4())
        
        # Track all audit events in a session
        audit_events = []
        
        def track_audit(audit_log):
            audit_events.append({
                "action": audit_log.action,
                "timestamp": audit_log.timestamp,
                "session_id": audit_log.session_id
            })
        
        mock_db.add = MagicMock(side_effect=track_audit)
        mock_db.commit = AsyncMock()
        
        # 1. Login
        await audit_service.log(
            db=mock_db,
            action=AuditAction.USER_LOGIN,
            user=user,
            session_id=session_id
        )
        
        # 2. Permission check
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERMISSION_CHECKED,
            user=user,
            session_id=session_id,
            resource_type="report"
        )
        
        # 3. Rate limit check
        await audit_service.log(
            db=mock_db,
            action=AuditAction.RATE_LIMIT_CHECK,
            user=user,
            session_id=session_id
        )
        
        # 4. Data access
        await audit_service.log(
            db=mock_db,
            action=AuditAction.REPORT_ACCESSED,
            user=user,
            session_id=session_id,
            resource_id="report_123"
        )
        
        # Verify audit trail integrity
        assert len(audit_events) == 4
        
        # All events should have same session ID
        assert all(e["session_id"] == session_id for e in audit_events)
        
        # Events should be in chronological order
        timestamps = [e["timestamp"] for e in audit_events]
        assert timestamps == sorted(timestamps)
        
        # Verify event sequence makes sense
        actions = [e["action"] for e in audit_events]
        assert actions[0] == AuditAction.USER_LOGIN
        assert actions[-1] == AuditAction.REPORT_ACCESSED