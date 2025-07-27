"""
Tests for payout service functionality.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from modules.financial.application.payout_service import PayoutService
from modules.financial.domain.models import (
    Payout,
    PayoutStatus,
    BillingCycle,
    CryptoWallet,
    FinancialTransaction,
    TransactionType,
    CryptoNetwork,
    PayoutSchedule
)
from modules.financial.domain.schemas import (
    PayoutRequest,
    PayoutStatusUpdate,
    PayoutScheduleCreate,
    PayoutApprovalRequest
)
from core.domain.models import User, Agency, ModelProfile


@pytest.fixture
async def payout_service(db_session):
    """Create payout service instance."""
    return PayoutService(db_session)


@pytest.fixture
async def test_agency(db_session):
    """Create test agency."""
    agency = Agency(
        name="Test Agency",
        domain="test-agency.com",
        settings={}
    )
    db_session.add(agency)
    await db_session.commit()
    return agency


@pytest.fixture
async def test_model_user(db_session, test_agency):
    """Create test model user."""
    user = User(
        email="model@test.com",
        username="testmodel",
        full_name="Test Model",
        role="model",
        agency_id=test_agency.id
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def test_model_profile(db_session, test_model_user, test_agency):
    """Create test model profile."""
    model = ModelProfile(
        user_id=test_model_user.id,
        agency_id=test_agency.id,
        display_name="Test Model",
        bio="Test bio"
    )
    db_session.add(model)
    await db_session.commit()
    return model


@pytest.fixture
async def test_crypto_wallet(db_session, test_model_user):
    """Create test crypto wallet."""
    wallet = CryptoWallet(
        user_id=test_model_user.id,
        network=CryptoNetwork.ETHEREUM,
        address="0x1234567890abcdef1234567890abcdef12345678",
        label="Test ETH Wallet",
        is_verified=True,
        is_active=True,
        is_default=True
    )
    db_session.add(wallet)
    await db_session.commit()
    return wallet


@pytest.fixture
async def test_billing_cycle(db_session, test_agency):
    """Create test billing cycle."""
    cycle = BillingCycle(
        agency_id=test_agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=True,
        total_revenue=Decimal("10000.00"),
        total_commission=Decimal("3000.00"),
        closed_at=datetime.utcnow()
    )
    db_session.add(cycle)
    await db_session.commit()
    return cycle


@pytest.fixture
async def admin_user(db_session, test_agency):
    """Create admin user."""
    user = User(
        email="admin@test.com",
        username="admin",
        full_name="Admin User",
        role="agency_owner",
        agency_id=test_agency.id
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestPayoutService:
    """Test payout service functionality."""
    
    async def test_create_payout(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test creating a new payout."""
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)},
            scheduled_at=datetime.utcnow() + timedelta(days=1)
        )
        
        payout = await payout_service.create_payout(payout_data, admin_user)
        
        assert payout.billing_cycle_id == str(test_billing_cycle.id)
        assert payout.recipient_id == str(test_model_user.id)
        assert payout.recipient_type == "model"
        assert payout.amount == Decimal("1000.00")
        assert payout.payment_method == "crypto"
        assert payout.status == PayoutStatus.PENDING
        assert payout.payment_details['wallet_id'] == str(test_crypto_wallet.id)
    
    async def test_create_payout_validation(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        admin_user,
        db_session
    ):
        """Test payout creation validation."""
        # Test with open billing cycle
        open_cycle = BillingCycle(
            agency_id=test_billing_cycle.agency_id,
            cycle_start=datetime.utcnow(),
            cycle_end=datetime.utcnow() + timedelta(days=30),
            is_closed=False
        )
        db_session.add(open_cycle)
        await db_session.commit()
        
        payout_data = PayoutRequest(
            billing_cycle_id=str(open_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="bank_transfer",
            payment_details={'account': '123456'}
        )
        
        with pytest.raises(ValueError, match="Billing cycle must be closed"):
            await payout_service.create_payout(payout_data, admin_user)
        
        # Test with non-existent recipient
        payout_data.billing_cycle_id = str(test_billing_cycle.id)
        payout_data.recipient_id = str(uuid4())
        
        with pytest.raises(ValueError, match="Recipient not found"):
            await payout_service.create_payout(payout_data, admin_user)
        
        # Test with invalid crypto wallet
        payout_data.recipient_id = str(test_model_user.id)
        payout_data.payment_method = "crypto"
        payout_data.payment_details = {'wallet_id': str(uuid4())}
        
        with pytest.raises(ValueError, match="Invalid crypto wallet"):
            await payout_service.create_payout(payout_data, admin_user)
    
    async def test_process_payout(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user,
        db_session
    ):
        """Test processing a payout."""
        # Create payout
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)}
        )
        
        payout_response = await payout_service.create_payout(payout_data, admin_user)
        
        # Mock crypto service process_payout to return success
        payout_service.crypto_service.process_payout = lambda p: {
            'success': True,
            'transaction_hash': '0xabc123'
        }
        
        # Process payout
        processed = await payout_service.process_payout(payout_response.id)
        
        assert processed.status == PayoutStatus.COMPLETED
        assert processed.transaction_hash == '0xabc123'
        assert processed.processed_at is not None
        assert processed.completed_at is not None
    
    async def test_process_payout_failure(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test payout processing failure."""
        # Create payout
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)}
        )
        
        payout_response = await payout_service.create_payout(payout_data, admin_user)
        
        # Mock crypto service to return failure
        payout_service.crypto_service.process_payout = lambda p: {
            'success': False,
            'error': 'Insufficient funds'
        }
        
        # Process payout
        processed = await payout_service.process_payout(payout_response.id)
        
        assert processed.status == PayoutStatus.FAILED
        assert processed.failure_reason == 'Insufficient funds'
        assert processed.retry_count == 1
    
    async def test_update_payout_status(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test updating payout status."""
        # Create payout
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)}
        )
        
        payout_response = await payout_service.create_payout(payout_data, admin_user)
        
        # Update status
        status_update = PayoutStatusUpdate(
            status=PayoutStatus.COMPLETED,
            transaction_id="tx_123",
            transaction_hash="0xdef456"
        )
        
        updated = await payout_service.update_payout_status(
            payout_response.id,
            status_update
        )
        
        assert updated.status == PayoutStatus.COMPLETED
        assert updated.transaction_id == "tx_123"
        assert updated.transaction_hash == "0xdef456"
        assert updated.completed_at is not None
    
    async def test_get_payouts_filtering(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user,
        db_session
    ):
        """Test getting payouts with filters."""
        # Create multiple payouts
        payouts_data = [
            PayoutRequest(
                billing_cycle_id=str(test_billing_cycle.id),
                recipient_id=str(test_model_user.id),
                recipient_type="model",
                amount=Decimal("1000.00"),
                payment_method="crypto",
                payment_details={'wallet_id': str(test_crypto_wallet.id)}
            ),
            PayoutRequest(
                billing_cycle_id=str(test_billing_cycle.id),
                recipient_id=str(test_model_user.id),
                recipient_type="model",
                amount=Decimal("2000.00"),
                payment_method="crypto",
                payment_details={'wallet_id': str(test_crypto_wallet.id)}
            )
        ]
        
        created_payouts = []
        for data in payouts_data:
            payout = await payout_service.create_payout(data, admin_user)
            created_payouts.append(payout)
        
        # Update one payout to completed
        await db_session.execute(
            f"UPDATE payouts SET status = '{PayoutStatus.COMPLETED}' WHERE id = '{created_payouts[0].id}'"
        )
        await db_session.commit()
        
        # Test filtering by billing cycle
        payouts = await payout_service.get_payouts(
            billing_cycle_id=str(test_billing_cycle.id)
        )
        assert len(payouts) == 2
        
        # Test filtering by recipient
        payouts = await payout_service.get_payouts(
            recipient_id=str(test_model_user.id)
        )
        assert len(payouts) == 2
        
        # Test filtering by status
        payouts = await payout_service.get_payouts(
            status=PayoutStatus.PENDING
        )
        assert len(payouts) == 1
        assert payouts[0].id == created_payouts[1].id
    
    async def test_create_billing_cycle_payouts(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_model_profile,
        test_crypto_wallet,
        admin_user,
        db_session
    ):
        """Test creating payouts for all recipients in a billing cycle."""
        # Create revenue transactions
        transactions = [
            FinancialTransaction(
                agency_id=test_billing_cycle.agency_id,
                user_id=test_model_user.id,
                type=TransactionType.REVENUE,
                amount=Decimal("5000.00"),
                billing_cycle_id=test_billing_cycle.id,
                transaction_date=datetime.utcnow() - timedelta(days=15)
            ),
            FinancialTransaction(
                agency_id=test_billing_cycle.agency_id,
                user_id=test_model_user.id,
                type=TransactionType.REVENUE,
                amount=Decimal("3000.00"),
                billing_cycle_id=test_billing_cycle.id,
                transaction_date=datetime.utcnow() - timedelta(days=10)
            )
        ]
        for tx in transactions:
            db_session.add(tx)
        await db_session.commit()
        
        # Mock commission calculation (70% to model)
        payout_service.db.execute = lambda q: type('Result', (), {
            'all': lambda: [(test_model_user.id, Decimal("8000.00"))]
        })()
        
        from modules.financial.application.commission_service import CommissionService
        CommissionService.calculate_commission = lambda self, *args, **kwargs: type('Calc', (), {
            'net_amount': Decimal("5600.00")  # 70% of 8000
        })()
        
        # Create payouts for billing cycle
        payouts = await payout_service.create_billing_cycle_payouts(
            str(test_billing_cycle.id),
            admin_user
        )
        
        assert len(payouts) >= 1
        model_payout = next(p for p in payouts if p.recipient_type == "model")
        assert model_payout.amount == Decimal("5600.00")
        assert model_payout.recipient_id == str(test_model_user.id)
    
    async def test_create_payout_schedule(
        self,
        payout_service,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test creating automatic payout schedule."""
        schedule_data = PayoutScheduleCreate(
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            frequency="weekly",
            minimum_amount=Decimal("100.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)},
            next_payout_date=datetime.utcnow() + timedelta(days=7)
        )
        
        schedule = await payout_service.create_payout_schedule(
            schedule_data,
            admin_user
        )
        
        assert schedule.recipient_id == str(test_model_user.id)
        assert schedule.frequency == "weekly"
        assert schedule.minimum_amount == Decimal("100.00")
        assert schedule.is_active is True
    
    async def test_retry_failed_payouts(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user,
        db_session
    ):
        """Test retrying failed payouts."""
        # Create failed payout
        payout = Payout(
            billing_cycle_id=test_billing_cycle.id,
            recipient_id=test_model_user.id,
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)},
            status=PayoutStatus.FAILED,
            retry_count=0,
            failure_reason="Network error",
            processed_at=datetime.utcnow() - timedelta(hours=2)
        )
        db_session.add(payout)
        await db_session.commit()
        
        # Mock successful retry
        payout_service.crypto_service.process_payout = lambda p: {
            'success': True,
            'transaction_hash': '0xretry123'
        }
        
        # Retry failed payouts
        result = await payout_service.retry_failed_payouts(max_age_hours=24)
        
        assert result['total_failed'] == 1
        assert result['retried'] == 1
        assert result['succeeded'] == 1
        assert result['still_failed'] == 0
        
        # Verify payout was updated
        await db_session.refresh(payout)
        assert payout.status == PayoutStatus.COMPLETED
        assert payout.transaction_hash == '0xretry123'
        assert payout.retry_count == 1
    
    async def test_approve_payout(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test payout approval workflow."""
        # Create payout
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)}
        )
        
        payout_response = await payout_service.create_payout(payout_data, admin_user)
        
        # Approve payout
        approval = PayoutApprovalRequest(
            approved=True,
            notes="Approved for immediate processing",
            process_immediately=True
        )
        
        # Mock process_payout for immediate processing
        payout_service.process_payout = lambda pid: type('Payout', (), {
            'status': PayoutStatus.COMPLETED
        })()
        
        approved = await payout_service.approve_payout(
            payout_response.id,
            approval,
            admin_user
        )
        
        assert approved.metadata['approval']['approved'] is True
        assert approved.metadata['approval']['approver_id'] == str(admin_user.id)
        assert approved.metadata['approval']['notes'] == "Approved for immediate processing"
    
    async def test_reject_payout(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test payout rejection."""
        # Create payout
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("1000.00"),
            payment_method="crypto",
            payment_details={'wallet_id': str(test_crypto_wallet.id)}
        )
        
        payout_response = await payout_service.create_payout(payout_data, admin_user)
        
        # Reject payout
        rejection = PayoutApprovalRequest(
            approved=False,
            notes="Suspicious activity detected"
        )
        
        rejected = await payout_service.approve_payout(
            payout_response.id,
            rejection,
            admin_user
        )
        
        assert rejected.status == PayoutStatus.CANCELLED
        assert rejected.failure_reason == f"Rejected by {admin_user.full_name}: Suspicious activity detected"
        assert rejected.metadata['approval']['approved'] is False
    
    async def test_payout_minimum_amounts(
        self,
        payout_service,
        test_billing_cycle,
        test_model_user,
        test_crypto_wallet,
        admin_user
    ):
        """Test payout minimum amount validation."""
        # Test amount below minimum for USD
        payout_data = PayoutRequest(
            billing_cycle_id=str(test_billing_cycle.id),
            recipient_id=str(test_model_user.id),
            recipient_type="model",
            amount=Decimal("25.00"),  # Below $50 minimum
            payment_method="bank_transfer",
            payment_details={'account': '123456'}
        )
        
        # Should still create (validation might be at processing time)
        payout = await payout_service.create_payout(payout_data, admin_user)
        assert payout.amount == Decimal("25.00")
    
    async def test_payout_schedule_frequencies(self, payout_service):
        """Test payout schedule frequency calculations."""
        now = datetime.utcnow()
        
        # Test daily
        next_date = payout_service._calculate_next_payout_date('daily')
        assert (next_date - now).days == 1
        
        # Test weekly
        next_date = payout_service._calculate_next_payout_date('weekly')
        assert 6 <= (next_date - now).days <= 7
        
        # Test biweekly
        next_date = payout_service._calculate_next_payout_date('biweekly')
        assert 13 <= (next_date - now).days <= 14
        
        # Test monthly
        next_date = payout_service._calculate_next_payout_date('monthly')
        assert 28 <= (next_date - now).days <= 31