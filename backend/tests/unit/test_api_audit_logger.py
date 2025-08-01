"""
Unit tests for API Audit Logger Service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import uuid

from services.api_audit_logger import APIAuditLogger, AuditAction, APIKeyAuditLog, AuditLoggerMiddleware


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def api_audit_logger(mock_db_session):
    """Create API audit logger instance."""
    return APIAuditLogger(mock_db_session)


@pytest.fixture
def sample_audit_logs():
    """Create sample audit log entries."""
    base_time = datetime.utcnow()
    return [
        Mock(
            id=uuid.uuid4(),
            api_key_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            agency_id=uuid.uuid4(),
            action=AuditAction.CREATE,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            metadata={"key_name": "Test Key"},
            created_at=base_time - timedelta(hours=1),
            error_message=None
        ),
        Mock(
            id=uuid.uuid4(),
            api_key_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            agency_id=uuid.uuid4(),
            action=AuditAction.ACCESS_GRANTED,
            ip_address="192.168.1.2",
            user_agent="TestAgent/1.0",
            metadata={"endpoint": "/api/v1/users"},
            created_at=base_time - timedelta(minutes=30),
            error_message=None
        ),
        Mock(
            id=uuid.uuid4(),
            api_key_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            agency_id=uuid.uuid4(),
            action=AuditAction.ACCESS_DENIED,
            ip_address="10.0.0.1",
            user_agent="BadBot/1.0",
            metadata={"reason": "Invalid key"},
            created_at=base_time - timedelta(minutes=10),
            error_message="Authentication failed"
        )
    ]


class TestAPIAuditLogger:
    """Test cases for APIAuditLogger"""
    
    @pytest.mark.asyncio
    async def test_log_action_basic(self, api_audit_logger, mock_db_session):
        """Test basic action logging."""
        api_key_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        agency_id = str(uuid.uuid4())
        
        with patch('services.api_audit_logger.logger') as mock_logger:
            result = await api_audit_logger.log_action(
                api_key_id=api_key_id,
                action=AuditAction.CREATE,
                user_id=user_id,
                agency_id=agency_id,
                ip_address="127.0.0.1",
                user_agent="TestAgent/1.0",
                metadata={"key_name": "Production Key"}
            )
            
            # Verify log entry was created
            assert mock_db_session.add.called
            log_entry = mock_db_session.add.call_args[0][0]
            assert log_entry.api_key_id == api_key_id
            assert log_entry.action == AuditAction.CREATE
            assert log_entry.user_id == user_id
            assert log_entry.agency_id == agency_id
            assert log_entry.ip_address == "127.0.0.1"
            assert log_entry.metadata["key_name"] == "Production Key"
            
            # Verify flush was called
            assert mock_db_session.flush.called
            
            # Verify logger was called
            mock_logger.info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_action_with_error(self, api_audit_logger, mock_db_session):
        """Test logging action with error message."""
        api_key_id = str(uuid.uuid4())
        agency_id = str(uuid.uuid4())
        
        await api_audit_logger.log_action(
            api_key_id=api_key_id,
            action=AuditAction.SYNC_FAILED,
            agency_id=agency_id,
            error_message="Connection timeout",
            metadata={"platform": "test_platform"}
        )
        
        log_entry = mock_db_session.add.call_args[0][0]
        assert log_entry.action == AuditAction.SYNC_FAILED
        assert log_entry.error_message == "Connection timeout"
    
    @pytest.mark.asyncio
    async def test_log_action_with_request_context(self, api_audit_logger, mock_db_session):
        """Test logging with request context."""
        api_key_id = str(uuid.uuid4())
        agency_id = str(uuid.uuid4())
        
        request_context = {
            "request_id": "req-123",
            "path": "/api/v1/users",
            "method": "GET"
        }
        
        await api_audit_logger.log_action(
            api_key_id=api_key_id,
            action=AuditAction.ACCESS_GRANTED,
            agency_id=agency_id,
            request_context=request_context
        )
        
        log_entry = mock_db_session.add.call_args[0][0]
        assert log_entry.request_id == "req-123"
        assert log_entry.request_path == "/api/v1/users"
        assert log_entry.request_method == "GET"
    
    @pytest.mark.asyncio
    async def test_get_logs_with_filters(self, api_audit_logger, mock_db_session, sample_audit_logs):
        """Test retrieving logs with various filters."""
        # Mock query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = sample_audit_logs[:2]
        mock_db_session.execute.return_value = mock_result
        
        api_key_id = str(uuid.uuid4())
        start_date = datetime.utcnow() - timedelta(hours=2)
        
        logs = await api_audit_logger.get_logs(
            api_key_id=api_key_id,
            action=AuditAction.CREATE,
            start_date=start_date,
            limit=50
        )
        
        # Verify execute was called
        assert mock_db_session.execute.called
        
        # Check results
        assert len(logs) == 2
        assert all(isinstance(log, Mock) for log in logs)
    
    @pytest.mark.asyncio
    async def test_get_logs_pagination(self, api_audit_logger, mock_db_session):
        """Test log retrieval with pagination."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        await api_audit_logger.get_logs(limit=10, offset=20)
        
        # Verify query was executed
        assert mock_db_session.execute.called
    
    @pytest.mark.asyncio
    async def test_get_security_events(self, api_audit_logger, mock_db_session, sample_audit_logs):
        """Test retrieving security events."""
        # Filter for security events only
        security_logs = [log for log in sample_audit_logs if log.action in [
            AuditAction.ACCESS_DENIED,
            AuditAction.INVALID_KEY_ATTEMPT
        ]]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = security_logs
        mock_db_session.execute.return_value = mock_result
        
        agency_id = str(uuid.uuid4())
        events = await api_audit_logger.get_security_events(
            agency_id=agency_id,
            hours=24
        )
        
        # Verify query was executed
        assert mock_db_session.execute.called
        
        # All returned events should be security-related
        assert len(events) > 0
    
    @pytest.mark.asyncio
    async def test_get_activity_summary(self, api_audit_logger, sample_audit_logs):
        """Test activity summary generation."""
        api_key_id = str(uuid.uuid4())
        
        # Mock get_logs to return sample data
        with patch.object(api_audit_logger, 'get_logs', return_value=sample_audit_logs):
            summary = await api_audit_logger.get_activity_summary(
                api_key_id=api_key_id,
                days=7
            )
            
            assert summary["api_key_id"] == api_key_id
            assert summary["period_days"] == 7
            assert summary["total_events"] == len(sample_audit_logs)
            assert summary["error_count"] == 1  # One log has error_message
            assert summary["unique_ips"] == 3  # Three unique IPs in sample data
            assert len(summary["recent_errors"]) == 1
            assert summary["last_activity"] is not None
    
    @pytest.mark.asyncio
    async def test_get_activity_summary_empty(self, api_audit_logger):
        """Test activity summary with no logs."""
        api_key_id = str(uuid.uuid4())
        
        with patch.object(api_audit_logger, 'get_logs', return_value=[]):
            summary = await api_audit_logger.get_activity_summary(
                api_key_id=api_key_id,
                days=30
            )
            
            assert summary["total_events"] == 0
            assert summary["error_count"] == 0
            assert summary["unique_ips"] == 0
            assert summary["last_activity"] is None


