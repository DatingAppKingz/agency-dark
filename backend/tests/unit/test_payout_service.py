"""
Unit tests for enhanced PayoutService.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from modules.financial.application.payout_service import PayoutService
from modules.financial.domain.models import (
    Payout,
    PayoutStatus,
    BillingCycle,
    CryptoWallet,
    FinancialTransaction,
    TransactionType,
    PayoutSchedule
)
from modules.financial.domain.schemas import (
    PayoutRequest,
    PayoutScheduleCreate,
    PayoutApprovalRequest
)
from core.domain.models import User, UserRole, Agency, ModelProfile


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return User(
        id=uuid4(),
        agency_id=uuid4(),
        email="admin@example.com",
        role=UserRole.AGENCY_ADMIN,
        full_name="Admin User"
    )


@pytest.fixture
def mock_model_user():
    """Create a mock model user."""
    return User(
        id=uuid4(),
        agency_id=uuid4(),
        email="model@example.com",
        role=UserRole.MODEL,
        full_name="Test Model"
    )


@pytest.fixture
def mock_billing_cycle():
    """Create a mock billing cycle."""
    return BillingCycle(
        id=uuid4(),
        agency_id=uuid4(),
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=True,
        gross_revenue=Decimal("10000.00"),
        total_commission=Decimal("7000.00"),
        net_revenue=Decimal("3000.00")
    )


@pytest.fixture
def mock_crypto_wallet():
    """Create a mock crypto wallet."""
    return CryptoWallet(
        id=uuid4(),
        user_id=uuid4(),
        network="ethereum",
        address="0x1234567890abcdef",
        is_active=True,
        is_verified=True
    )


@pytest.fixture
def payout_service(mock_db):
    """Create a PayoutService instance."""
    return PayoutService(mock_db)


class TestPayoutService:
    """Test suite for enhanced PayoutService."""
    
    @pytest.mark.asyncio
    async def test_create_payout_schedule(self, payout_service, mock_user, mock_crypto_wallet):
        """Test creating automatic payout schedule."""
        # Arrange
        schedule_data = PayoutScheduleCreate(
            recipient_id=str(mock_crypto_wallet.user_id),
            recipient_type="model",
            frequency="weekly",
            minimum_amount=Decimal("100.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(mock_crypto_wallet.id)}
        )
        
        # Mock recipient lookup
        payout_service.db.get = AsyncMock(side_effect=[
            mock_user,  # Recipient user
            mock_crypto_wallet  # Wallet
        ])
        
        # Mock no existing schedule
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        payout_service.db.execute = AsyncMock(return_value=mock_result)
        
        payout_service.db.add = MagicMock()
        payout_service.db.commit = AsyncMock()
        payout_service.db.refresh = AsyncMock()
        
        # Act
        result = await payout_service.create_payout_schedule(schedule_data, mock_user)
        
        # Assert
        assert payout_service.db.add.called
        added_schedule = payout_service.db.add.call_args[0][0]
        assert added_schedule.frequency == "weekly"
        assert added_schedule.minimum_amount == Decimal("100.00")
        assert added_schedule.is_active is True
    
    @pytest.mark.asyncio
    async def test_create_schedule_duplicate_error(self, payout_service, mock_user):
        """Test error when creating duplicate active schedule."""
        # Arrange
        schedule_data = PayoutScheduleCreate(
            recipient_id=str(uuid4()),
            recipient_type="model",
            frequency="daily",
            minimum_amount=Decimal("50.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(uuid4())}
        )
        
        # Mock existing active schedule
        existing_schedule = PayoutSchedule(id=uuid4(), is_active=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_schedule
        
        payout_service.db.get = AsyncMock(return_value=mock_user)
        payout_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await payout_service.create_payout_schedule(schedule_data, mock_user)
        
        assert "already exists" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_process_scheduled_payouts_batch(self, payout_service, mock_user, mock_model_user):
        """Test batch processing of scheduled payouts."""
        # Arrange
        # Mock active schedules
        schedules = [
            PayoutSchedule(
                id=uuid4(),
                recipient_id=mock_model_user.id,
                recipient_type="model",
                frequency="weekly",
                minimum_amount=Decimal("50.00"),
                payment_method="crypto",
                payment_details={'wallet_id': str(uuid4())},
                next_payout_date=datetime.utcnow() - timedelta(hours=1),
                is_active=True
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = schedules
        
        # Mock calculate_payout_amount
        with patch.object(payout_service, '_calculate_payout_amount') as mock_calc:
            mock_calc.return_value = Decimal("500.00")  # Above minimum
            
            # Mock get_system_user
            with patch.object(payout_service, '_get_system_user') as mock_system:
                mock_system.return_value = mock_user
                
                # Mock create_payout
                with patch.object(payout_service, 'create_payout') as mock_create:
                    mock_payout = MagicMock(id=uuid4())
                    mock_create.return_value = mock_payout
                    
                    # Mock process_payout
                    with patch.object(payout_service, 'process_payout') as mock_process:
                        mock_process.return_value = None
                        
                        payout_service.db.execute = AsyncMock(return_value=mock_result)
                        payout_service.db.commit = AsyncMock()
                        
                        # Act
                        result = await payout_service.process_scheduled_payouts_batch()
        
        # Assert
        assert result.total_schedules == 1
        assert result.payouts_created == 1
        assert result.payouts_processed == 1
        assert result.payouts_failed == 0
        assert schedules[0].last_payout_amount == Decimal("500.00")
    
    @pytest.mark.asyncio
    async def test_skip_payout_below_minimum(self, payout_service, mock_user):
        """Test skipping payout when amount is below minimum."""
        # Arrange
        schedule = PayoutSchedule(
            recipient_id=uuid4(),
            recipient_type="model",
            minimum_amount=Decimal("100.00"),
            next_payout_date=datetime.utcnow() - timedelta(hours=1)
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        
        # Mock calculate_payout_amount to return below minimum
        with patch.object(payout_service, '_calculate_payout_amount') as mock_calc:
            mock_calc.return_value = Decimal("50.00")  # Below minimum
            
            with patch.object(payout_service, '_get_system_user') as mock_system:
                mock_system.return_value = mock_user
                
                payout_service.db.execute = AsyncMock(return_value=mock_result)
                payout_service.db.commit = AsyncMock()
                
                # Act
                result = await payout_service.process_scheduled_payouts_batch()
        
        # Assert
        assert result.payouts_created == 0  # No payout created
        assert result.total_schedules == 1
    
    @pytest.mark.asyncio
    async def test_retry_failed_payouts(self, payout_service):
        """Test retrying failed payouts with exponential backoff."""
        # Arrange
        failed_payouts = [
            Payout(
                id=uuid4(),
                status=PayoutStatus.FAILED,
                retry_count=1,
                processed_at=datetime.utcnow() - timedelta(hours=2),
                created_at=datetime.utcnow() - timedelta(hours=3)
            ),
            Payout(
                id=uuid4(),
                status=PayoutStatus.FAILED,
                retry_count=2,
                processed_at=datetime.utcnow() - timedelta(minutes=30),  # Too recent
                created_at=datetime.utcnow() - timedelta(hours=1)
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = failed_payouts
        
        payout_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Mock process_payout
        with patch.object(payout_service, 'process_payout') as mock_process:
            mock_process.return_value = None
            failed_payouts[0].status = PayoutStatus.COMPLETED  # Simulate success
            
            # Act
            result = await payout_service.retry_failed_payouts(max_age_hours=24)
        
        # Assert
        assert result['total_failed'] == 2
        assert result['retried'] == 1  # Only first payout (second is too recent)
        assert result['succeeded'] == 1
        assert result['still_failed'] == 0
    
    @pytest.mark.asyncio
    async def test_approve_payout(self, payout_service, mock_user):
        """Test payout approval workflow."""
        # Arrange
        payout_id = str(uuid4())
        payout = Payout(
            id=uuid4(),
            status=PayoutStatus.PENDING,
            amount=Decimal("1000.00"),
            metadata={}
        )
        
        approval = PayoutApprovalRequest(
            approved=True,
            notes="Approved for immediate processing",
            process_immediately=True
        )
        
        payout_service.db.get = AsyncMock(return_value=payout)
        payout_service.db.commit = AsyncMock()
        payout_service.db.refresh = AsyncMock()
        
        # Mock process_payout for immediate processing
        with patch.object(payout_service, 'process_payout') as mock_process:
            mock_process.return_value = None
            
            # Act
            result = await payout_service.approve_payout(payout_id, approval, mock_user)
        
        # Assert
        assert payout.metadata['approval']['approved'] is True
        assert payout.metadata['approval']['approver_id'] == str(mock_user.id)
        assert payout.metadata['approval']['notes'] == approval.notes
        assert mock_process.called  # Immediate processing
    
    @pytest.mark.asyncio
    async def test_reject_payout(self, payout_service, mock_user):
        """Test payout rejection."""
        # Arrange
        payout = Payout(
            id=uuid4(),
            status=PayoutStatus.PENDING,
            metadata={}
        )
        
        approval = PayoutApprovalRequest(
            approved=False,
            notes="Suspicious activity detected",
            process_immediately=False
        )
        
        payout_service.db.get = AsyncMock(return_value=payout)
        payout_service.db.commit = AsyncMock()
        payout_service.db.refresh = AsyncMock()
        
        # Act
        result = await payout_service.approve_payout(str(payout.id), approval, mock_user)
        
        # Assert
        assert payout.status == PayoutStatus.CANCELLED
        assert "Rejected by" in payout.failure_reason
        assert payout.metadata['approval']['approved'] is False
    
    @pytest.mark.asyncio
    async def test_calculate_next_payout_date(self, payout_service):
        """Test next payout date calculation for different frequencies."""
        now = datetime.utcnow()
        
        # Test daily
        next_date = payout_service._calculate_next_payout_date('daily')
        assert (next_date - now).days == 1
        
        # Test weekly
        next_date = payout_service._calculate_next_payout_date('weekly')
        assert (next_date - now).days == 7
        
        # Test biweekly
        next_date = payout_service._calculate_next_payout_date('biweekly')
        assert (next_date - now).days == 14
        
        # Test monthly
        next_date = payout_service._calculate_next_payout_date('monthly')
        # Should be next month
        assert next_date.month == (now.month % 12) + 1 or (
            next_date.month == 1 and now.month == 12
        )
    
    @pytest.mark.asyncio
    async def test_calculate_payout_amount_with_commission(self, payout_service):
        """Test payout amount calculation with commission deduction."""
        # Arrange
        schedule = PayoutSchedule(
            recipient_id=uuid4(),
            recipient_type='model',
            last_payout_date=datetime.utcnow() - timedelta(days=7)
        )
        
        # Mock revenue transactions
        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("1000.00")  # Gross revenue
        
        # Mock model profile
        model = ModelProfile(id=uuid4())
        model_result = MagicMock()
        model_result.scalar_one_or_none.return_value = model
        
        payout_service.db.execute = AsyncMock(side_effect=[mock_result, model_result])
        
        # Mock commission calculation
        from modules.financial.application.commission_service import CommissionService
        with patch.object(CommissionService, 'calculate_commission') as mock_calc:
            mock_calc.return_value = MagicMock(
                net_amount=Decimal("300.00")  # After 70% commission
            )
            
            # Act
            amount = await payout_service._calculate_payout_amount(schedule)
        
        # Assert
        assert amount == Decimal("300.00")
    
    @pytest.mark.asyncio
    async def test_max_retry_attempts_limit(self, payout_service):
        """Test that payouts exceeding max retry attempts are not retried."""
        # Arrange
        failed_payout = Payout(
            id=uuid4(),
            status=PayoutStatus.FAILED,
            retry_count=payout_service.MAX_RETRY_ATTEMPTS,  # At max
            processed_at=datetime.utcnow() - timedelta(hours=2),
            created_at=datetime.utcnow() - timedelta(hours=3)
        )
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No payouts match criteria
        
        payout_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act
        result = await payout_service.retry_failed_payouts()
        
        # Assert
        assert result['total_failed'] == 0
        assert result['retried'] == 0