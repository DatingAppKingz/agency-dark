"""
Unit tests for feature permission system.

Tests core functionality of feature permissions including:
- Permission creation and management
- Access control checks
- Time and location restrictions
- Usage quotas and rate limiting
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, ReportType, ExportFormat,
    AnalyticsScope, MessagePermission, DataSensitivity
)
from core.security.feature_permissions.service import FeaturePermissionService
from core.exceptions import PermissionDeniedError, ResourceNotFoundError


@pytest.fixture
def feature_permission_service():
    """Create feature permission service instance."""
    return FeaturePermissionService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def test_user():
    """Create test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role=UserRole.MANAGER,
        agency_id=uuid.uuid4(),
        is_active=True,
        mfa_enabled=True
    )
    user.roles = [MagicMock(id=uuid.uuid4(), name="manager")]
    user.primary_role_id = user.roles[0].id
    return user


@pytest.fixture
def admin_user():
    """Create admin user."""
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True
    )
    user.roles = [MagicMock(id=uuid.uuid4(), name="admin")]
    return user


@pytest.fixture
def test_permission():
    """Create test feature permission."""
    return FeaturePermission(
        id=uuid.uuid4(),
        name="Test Permission",
        feature_type=FeatureType.REPORTS,
        role_id=uuid.uuid4(),
        allowed_actions=["view_report", "export_report"],
        denied_actions=["delete_report"],
        is_active=True,
        priority=10,
        can_access_financial_data=True,
        can_access_pii_data=False,
        max_report_range_days=90,
        data_sensitivity_level=DataSensitivity.CONFIDENTIAL
    )


