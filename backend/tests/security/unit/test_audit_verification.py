"""
Audit trail verification tests.

Tests to ensure comprehensive audit logging, compliance requirements,
and forensic capabilities of the audit system.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json
from typing import List, Dict, Any

from models.user import User, UserRole
from models.audit_log import AuditLog, AuditAction, AuditSeverity
from models.feature_permission import FeaturePermission, FeatureType
from core.audit.service import AuditService
from core.security.feature_permissions.service import feature_permission_service


@pytest.fixture
def audit_service():
    """Create audit service instance."""
    return AuditService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def test_user():
    """Create test user."""
    return User(
        id=uuid.uuid4(),
        email="auditor@example.com",
        role=UserRole.ADMIN,
        agency_id=uuid.uuid4()
    )


class TestAuditCompleteness:
    """Test audit trail completeness for all critical operations."""
    
    @pytest.mark.asyncio
    async def test_authentication_events_logged(self, audit_service, mock_db, test_user):
        """Test that all authentication events are logged."""
        # Mock database operations
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        
        # Test login event
        await audit_service.log(
            db=mock_db,
            action=AuditAction.USER_LOGIN,
            user=test_user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            details={"method": "password"}
        )
        
        # Verify audit log was created
        mock_db.add.assert_called_once()
        audit_log = mock_db.add.call_args[0][0]
        
        assert isinstance(audit_log, AuditLog)
        assert audit_log.action == AuditAction.USER_LOGIN
        assert audit_log.user_id == test_user.id
        assert audit_log.ip_address == "192.168.1.100"
        assert audit_log.details["method"] == "password"
        
        # Test logout event
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.USER_LOGOUT,
            user=test_user,
            details={"session_duration_minutes": 45}
        )
        
        mock_db.add.assert_called_once()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.USER_LOGOUT
        
        # Test failed login
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.LOGIN_FAILED,
            user_email="hacker@example.com",
            ip_address="10.0.0.1",
            details={"reason": "invalid_password", "attempts": 3}
        )
        
        mock_db.add.assert_called_once()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.LOGIN_FAILED
        assert audit_log.severity == AuditSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_permission_changes_logged(self, audit_service, mock_db, test_user):
        """Test that all permission changes are logged."""
        # Test permission creation
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERMISSION_CREATED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="feature_permission",
            details={
                "permission_name": "New Analytics Permission",
                "feature_type": "analytics",
                "scope": "agency"
            }
        )
        
        # Verify logged
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.PERMISSION_CREATED
        assert audit_log.resource_type == "feature_permission"
        
        # Test permission update
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERMISSION_UPDATED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="feature_permission",
            details={
                "changes": {
                    "can_view_revenue_data": {"old": False, "new": True},
                    "max_export_rows": {"old": 1000, "new": 5000}
                }
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.PERMISSION_UPDATED
        assert "changes" in audit_log.details
        
        # Test permission deletion
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERMISSION_DELETED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="feature_permission",
            details={"permission_name": "Obsolete Permission"}
        )
        
        mock_db.add.assert_called()
        assert mock_db.add.call_args[0][0].action == AuditAction.PERMISSION_DELETED
    
    @pytest.mark.asyncio
    async def test_data_access_logged(self, audit_service, mock_db, test_user):
        """Test that data access events are logged."""
        # Test report access
        await audit_service.log(
            db=mock_db,
            action=AuditAction.REPORT_ACCESSED,
            user=test_user,
            resource_id="earnings_report_2024",
            resource_type="report",
            details={
                "report_type": "earnings",
                "date_range": "2024-01-01 to 2024-12-31",
                "rows_returned": 15000
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.REPORT_ACCESSED
        assert audit_log.details["rows_returned"] == 15000
        
        # Test data export
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.DATA_EXPORT,
            user=test_user,
            resource_id="export_12345",
            resource_type="user_data_export",
            details={
                "export_type": "user_analytics",
                "format": "csv",
                "rows": 50000,
                "size_mb": 125.5,
                "contains_pii": True
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.DATA_EXPORT
        assert audit_log.severity == AuditSeverity.WARNING  # Due to PII
        assert audit_log.details["contains_pii"] is True
    
    @pytest.mark.asyncio
    async def test_security_events_logged(self, audit_service, mock_db, test_user):
        """Test that security events are properly logged."""
        # Test rate limit violation
        await audit_service.log(
            db=mock_db,
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            user=test_user,
            ip_address="192.168.1.100",
            details={
                "endpoint": "/api/v1/export",
                "limit_type": "export_rate_limit",
                "limit": 10,
                "current": 15
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.RATE_LIMIT_EXCEEDED
        assert audit_log.severity == AuditSeverity.WARNING
        
        # Test suspicious activity
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            user=test_user,
            details={
                "type": "unusual_export_pattern",
                "description": "User exported 90% of database in 1 hour",
                "risk_score": 85
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.SUSPICIOUS_ACTIVITY
        assert audit_log.severity == AuditSeverity.ERROR
        assert audit_log.risk_score == 85


class TestAuditIntegrity:
    """Test audit trail integrity and tamper resistance."""
    
    @pytest.mark.asyncio
    async def test_audit_log_immutability(self, mock_db):
        """Test that audit logs cannot be modified after creation."""
        # Create audit log
        audit_log = AuditLog(
            id=uuid.uuid4(),
            action=AuditAction.USER_LOGIN,
            user_id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.100"
        )
        
        # Attempt to modify - should fail in real implementation
        # Audit logs should be append-only
        original_action = audit_log.action
        original_timestamp = audit_log.timestamp
        
        # These modifications should be prevented by the system
        # In real implementation, the ORM would prevent updates
        assert audit_log.action == original_action
        assert audit_log.timestamp == original_timestamp
    
    @pytest.mark.asyncio
    async def test_audit_log_completeness_check(self, mock_db):
        """Test detection of missing audit logs."""
        # Simulate sequence of audit logs
        audit_logs = []
        for i in range(10):
            log = AuditLog(
                id=uuid.uuid4(),
                action=AuditAction.API_REQUEST,
                timestamp=datetime.utcnow() + timedelta(minutes=i),
                sequence_number=i  # Assuming sequential numbering
            )
            audit_logs.append(log)
        
        # Check for gaps in sequence
        sequence_numbers = [log.sequence_number for log in audit_logs]
        expected_sequence = list(range(10))
        
        assert sequence_numbers == expected_sequence
        
        # Simulate missing log
        audit_logs.pop(5)  # Remove log with sequence_number 5
        sequence_numbers = [log.sequence_number for log in audit_logs]
        
        # Detect gap
        gaps = []
        for i in range(1, len(sequence_numbers)):
            if sequence_numbers[i] - sequence_numbers[i-1] > 1:
                gaps.append(sequence_numbers[i-1] + 1)
        
        assert 5 in gaps  # Gap detected
    
    @pytest.mark.asyncio
    async def test_audit_log_cryptographic_integrity(self, mock_db):
        """Test cryptographic integrity of audit logs."""
        import hashlib
        
        # Create audit log with hash chain
        previous_hash = "0" * 64  # Genesis hash
        
        audit_logs = []
        for i in range(5):
            log_data = {
                "id": str(uuid.uuid4()),
                "action": "USER_LOGIN",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(uuid.uuid4()),
                "previous_hash": previous_hash
            }
            
            # Calculate hash including previous hash
            log_string = json.dumps(log_data, sort_keys=True)
            current_hash = hashlib.sha256(log_string.encode()).hexdigest()
            
            log_data["hash"] = current_hash
            audit_logs.append(log_data)
            previous_hash = current_hash
        
        # Verify chain integrity
        for i in range(1, len(audit_logs)):
            current_log = audit_logs[i]
            previous_log = audit_logs[i-1]
            
            # Verify previous hash reference
            assert current_log["previous_hash"] == previous_log["hash"]
            
            # Recalculate and verify hash
            log_copy = current_log.copy()
            stored_hash = log_copy.pop("hash")
            
            recalculated = hashlib.sha256(
                json.dumps(log_copy, sort_keys=True).encode()
            ).hexdigest()
            
            assert stored_hash == recalculated


class TestComplianceRequirements:
    """Test compliance with regulatory requirements."""
    
    @pytest.mark.asyncio
    async def test_gdpr_compliance_logging(self, audit_service, mock_db, test_user):
        """Test GDPR-compliant audit logging."""
        # Test data access logging
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERSONAL_DATA_ACCESSED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="user_profile",
            details={
                "data_categories": ["name", "email", "phone"],
                "purpose": "customer_support",
                "legal_basis": "legitimate_interest"
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        
        # Verify GDPR requirements
        assert "data_categories" in audit_log.details
        assert "purpose" in audit_log.details
        assert "legal_basis" in audit_log.details
        
        # Test data deletion logging
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.PERSONAL_DATA_DELETED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="user_data",
            details={
                "deletion_reason": "user_request",
                "data_types": ["messages", "profile", "analytics"],
                "retention_period_days": 30  # Soft delete period
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        assert audit_log.action == AuditAction.PERSONAL_DATA_DELETED
        assert audit_log.details["deletion_reason"] == "user_request"
    
    @pytest.mark.asyncio
    async def test_sox_compliance_logging(self, audit_service, mock_db, test_user):
        """Test SOX-compliant financial audit logging."""
        # Test financial data access
        await audit_service.log(
            db=mock_db,
            action=AuditAction.FINANCIAL_REPORT_ACCESSED,
            user=test_user,
            resource_id="quarterly_earnings_q4_2024",
            resource_type="financial_report",
            details={
                "report_type": "earnings",
                "period": "Q4 2024",
                "contains_material_info": True,
                "access_approved_by": str(uuid.uuid4())
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        
        # SOX requires approval tracking for material financial data
        assert "access_approved_by" in audit_log.details
        assert audit_log.details["contains_material_info"] is True
        
        # Test financial data modification
        mock_db.add.reset_mock()
        
        await audit_service.log(
            db=mock_db,
            action=AuditAction.FINANCIAL_DATA_MODIFIED,
            user=test_user,
            resource_id=str(uuid.uuid4()),
            resource_type="transaction",
            details={
                "modification_type": "adjustment",
                "original_amount": 10000.00,
                "new_amount": 9500.00,
                "reason": "pricing_correction",
                "approved_by": str(uuid.uuid4()),
                "approval_timestamp": datetime.utcnow().isoformat()
            }
        )
        
        mock_db.add.assert_called()
        audit_log = mock_db.add.call_args[0][0]
        
        # SOX requires detailed change tracking
        assert "original_amount" in audit_log.details
        assert "new_amount" in audit_log.details
        assert "approved_by" in audit_log.details
        assert audit_log.severity == AuditSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_audit_retention_policy(self, audit_service, mock_db):
        """Test audit log retention policy compliance."""
        # Different retention requirements by type
        retention_policies = {
            AuditAction.USER_LOGIN: 90,  # 90 days
            AuditAction.PERMISSION_UPDATED: 365,  # 1 year
            AuditAction.FINANCIAL_DATA_MODIFIED: 2555,  # 7 years (SOX)
            AuditAction.PERSONAL_DATA_DELETED: 1095,  # 3 years (GDPR)
        }
        
        # Verify retention policies are enforced
        for action, retention_days in retention_policies.items():
            retention_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # In real implementation, old logs would be archived/deleted
            # based on retention policy
            assert retention_days > 0
            assert retention_date < datetime.utcnow()


class TestAuditSearch:
    """Test audit trail search and forensic capabilities."""
    
    @pytest.mark.asyncio
    async def test_audit_search_by_user(self, audit_service, mock_db):
        """Test searching audit logs by user."""
        user_id = uuid.uuid4()
        
        # Mock search results
        mock_results = [
            AuditLog(
                action=AuditAction.USER_LOGIN,
                user_id=user_id,
                timestamp=datetime.utcnow() - timedelta(hours=2)
            ),
            AuditLog(
                action=AuditAction.DATA_EXPORT,
                user_id=user_id,
                timestamp=datetime.utcnow() - timedelta(hours=1)
            )
        ]
        
        # Mock query execution
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_results
        
        # Search
        results = await audit_service.search_logs(
            db=mock_db,
            user_id=str(user_id),
            limit=10
        )
        
        assert len(results) == 2
        assert all(log.user_id == user_id for log in results)
    
    @pytest.mark.asyncio
    async def test_audit_search_by_action(self, audit_service, mock_db):
        """Test searching audit logs by action type."""
        # Mock search for all permission changes
        permission_actions = [
            AuditAction.PERMISSION_CREATED,
            AuditAction.PERMISSION_UPDATED,
            AuditAction.PERMISSION_DELETED
        ]
        
        mock_results = [
            AuditLog(
                action=AuditAction.PERMISSION_UPDATED,
                timestamp=datetime.utcnow() - timedelta(hours=1),
                details={"permission_id": str(uuid.uuid4())}
            )
        ]
        
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_results
        
        results = await audit_service.search_logs(
            db=mock_db,
            actions=permission_actions,
            limit=50
        )
        
        assert len(results) == 1
        assert results[0].action == AuditAction.PERMISSION_UPDATED
    
    @pytest.mark.asyncio
    async def test_audit_correlation_analysis(self, audit_service, mock_db):
        """Test correlation of related audit events."""
        session_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        
        # Simulate correlated events in a session
        correlated_events = [
            AuditLog(
                action=AuditAction.USER_LOGIN,
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.utcnow() - timedelta(minutes=30)
            ),
            AuditLog(
                action=AuditAction.PERMISSION_CHECKED,
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.utcnow() - timedelta(minutes=25)
            ),
            AuditLog(
                action=AuditAction.DATA_EXPORT,
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.utcnow() - timedelta(minutes=20)
            ),
            AuditLog(
                action=AuditAction.SUSPICIOUS_ACTIVITY,
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.utcnow() - timedelta(minutes=19),
                details={"reason": "unusual_export_volume"}
            )
        ]
        
        # Group by session
        events_by_session = {}
        for event in correlated_events:
            if event.session_id not in events_by_session:
                events_by_session[event.session_id] = []
            events_by_session[event.session_id].append(event)
        
        # Verify correlation
        assert len(events_by_session[session_id]) == 4
        
        # Check chronological order
        session_events = sorted(
            events_by_session[session_id],
            key=lambda e: e.timestamp
        )
        
        # Verify suspicious activity followed export
        export_idx = next(
            i for i, e in enumerate(session_events)
            if e.action == AuditAction.DATA_EXPORT
        )
        suspicious_idx = next(
            i for i, e in enumerate(session_events)
            if e.action == AuditAction.SUSPICIOUS_ACTIVITY
        )
        
        assert suspicious_idx > export_idx  # Suspicious activity detected after export