class TestAuditLoggerMiddleware:
    """Test cases for AuditLoggerMiddleware"""
    
    @pytest.mark.asyncio
    async def test_log_api_access_granted(self):
        """Test logging granted API access."""
        mock_request = Mock()
        mock_request.client = Mock(host="192.168.1.100")
        mock_request.headers = {"user-agent": "TestClient/2.0"}
        mock_request.url = Mock(path="/api/v1/data")
        mock_request.method = "GET"
        mock_request.state = Mock(request_id="req-456")
        
        api_key_id = str(uuid.uuid4())
        
        with patch('services.api_audit_logger.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            with patch('services.api_audit_logger.APIAuditLogger') as mock_logger_class:
                mock_logger = Mock()
                mock_logger.log_action = AsyncMock()
                mock_logger_class.return_value = mock_logger
                
                await AuditLoggerMiddleware.log_api_access(
                    request=mock_request,
                    api_key_id=api_key_id,
                    granted=True
                )
                
                # Verify log_action was called with correct parameters
                mock_logger.log_action.assert_called_once()
                call_args = mock_logger.log_action.call_args[1]
                assert call_args["api_key_id"] == api_key_id
                assert call_args["action"] == AuditAction.ACCESS_GRANTED
                assert call_args["ip_address"] == "192.168.1.100"
                assert call_args["user_agent"] == "TestClient/2.0"
                
                # Verify commit was called
                mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_api_access_denied(self):
        """Test logging denied API access."""
        mock_request = Mock()
        mock_request.client = Mock(host="10.0.0.50")
        mock_request.headers = {}
        mock_request.url = Mock(path="/api/v1/admin")
        mock_request.method = "DELETE"
        mock_request.state = Mock()
        
        api_key_id = str(uuid.uuid4())
        
        with patch('services.api_audit_logger.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            with patch('services.api_audit_logger.APIAuditLogger') as mock_logger_class:
                mock_logger = Mock()
                mock_logger.log_action = AsyncMock()
                mock_logger_class.return_value = mock_logger
                
                await AuditLoggerMiddleware.log_api_access(
                    request=mock_request,
                    api_key_id=api_key_id,
                    granted=False,
                    reason="Insufficient permissions"
                )
                
                call_args = mock_logger.log_action.call_args[1]
                assert call_args["action"] == AuditAction.ACCESS_DENIED
                assert call_args["metadata"]["reason"] == "Insufficient permissions"
    
    @pytest.mark.asyncio
    async def test_log_api_access_error_handling(self):
        """Test error handling in middleware logging."""
        mock_request = Mock()
        mock_request.client = None  # No client info
        mock_request.headers = {}
        mock_request.url = Mock(path="/api/v1/test")
        mock_request.method = "POST"
        
        api_key_id = str(uuid.uuid4())
        
        with patch('services.api_audit_logger.get_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            with patch('services.api_audit_logger.APIAuditLogger') as mock_logger_class:
                # Simulate an error during logging
                mock_logger = Mock()
                mock_logger.log_action = AsyncMock(side_effect=Exception("DB Error"))
                mock_logger_class.return_value = mock_logger
                
                with patch('services.api_audit_logger.logger') as mock_logger_module:
                    await AuditLoggerMiddleware.log_api_access(
                        request=mock_request,
                        api_key_id=api_key_id,
                        granted=True
                    )
                    
                    # Verify error was logged
                    mock_logger_module.error.assert_called_once()
                    
                    # Verify rollback was called
                    mock_db.rollback.assert_called_once()
                    
                    # Verify close was called
                    mock_db.close.assert_called_once()