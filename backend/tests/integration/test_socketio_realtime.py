"""
Integration tests for Socket.IO real-time features.
"""
import pytest
import asyncio
import json
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import socketio
from sqlalchemy.ext.asyncio import AsyncSession

from core.realtime.server import sio as server_sio
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionStatus,
    TransactionType
)
from modules.notifications.realtime.namespace import send_notification
from core.domain.models import UserRole, ModelProfile


class TestSocketIOIntegration:
    
    @pytest.fixture
    async def socketio_client(self):
        """Create Socket.IO test client."""
        client = socketio.AsyncClient()
        yield client
        if client.connected:
            await client.disconnect()
    
    @pytest.fixture
    def auth_token(self, test_user):
        """Generate auth token for test user."""
        from core.security import create_access_token
        return create_access_token(
            data={"sub": str(test_user.id)}
        )
    
    @pytest.mark.asyncio
    async def test_client_connection_with_auth(
        self,
        socketio_client,
        auth_token,
        test_user
    ):
        """Test client connection with authentication."""
        # Mock the server
        with pytest.mock.patch('core.realtime.server.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": str(test_user.id)}
            
            # Connect with auth
            await socketio_client.connect(
                'http://localhost:8000',
                auth={'token': auth_token},
                namespaces=['/']
            )
            
            assert socketio_client.connected
            
            # Should receive connection confirmation
            received = []
            
            @socketio_client.on('connected')
            def on_connected(data):
                received.append(data)
            
            # Wait for event
            await asyncio.sleep(0.1)
            
            assert len(received) > 0
            assert received[0]['user_id'] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_financial_namespace_payment_tracking(
        self,
        socketio_client,
        auth_token,
        test_agency_member,
        test_transaction,
        db_session: AsyncSession
    ):
        """Test payment tracking through financial namespace."""
        # Add transaction to db
        db_session.add(test_transaction)
        await db_session.commit()
        
        # Connect to financial namespace
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/financial']
        )
        
        # Track payment updates
        updates = []
        
        @socketio_client.on('payment_status_update', namespace='/financial')
        def on_payment_update(data):
            updates.append(data)
        
        # Start tracking payment
        await socketio_client.emit(
            'track_payment',
            {'transaction_id': str(test_transaction.id)},
            namespace='/financial'
        )
        
        # Simulate payment confirmation
        test_transaction.status = TransactionStatus.COMPLETED
        test_transaction.processed_at = datetime.utcnow()
        await db_session.commit()
        
        # Wait for update
        await asyncio.sleep(6)  # Wait for tracking interval
        
        # Should have received status update
        assert len(updates) > 0
        assert updates[0]['transaction_id'] == str(test_transaction.id)
        assert updates[0]['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_notification_delivery(
        self,
        socketio_client,
        auth_token,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test notification delivery through Socket.IO."""
        # Connect to notifications namespace
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/notifications']
        )
        
        # Listen for notifications
        notifications = []
        
        @socketio_client.on('payment_confirmed', namespace='/notifications')
        def on_notification(data):
            notifications.append(data)
        
        # Send notification via helper
        await send_notification(
            'payment_confirmed',
            {
                'transaction_id': str(uuid4()),
                'model_id': str(test_model_profile.id),
                'amount': 100.0,
                'currency': 'USD'
            }
        )
        
        # Wait for notification
        await asyncio.sleep(0.5)
        
        # Should have received notification
        assert len(notifications) > 0
        assert notifications[0]['amount'] == 100.0
    
    @pytest.mark.asyncio
    async def test_dashboard_metrics_subscription(
        self,
        socketio_client,
        auth_token,
        test_model_profile
    ):
        """Test dashboard metrics subscription."""
        # Connect to notifications namespace
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/notifications']
        )
        
        # Subscribe to metrics
        metrics_updates = []
        
        @socketio_client.on('metrics_update', namespace='/notifications')
        def on_metrics(data):
            metrics_updates.append(data)
        
        await socketio_client.emit(
            'subscribe_metrics',
            {
                'model_id': str(test_model_profile.id),
                'metrics': ['revenue_today', 'active_subscribers'],
                'interval': 2
            },
            namespace='/notifications'
        )
        
        # Wait for updates
        await asyncio.sleep(3)
        
        # Should have received at least one update
        assert len(metrics_updates) > 0
        assert 'revenue_today' in metrics_updates[0]['data']
        assert 'active_subscribers' in metrics_updates[0]['data']
    
    @pytest.mark.asyncio
    async def test_cross_namespace_communication(
        self,
        socketio_client,
        auth_token,
        test_transaction,
        db_session: AsyncSession
    ):
        """Test communication between namespaces."""
        # Connect to multiple namespaces
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/financial', '/notifications']
        )
        
        # Listen on both namespaces
        financial_events = []
        notification_events = []
        
        @socketio_client.on('payment_update', namespace='/financial')
        def on_financial_event(data):
            financial_events.append(data)
        
        @socketio_client.on('notification', namespace='/notifications')
        def on_notification_event(data):
            notification_events.append(data)
        
        # Trigger payment confirmation webhook
        from modules.financial.realtime.namespace import notify_payment_status
        test_transaction.status = TransactionStatus.COMPLETED
        await notify_payment_status(test_transaction, server_sio)
        
        # Wait for events
        await asyncio.sleep(0.5)
        
        # Should receive events on both namespaces
        assert len(financial_events) > 0
        assert financial_events[0]['transaction_id'] == str(test_transaction.id)
        
        # Notification namespace might also receive if configured
        # This depends on implementation details
    
    @pytest.mark.asyncio
    async def test_role_based_room_access(
        self,
        socketio_client,
        auth_token,
        test_super_admin
    ):
        """Test role-based room access."""
        # Connect as super admin
        with pytest.mock.patch('core.realtime.server.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": str(test_super_admin.id)}
            
            await socketio_client.connect(
                'http://localhost:8000',
                auth={'token': auth_token},
                namespaces=['/financial']
            )
            
            # Super admin should be in 'financial:all' room
            # Test by checking if they receive global events
            global_events = []
            
            @socketio_client.on('payment_update', namespace='/financial')
            def on_global_event(data):
                global_events.append(data)
            
            # Emit to global room
            await server_sio.emit(
                'payment_update',
                {'test': 'global_event'},
                room='financial:all',
                namespace='/financial'
            )
            
            await asyncio.sleep(0.1)
            
            # Super admin should receive it
            assert len(global_events) > 0
    
    @pytest.mark.asyncio
    async def test_disconnect_cleanup(
        self,
        socketio_client,
        auth_token,
        test_transaction
    ):
        """Test cleanup on disconnect."""
        # Connect and start tracking
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/financial']
        )
        
        # Start tracking payment
        await socketio_client.emit(
            'track_payment',
            {'transaction_id': str(test_transaction.id)},
            namespace='/financial'
        )
        
        # Get session ID (would be available in real scenario)
        # For test, we'll verify the behavior
        
        # Disconnect
        await socketio_client.disconnect()
        
        # Verify client is disconnected
        assert not socketio_client.connected
        
        # In real scenario, server would clean up tracking tasks
        # This is hard to test without access to server internals
    
    @pytest.mark.asyncio
    async def test_error_handling(
        self,
        socketio_client,
        auth_token
    ):
        """Test error handling in Socket.IO events."""
        await socketio_client.connect(
            'http://localhost:8000',
            auth={'token': auth_token},
            namespaces=['/financial']
        )
        
        errors = []
        
        @socketio_client.on('error', namespace='/financial')
        def on_error(data):
            errors.append(data)
        
        # Try to track non-existent transaction
        await socketio_client.emit(
            'track_payment',
            {'transaction_id': str(uuid4())},
            namespace='/financial'
        )
        
        await asyncio.sleep(0.1)
        
        # Should receive error
        assert len(errors) > 0
        assert 'not found' in errors[0]['message'].lower()


@pytest.fixture
async def test_transaction(test_model_profile):
    """Create test transaction."""
    return FinancialTransaction(
        id=uuid4(),
        agency_id=test_model_profile.agency_id,
        model_id=test_model_profile.id,
        amount=Decimal("100.00"),
        currency="USD",
        type=TransactionType.REVENUE,
        status=TransactionStatus.PENDING,
        external_reference="test_payment_123",
        transaction_date=datetime.utcnow()
    )