class TestFeaturePermissionService:
    """Test cases for FeaturePermissionService."""
    
    @pytest.mark.asyncio
    async def test_check_feature_permission_allowed(
        self, feature_permission_service, mock_db, test_user, test_permission
    ):
        """Test successful permission check."""
        # Mock cache miss
        with patch('core.redis.redis_client.get', return_value=None):
            # Mock getting permissions
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[test_permission]
            ):
                # Mock evaluation
                with patch.object(
                    feature_permission_service,
                    '_evaluate_permission',
                    return_value=(True, None)
                ):
                    # Mock logging
                    with patch.object(
                        feature_permission_service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        # Mock cache set
                        with patch('core.redis.redis_client.setex'):
                            allowed, reason = await feature_permission_service.check_feature_permission(
                                db=mock_db,
                                user=test_user,
                                feature_type=FeatureType.REPORTS,
                                action="view_report"
                            )
                            
                            assert allowed is True
                            assert reason is None
    
    @pytest.mark.asyncio
    async def test_check_feature_permission_denied(
        self, feature_permission_service, mock_db, test_user, test_permission
    ):
        """Test denied permission check."""
        test_permission.denied_actions = ["view_report"]
        
        with patch('core.redis.redis_client.get', return_value=None):
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions',
                return_value=[test_permission]
            ):
                with patch.object(
                    feature_permission_service,
                    '_evaluate_permission',
                    return_value=(False, "Action 'view_report' is explicitly denied")
                ):
                    with patch.object(
                        feature_permission_service,
                        '_log_feature_usage',
                        return_value=None
                    ):
                        with patch('core.redis.redis_client.setex'):
                            allowed, reason = await feature_permission_service.check_feature_permission(
                                db=mock_db,
                                user=test_user,
                                feature_type=FeatureType.REPORTS,
                                action="view_report"
                            )
                            
                            assert allowed is False
                            assert "denied" in reason
    
    @pytest.mark.asyncio
    async def test_check_feature_permission_cached(
        self, feature_permission_service, mock_db, test_user
    ):
        """Test permission check with cache hit."""
        cached_result = '{"allowed": true, "reason": null}'
        
        with patch('core.redis.redis_client.get', return_value=cached_result):
            # Should not call other methods when cache hit
            with patch.object(
                feature_permission_service,
                '_get_user_feature_permissions'
            ) as mock_get_perms:
                allowed, reason = await feature_permission_service.check_feature_permission(
                    db=mock_db,
                    user=test_user,
                    feature_type=FeatureType.REPORTS,
                    action="view_report"
                )
                
                assert allowed is True
                assert reason is None
                mock_get_perms.assert_not_called()
    
    def test_check_time_restrictions_within_window(self, feature_permission_service):
        """Test time restrictions when current time is within allowed window."""
        permission = FeaturePermission(
            access_start_time="09:00",
            access_end_time="17:00",
            access_timezone="UTC"
        )
        
        # Mock current time to be 12:00 UTC
        with patch('core.security.feature_permissions.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value.hour = 12
            mock_datetime.now.return_value.time.return_value.minute = 0
            
            result = feature_permission_service._check_time_restrictions(permission)
            assert result is True
    
    def test_check_time_restrictions_outside_window(self, feature_permission_service):
        """Test time restrictions when current time is outside allowed window."""
        permission = FeaturePermission(
            access_start_time="09:00",
            access_end_time="17:00",
            access_timezone="UTC"
        )
        
        # Mock current time to be 20:00 UTC
        with patch('core.security.feature_permissions.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value.hour = 20
            mock_datetime.now.return_value.time.return_value.minute = 0
            
            result = feature_permission_service._check_time_restrictions(permission)
            assert result is False
    
    def test_check_time_restrictions_overnight_window(self, feature_permission_service):
        """Test time restrictions with overnight window (e.g., 22:00-02:00)."""
        permission = FeaturePermission(
            access_start_time="22:00",
            access_end_time="02:00",
            access_timezone="UTC"
        )
        
        # Test at 23:00 (should be allowed)
        with patch('core.security.feature_permissions.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value.hour = 23
            mock_datetime.now.return_value.time.return_value.minute = 0
            
            result = feature_permission_service._check_time_restrictions(permission)
            assert result is True
        
        # Test at 01:00 (should be allowed)
        with patch('core.security.feature_permissions.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value.hour = 1
            mock_datetime.now.return_value.time.return_value.minute = 0
            
            result = feature_permission_service._check_time_restrictions(permission)
            assert result is True
        
        # Test at 10:00 (should be denied)
        with patch('core.security.feature_permissions.service.datetime') as mock_datetime:
            mock_datetime.now.return_value.time.return_value.hour = 10
            mock_datetime.now.return_value.time.return_value.minute = 0
            
            result = feature_permission_service._check_time_restrictions(permission)
            assert result is False
    
    def test_check_location_restrictions_allowed_ip(self, feature_permission_service):
        """Test location restrictions with allowed IP."""
        permission = FeaturePermission(
            allowed_ip_ranges=["192.168.1.0/24", "10.0.0.0/8"]
        )
        
        context = {"ip_address": "192.168.1.100"}
        result = feature_permission_service._check_location_restrictions(permission, context)
        assert result is True
    
    def test_check_location_restrictions_denied_ip(self, feature_permission_service):
        """Test location restrictions with denied IP."""
        permission = FeaturePermission(
            allowed_ip_ranges=["192.168.1.0/24"]
        )
        
        context = {"ip_address": "172.16.0.1"}
        result = feature_permission_service._check_location_restrictions(permission, context)
        assert result is False
    
    def test_check_location_restrictions_allowed_country(self, feature_permission_service):
        """Test location restrictions with allowed country."""
        permission = FeaturePermission(
            allowed_countries=["US", "CA", "GB"]
        )
        
        context = {"country_code": "US"}
        result = feature_permission_service._check_location_restrictions(permission, context)
        assert result is True
    
    def test_check_location_restrictions_denied_country(self, feature_permission_service):
        """Test location restrictions with denied country."""
        permission = FeaturePermission(
            allowed_countries=["US", "CA"]
        )
        
        context = {"country_code": "CN"}
        result = feature_permission_service._check_location_restrictions(permission, context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_conditional_access_mfa_required(
        self, feature_permission_service, test_user
    ):
        """Test conditional access when MFA is required."""
        permission = FeaturePermission(requires_mfa=True)
        
        # User has MFA enabled, session has MFA verified
        context = {"mfa_verified": True}
        result = await feature_permission_service._check_conditional_access(
            test_user, permission, context
        )
        assert result is True
        
        # User has MFA enabled, but session doesn't have MFA verified
        context = {"mfa_verified": False}
        result = await feature_permission_service._check_conditional_access(
            test_user, permission, context
        )
        assert result is False
        
        # User doesn't have MFA enabled
        test_user.mfa_enabled = False
        result = await feature_permission_service._check_conditional_access(
            test_user, permission, context
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_report_permission_valid(
        self, feature_permission_service, test_permission
    ):
        """Test report-specific permission check."""
        context = {
            "report_type": ReportType.EARNINGS.value,
            "date_range_days": 30,
            "contains_financial": True,
            "contains_pii": False
        }
        
        test_permission.allowed_report_types = [ReportType.EARNINGS.value]
        
        allowed, reason = await feature_permission_service._check_report_permission(
            test_permission, "view_report", context
        )
        
        assert allowed is True
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_check_report_permission_denied_type(
        self, feature_permission_service, test_permission
    ):
        """Test report permission denied due to report type."""
        context = {
            "report_type": ReportType.TAX_REPORT.value
        }
        
        test_permission.allowed_report_types = [ReportType.EARNINGS.value]
        
        allowed, reason = await feature_permission_service._check_report_permission(
            test_permission, "view_report", context
        )
        
        assert allowed is False
        assert "not allowed" in reason
    
    @pytest.mark.asyncio
    async def test_check_report_permission_date_range_exceeded(
        self, feature_permission_service, test_permission
    ):
        """Test report permission denied due to date range."""
        context = {
            "date_range_days": 180
        }
        
        test_permission.max_report_range_days = 90
        
        allowed, reason = await feature_permission_service._check_report_permission(
            test_permission, "view_report", context
        )
        
        assert allowed is False
        assert "exceeds maximum" in reason
    
    @pytest.mark.asyncio
    async def test_check_export_permission_valid(
        self, feature_permission_service
    ):
        """Test export permission check."""
        permission = FeaturePermission(
            allowed_export_formats=[ExportFormat.CSV.value, ExportFormat.EXCEL.value],
            max_export_rows=10000,
            max_export_size_mb=50
        )
        
        context = {
            "format": ExportFormat.CSV.value,
            "row_count": 5000,
            "size_mb": 10
        }
        
        allowed, reason = await feature_permission_service._check_export_permission(
            permission, "export_data", context
        )
        
        assert allowed is True
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_check_analytics_permission_scope(
        self, feature_permission_service
    ):
        """Test analytics permission with scope checking."""
        permission = FeaturePermission(
            analytics_scope=AnalyticsScope.TEAM
        )
        
        # Team scope requesting own data (allowed)
        context = {"scope": AnalyticsScope.OWN}
        allowed, reason = await feature_permission_service._check_analytics_permission(
            permission, "view_analytics", context
        )
        assert allowed is True
        
        # Team scope requesting agency data (denied)
        context = {"scope": AnalyticsScope.AGENCY}
        allowed, reason = await feature_permission_service._check_analytics_permission(
            permission, "view_analytics", context
        )
        assert allowed is False
        assert "not allowed" in reason
    
    @pytest.mark.asyncio
    async def test_check_messaging_permission_bulk(
        self, feature_permission_service
    ):
        """Test messaging permission for bulk send."""
        permission = FeaturePermission(
            message_permissions=[MessagePermission.SEND_BULK.value],
            max_bulk_recipients=100
        )
        
        # Within limit
        context = {"recipient_count": 50}
        allowed, reason = await feature_permission_service._check_messaging_permission(
            permission, "send_bulk", context
        )
        assert allowed is True
        
        # Exceeds limit
        context = {"recipient_count": 200}
        allowed, reason = await feature_permission_service._check_messaging_permission(
            permission, "send_bulk", context
        )
        assert allowed is False
        assert "exceeds maximum" in reason
    
    @pytest.mark.asyncio
    async def test_create_feature_permission_success(
        self, feature_permission_service, mock_db, admin_user
    ):
        """Test successful permission creation."""
        # Mock permission check
        with patch.object(
            feature_permission_service,
            'check_feature_permission',
            return_value=(True, None)
        ):
            # Mock audit logging
            with patch.object(
                feature_permission_service.audit_service,
                'log',
                return_value=None
            ):
                # Mock cache clear
                with patch.object(
                    feature_permission_service,
                    '_clear_permission_cache',
                    return_value=None
                ):
                    mock_db.commit = AsyncMock()
                    mock_db.refresh = AsyncMock()
                    
                    permission = await feature_permission_service.create_feature_permission(
                        db=mock_db,
                        user=admin_user,
                        name="Test Permission",
                        feature_type=FeatureType.REPORTS
                    )
                    
                    assert permission.name == "Test Permission"
                    assert permission.feature_type == FeatureType.REPORTS
                    mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_feature_permission_denied(
        self, feature_permission_service, mock_db, test_user
    ):
        """Test permission creation when user lacks permission."""
        # Mock permission check failure
        with patch.object(
            feature_permission_service,
            'check_feature_permission',
            return_value=(False, "Insufficient privileges")
        ):
            with pytest.raises(PermissionDeniedError) as exc_info:
                await feature_permission_service.create_feature_permission(
                    db=mock_db,
                    user=test_user,
                    name="Test Permission",
                    feature_type=FeatureType.REPORTS
                )
            
            assert "Cannot create permissions" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_quota_usage(
        self, feature_permission_service, mock_db, test_user, test_permission
    ):
        """Test quota usage checking."""
        test_permission.usage_quota_daily = 100
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar.return_value = 25
        mock_db.execute.return_value = mock_result
        
        used, limit = await feature_permission_service.check_quota_usage(
            db=mock_db,
            user=test_user,
            permission=test_permission,
            period="daily"
        )
        
        assert used == 25
        assert limit == 100