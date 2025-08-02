"""
Unit tests for financial Socket.IO namespace.
"""
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from modules.financial.realtime.namespace import (
    FinancialNamespace,
    notify_payment_status,
    notify_payout_status
)
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionStatus,
    TransactionType,
    Payout,
    PayoutStatus
)
from core.domain.models import UserRole, ModelProfile


class TestFinancialNamespace:
    
    @pytest.fixture
    def namespace(self):
        """Create financial namespace instance."""
        namespace = FinancialNamespace('/financial')
        namespace.server = MagicMock()
        namespace.emit = AsyncMock()
        namespace.get_session = AsyncMock()
        namespace.enter_room = MagicMock()
        return namespace
    
    @pytest.fixture
    def mock_session(self):
        """Create mock session data."""
        return {
            'user_id': str(uuid4()),
            'username': 'test_user',
            'role': UserRole.MEMBER,
            'agency_id': str(uuid4())
        }
    
    @pytest.fixture
    def mock_transaction(self):
        """Create mock transaction."""
        return FinancialTransaction(
            id=uuid4(),
            agency_id=uuid4(),
            model_id=uuid4(),
            amount=Decimal("100.00"),
            currency="USD",
            type=TransactionType.REVENUE,
            status=TransactionStatus.PENDING,
            external_reference="test_payment_123"
        )
    
    @pytest.mark.asyncio
    async def test_connect_success(self, namespace, mock_session):
        """Test successful connection to financial namespace."""
        namespace.get_session.return_value = mock_session
        
        result = await namespace.on_connect('test_sid', {})
        
        assert result is True
        namespace.enter_room.assert_called_with(
            'test_sid',
            f"financial:agency:{mock_session['agency_id']}"
        )
    
    @pytest.mark.asyncio
    async def test_connect_super_admin(self, namespace):
        """Test super admin connection gets all access."""
        session = {
            'user_id': str(uuid4()),
            'username': 'admin',
            'role': UserRole.SUPER_ADMIN,
            'agency_id': None
        }
        namespace.get_session.return_value = session
        
        result = await namespace.on_connect('test_sid', {})
        
        assert result is True
        namespace.enter_room.assert_called_with('test_sid', 'financial:all')
    
    @pytest.mark.asyncio
    async def test_track_payment_success(self, namespace, mock_session, mock_transaction):
        """Test tracking payment status."""
        namespace.get_session.return_value = mock_session
        mock_session['agency_id'] = str(mock_transaction.agency_id)
        
        with patch('modules.financial.realtime.namespace.AsyncSessionLocal') as mock_db:
            # Mock database session
            db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = db_session
            
            # Mock transaction query
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_transaction
            db_session.execute.return_value = mock_result
            
            # Start tracking
            await namespace.on_track_payment(
                'test_sid',
                {'transaction_id': str(mock_transaction.id)}
            )
            
            # Verify tracking started
            assert str(mock_transaction.id) in namespace.payment_trackers.get('test_sid', set())
            namespace.emit.assert_called_with(
                'tracking_started',
                {'transaction_id': str(mock_transaction.id)},
                room='test_sid'
            )
    
    @pytest.mark.asyncio
    async def test_track_payment_access_denied(self, namespace, mock_session, mock_transaction):
        """Test access denied when tracking payment from another agency."""
        namespace.get_session.return_value = mock_session
        mock_session['agency_id'] = str(uuid4())  # Different agency
        
        with patch('modules.financial.realtime.namespace.AsyncSessionLocal') as mock_db:
            db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = db_session
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_transaction
            db_session.execute.return_value = mock_result
            
            await namespace.on_track_payment(
                'test_sid',
                {'transaction_id': str(mock_transaction.id)}
            )
            
            # Should emit error
            namespace.emit.assert_called_with(
                'error',
                {'message': 'Access denied'},
                room='test_sid'
            )
    
    @pytest.mark.asyncio
    async def test_stop_tracking_payment(self, namespace):
        """Test stopping payment tracking."""
        transaction_id = str(uuid4())
        namespace.payment_trackers['test_sid'] = {transaction_id}
        
        # Mock task
        mock_task = MagicMock()
        namespace._tracker_tasks['test_sid'] = {f"payment_{transaction_id}": mock_task}
        
        await namespace.on_stop_tracking_payment(
            'test_sid',
            {'transaction_id': transaction_id}
        )
        
        # Verify tracking stopped
        assert transaction_id not in namespace.payment_trackers.get('test_sid', set())
        mock_task.cancel.assert_called_once()
        
        namespace.emit.assert_called_with(
            'tracking_stopped',
            {'transaction_id': transaction_id},
            room='test_sid'
        )
    
    @pytest.mark.asyncio
    async def test_subscribe_payouts_model(self, namespace, mock_session):
        """Test subscribing to model payout updates."""
        namespace.get_session.return_value = mock_session
        model_id = str(uuid4())
        
        with patch('modules.financial.realtime.namespace.AsyncSessionLocal') as mock_db:
            db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = db_session
            
            # Mock model with matching agency
            mock_model = ModelProfile(
                id=model_id,
                agency_id=mock_session['agency_id']
            )
            db_session.get.return_value = mock_model
            
            await namespace.on_subscribe_payouts(
                'test_sid',
                {'model_id': model_id}
            )
            
            namespace.enter_room.assert_called_with(
                'test_sid',
                f"payouts:model:{model_id}"
            )
            namespace.emit.assert_called_with(
                'subscribed_payouts',
                {'model_id': model_id},
                room='test_sid'
            )
    
    @pytest.mark.asyncio
    async def test_get_payment_stats(self, namespace, mock_session):
        """Test getting payment statistics."""
        namespace.get_session.return_value = mock_session
        
        with patch.object(namespace, '_get_payment_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_transactions': 10,
                'total_amount': 1000.0,
                'completed_transactions': 8,
                'completed_amount': 800.0
            }
            
            await namespace.on_get_payment_stats(
                'test_sid',
                {'period': 'today', 'model_id': str(uuid4())}
            )
            
            namespace.emit.assert_called_once()
            emitted_data = namespace.emit.call_args[0][1]
            assert emitted_data['total_transactions'] == 10
            assert emitted_data['total_amount'] == 1000.0
    
    @pytest.mark.asyncio
    async def test_payment_status_tracking_updates(self, namespace, mock_transaction):
        """Test payment status tracking sends updates."""
        mock_transaction.status = TransactionStatus.PENDING
        
        with patch('modules.financial.realtime.namespace.AsyncSessionLocal') as mock_db:
            db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = db_session
            
            # First call returns pending, second returns completed
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.side_effect = [
                mock_transaction,
                type('obj', (object,), {
                    'status': TransactionStatus.COMPLETED,
                    'amount': mock_transaction.amount,
                    'currency': mock_transaction.currency,
                    'processed_at': datetime.utcnow(),
                    'metadata': {}
                })()
            ]
            db_session.execute.return_value = mock_result
            
            # Run tracking briefly
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = asyncio.CancelledError
                
                try:
                    await namespace._track_payment_status(
                        'test_sid',
                        str(mock_transaction.id)
                    )
                except asyncio.CancelledError:
                    pass
            
            # Should have emitted status update
            namespace.emit.assert_called()
            call_args = namespace.emit.call_args[0]
            assert call_args[0] == 'payment_status_update'
            assert call_args[1]['status'] == TransactionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_notify_payment_status():
    """Test payment status notification helper."""
    transaction = FinancialTransaction(
        id=uuid4(),
        agency_id=uuid4(),
        model_id=uuid4(),
        amount=Decimal("100.00"),
        currency="USD",
        type=TransactionType.REVENUE,
        status=TransactionStatus.COMPLETED
    )
    
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()
    
    await notify_payment_status(transaction, mock_sio)
    
    # Should emit to agency room
    mock_sio.emit.assert_any_call(
        'payment_update',
        {
            'transaction_id': str(transaction.id),
            'model_id': str(transaction.model_id),
            'amount': 100.0,
            'currency': 'USD',
            'status': 'completed',
            'type': 'revenue',
            'timestamp': pytest.ANY
        },
        room=f"financial:agency:{transaction.agency_id}",
        namespace='/financial'
    )
    
    # Should also emit to super admin room
    assert mock_sio.emit.call_count == 2


@pytest.mark.asyncio
async def test_notify_payout_status():
    """Test payout status notification helper."""
    payout = Payout(
        id=uuid4(),
        model_id=uuid4(),
        amount=Decimal("500.00"),
        currency="USD",
        status=PayoutStatus.COMPLETED,
        payout_method="bank_transfer"
    )
    
    mock_sio = MagicMock()
    mock_sio.emit = AsyncMock()
    
    with patch('modules.financial.realtime.namespace.AsyncSessionLocal') as mock_db:
        db_session = AsyncMock()
        mock_db.return_value.__aenter__.return_value = db_session
        
        # Mock model
        mock_model = ModelProfile(
            id=payout.model_id,
            agency_id=uuid4()
        )
        db_session.get.return_value = mock_model
        
        await notify_payout_status(payout, mock_sio)
        
        # Should emit to model room
        mock_sio.emit.assert_any_call(
            'payout_update',
            {
                'payout_id': str(payout.id),
                'model_id': str(payout.model_id),
                'amount': 500.0,
                'currency': 'USD',
                'status': 'completed',
                'method': 'bank_transfer',
                'timestamp': pytest.ANY
            },
            room=f"payouts:model:{payout.model_id}",
            namespace='/financial'
        )