"""Comprehensive tests for financial models."""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.financial import (
    Earning, Payout, Commission, Transaction,
    EarningType, PayoutStatus, TransactionType,
    Currency
)
from models.user import User
from models.agency import Agency
from models.model import Model
from tests.factories import (
    create_test_agency, create_test_user, create_test_model
)


class TestEarningModel:
    """Test cases for Earning model."""
    
    @pytest.mark.asyncio
    async def test_create_earning_with_valid_data(self, db_session: AsyncSession):
        """Test creating an earning with all valid data."""
        # Setup
        agency = await create_test_agency()
        model = await create_test_model(agency=agency)
        
        # Create earning
        earning = Earning(
            model_id=model.id,
            agency_id=agency.id,
            amount=Decimal("100.00"),
            currency=Currency.USD,
            type=EarningType.SUBSCRIPTION,
            platform="onlyfans",
            platform_transaction_id="of_123",
            earned_at=datetime.utcnow()
        )
        
        db_session.add(earning)
        await db_session.commit()
        await db_session.refresh(earning)
        
        # Assertions
        assert earning.id is not None
        assert earning.amount == Decimal("100.00")
        assert earning.currency == Currency.USD
        assert earning.type == EarningType.SUBSCRIPTION
        assert earning.net_amount is None  # Not calculated yet
    
    @pytest.mark.asyncio
    async def test_earning_amount_validation(self, db_session: AsyncSession):
        """Test that earning amount must be positive."""
        model = await create_test_model()
        
        # Test negative amount
        with pytest.raises(ValueError, match="Amount must be positive"):
            earning = Earning(
                model_id=model.id,
                amount=Decimal("-10.00"),
                currency=Currency.USD,
                type=EarningType.TIP
            )
            earning.validate()
        
        # Test zero amount
        with pytest.raises(ValueError, match="Amount must be positive"):
            earning = Earning(
                model_id=model.id,
                amount=Decimal("0.00"),
                currency=Currency.USD,
                type=EarningType.TIP
            )
            earning.validate()
    
    @pytest.mark.asyncio
    async def test_earning_platform_fee_calculation(self, db_session: AsyncSession):
        """Test platform fee calculation for earnings."""
        model = await create_test_model()
        
        earning = Earning(
            model_id=model.id,
            amount=Decimal("100.00"),
            currency=Currency.USD,
            type=EarningType.SUBSCRIPTION,
            platform_fee_rate=Decimal("0.10")  # 10% platform fee
        )
        
        # Calculate platform fee
        platform_fee = earning.calculate_platform_fee()
        assert platform_fee == Decimal("10.00")
        assert earning.amount_after_platform_fee == Decimal("90.00")
    
    @pytest.mark.asyncio
    async def test_earning_currency_conversion(self, db_session: AsyncSession):
        """Test currency conversion for non-USD earnings."""
        model = await create_test_model()
        
        earning = Earning(
            model_id=model.id,
            amount=Decimal("100.00"),
            currency=Currency.EUR,
            type=EarningType.PPV,
            exchange_rate=Decimal("1.10")  # 1 EUR = 1.10 USD
        )
        
        # Calculate USD amount
        usd_amount = earning.get_usd_amount()
        assert usd_amount == Decimal("110.00")
    
    @pytest.mark.asyncio
    async def test_earning_types_have_different_fees(self, db_session: AsyncSession):
        """Test that different earning types can have different fee structures."""
        model = await create_test_model()
        
        # Subscription with standard fee
        subscription = Earning(
            model_id=model.id,
            amount=Decimal("100.00"),
            type=EarningType.SUBSCRIPTION,
            platform_fee_rate=Decimal("0.10")
        )
        assert subscription.calculate_platform_fee() == Decimal("10.00")
        
        # Tip with lower fee
        tip = Earning(
            model_id=model.id,
            amount=Decimal("100.00"),
            type=EarningType.TIP,
            platform_fee_rate=Decimal("0.05")
        )
        assert tip.calculate_platform_fee() == Decimal("5.00")


class TestCommissionModel:
    """Test cases for Commission model."""
    
    @pytest.mark.asyncio
    async def test_create_commission_from_earning(self, db_session: AsyncSession):
        """Test creating a commission from an earning."""
        agency = await create_test_agency(commission_rate=Decimal("0.20"))
        model = await create_test_model(agency=agency)
        
        earning = Earning(
            model_id=model.id,
            agency_id=agency.id,
            amount=Decimal("100.00"),
            platform_fee_rate=Decimal("0.10")
        )
        
        commission = Commission(
            earning_id=earning.id,
            agency_id=agency.id,
            model_id=model.id,
            rate=agency.commission_rate,
            gross_amount=earning.amount,
            platform_fee=earning.calculate_platform_fee(),
            commissionable_amount=earning.amount_after_platform_fee,
            amount=earning.amount_after_platform_fee * agency.commission_rate
        )
        
        assert commission.rate == Decimal("0.20")
        assert commission.platform_fee == Decimal("10.00")
        assert commission.commissionable_amount == Decimal("90.00")
        assert commission.amount == Decimal("18.00")  # 20% of 90
    
    @pytest.mark.asyncio
    async def test_commission_rate_validation(self, db_session: AsyncSession):
        """Test commission rate must be between 0 and 1."""
        earning = Earning(amount=Decimal("100.00"))
        
        # Test rate > 1
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 1"):
            commission = Commission(
                earning_id=earning.id,
                rate=Decimal("1.5"),
                amount=Decimal("150.00")
            )
            commission.validate()
        
        # Test negative rate
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 1"):
            commission = Commission(
                earning_id=earning.id,
                rate=Decimal("-0.1"),
                amount=Decimal("-10.00")
            )
            commission.validate()
    
    @pytest.mark.asyncio
    async def test_commission_with_custom_rate(self, db_session: AsyncSession):
        """Test commission calculation with custom model rate."""
        agency = await create_test_agency(commission_rate=Decimal("0.20"))
        model = await create_test_model(
            agency=agency,
            custom_commission_rate=Decimal("0.15")  # Custom 15% rate
        )
        
        earning = Earning(
            model_id=model.id,
            amount=Decimal("100.00"),
            platform_fee_rate=Decimal("0.00")
        )
        
        commission = Commission.calculate_from_earning(earning, model)
        assert commission.rate == Decimal("0.15")  # Uses custom rate
        assert commission.amount == Decimal("15.00")


class TestPayoutModel:
    """Test cases for Payout model."""
    
    @pytest.mark.asyncio
    async def test_create_payout_request(self, db_session: AsyncSession):
        """Test creating a payout request."""
        model = await create_test_model()
        
        payout = Payout(
            model_id=model.id,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            gross_earnings=Decimal("5000.00"),
            total_platform_fees=Decimal("500.00"),
            total_commission=Decimal("900.00"),  # 20% of 4500
            net_amount=Decimal("3600.00"),
            currency=Currency.USD,
            status=PayoutStatus.PENDING
        )
        
        db_session.add(payout)
        await db_session.commit()
        
        assert payout.id is not None
        assert payout.status == PayoutStatus.PENDING
        assert payout.net_amount == Decimal("3600.00")
        assert payout.paid_at is None
    
    @pytest.mark.asyncio
    async def test_payout_minimum_threshold(self, db_session: AsyncSession):
        """Test payout minimum threshold validation."""
        model = await create_test_model()
        
        # Below minimum threshold
        with pytest.raises(ValueError, match="Below minimum payout threshold"):
            payout = Payout(
                model_id=model.id,
                net_amount=Decimal("50.00"),  # Below $100 minimum
                status=PayoutStatus.PENDING
            )
            payout.validate_minimum_threshold(minimum=Decimal("100.00"))
    
    @pytest.mark.asyncio
    async def test_payout_status_transitions(self, db_session: AsyncSession):
        """Test valid payout status transitions."""
        payout = Payout(
            model_id="test",
            net_amount=Decimal("1000.00"),
            status=PayoutStatus.PENDING
        )
        
        # Valid transitions
        payout.transition_to_approved()
        assert payout.status == PayoutStatus.APPROVED
        assert payout.approved_at is not None
        
        payout.transition_to_processing()
        assert payout.status == PayoutStatus.PROCESSING
        
        payout.transition_to_completed(
            processor_reference="stripe_123",
            processor_fee=Decimal("2.50")
        )
        assert payout.status == PayoutStatus.COMPLETED
        assert payout.paid_at is not None
        assert payout.processor_reference == "stripe_123"
        assert payout.processor_fee == Decimal("2.50")
    
    @pytest.mark.asyncio
    async def test_payout_cancellation(self, db_session: AsyncSession):
        """Test payout cancellation with reason."""
        payout = Payout(
            model_id="test",
            net_amount=Decimal("1000.00"),
            status=PayoutStatus.PENDING
        )
        
        payout.cancel(reason="Model requested cancellation")
        assert payout.status == PayoutStatus.CANCELLED
        assert payout.cancelled_at is not None
        assert payout.cancellation_reason == "Model requested cancellation"
        
        # Cannot transition from cancelled
        with pytest.raises(ValueError, match="Cannot transition from cancelled"):
            payout.transition_to_approved()
    
    @pytest.mark.asyncio
    async def test_payout_period_overlap_check(self, db_session: AsyncSession):
        """Test checking for overlapping payout periods."""
        model = await create_test_model()
        
        # First payout
        payout1 = Payout(
            model_id=model.id,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
            net_amount=Decimal("1000.00"),
            status=PayoutStatus.COMPLETED
        )
        db_session.add(payout1)
        await db_session.commit()
        
        # Overlapping payout
        with pytest.raises(ValueError, match="Overlapping payout period"):
            payout2 = Payout(
                model_id=model.id,
                period_start=datetime(2024, 1, 15),
                period_end=datetime(2024, 2, 15),
                net_amount=Decimal("1000.00"),
                status=PayoutStatus.PENDING
            )
            await payout2.check_period_overlap(db_session)


class TestTransactionModel:
    """Test cases for Transaction model."""
    
    @pytest.mark.asyncio
    async def test_create_payout_transaction(self, db_session: AsyncSession):
        """Test creating a transaction for a payout."""
        payout = Payout(
            model_id="test",
            net_amount=Decimal("1000.00"),
            status=PayoutStatus.PROCESSING
        )
        
        transaction = Transaction(
            payout_id=payout.id,
            type=TransactionType.PAYOUT,
            amount=payout.net_amount,
            currency=Currency.USD,
            status="completed",
            processor="stripe",
            processor_reference="pi_123",
            processor_fee=Decimal("2.50")
        )
        
        assert transaction.type == TransactionType.PAYOUT
        assert transaction.amount == Decimal("1000.00")
        assert transaction.processor_fee == Decimal("2.50")
        assert transaction.net_amount == Decimal("997.50")
    
    @pytest.mark.asyncio
    async def test_transaction_idempotency(self, db_session: AsyncSession):
        """Test transaction idempotency key prevents duplicates."""
        transaction1 = Transaction(
            type=TransactionType.PAYOUT,
            amount=Decimal("1000.00"),
            idempotency_key="payout_123_attempt_1"
        )
        db_session.add(transaction1)
        await db_session.commit()
        
        # Duplicate with same idempotency key
        transaction2 = Transaction(
            type=TransactionType.PAYOUT,
            amount=Decimal("1000.00"),
            idempotency_key="payout_123_attempt_1"
        )
        db_session.add(transaction2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestFinancialCalculations:
    """Test complex financial calculations and scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_earning_to_payout_flow(self, db_session: AsyncSession):
        """Test the complete flow from earning to payout."""
        # Setup
        agency = await create_test_agency(commission_rate=Decimal("0.20"))
        model = await create_test_model(agency=agency)
        
        # Create multiple earnings
        earnings = []
        for i in range(5):
            earning = Earning(
                model_id=model.id,
                agency_id=agency.id,
                amount=Decimal("1000.00"),
                platform_fee_rate=Decimal("0.10"),
                type=EarningType.SUBSCRIPTION,
                earned_at=datetime.utcnow() - timedelta(days=i)
            )
            earnings.append(earning)
            db_session.add(earning)
        
        await db_session.commit()
        
        # Calculate totals
        gross_total = sum(e.amount for e in earnings)
        platform_fees = sum(e.calculate_platform_fee() for e in earnings)
        after_fees = gross_total - platform_fees
        commission_total = after_fees * agency.commission_rate
        net_total = after_fees - commission_total
        
        assert gross_total == Decimal("5000.00")
        assert platform_fees == Decimal("500.00")
        assert commission_total == Decimal("900.00")  # 20% of 4500
        assert net_total == Decimal("3600.00")
        
        # Create payout
        payout = Payout(
            model_id=model.id,
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            gross_earnings=gross_total,
            total_platform_fees=platform_fees,
            total_commission=commission_total,
            net_amount=net_total,
            status=PayoutStatus.PENDING
        )
        
        assert payout.net_amount == Decimal("3600.00")
    
    @pytest.mark.asyncio
    async def test_multi_currency_payout_calculation(self, db_session: AsyncSession):
        """Test payout calculation with multiple currencies."""
        model = await create_test_model()
        
        # Earnings in different currencies
        usd_earning = Earning(
            model_id=model.id,
            amount=Decimal("1000.00"),
            currency=Currency.USD,
            exchange_rate=Decimal("1.00")
        )
        
        eur_earning = Earning(
            model_id=model.id,
            amount=Decimal("1000.00"),
            currency=Currency.EUR,
            exchange_rate=Decimal("1.10")  # 1 EUR = 1.10 USD
        )
        
        gbp_earning = Earning(
            model_id=model.id,
            amount=Decimal("1000.00"),
            currency=Currency.GBP,
            exchange_rate=Decimal("1.25")  # 1 GBP = 1.25 USD
        )
        
        # Calculate total in USD
        total_usd = (
            usd_earning.get_usd_amount() +
            eur_earning.get_usd_amount() +
            gbp_earning.get_usd_amount()
        )
        
        assert total_usd == Decimal("3350.00")  # 1000 + 1100 + 1250
    
    @pytest.mark.asyncio
    async def test_retroactive_commission_adjustment(self, db_session: AsyncSession):
        """Test handling retroactive commission rate changes."""
        agency = await create_test_agency(commission_rate=Decimal("0.20"))
        model = await create_test_model(agency=agency)
        
        # Original earning and commission
        earning = Earning(
            model_id=model.id,
            amount=Decimal("1000.00"),
            platform_fee_rate=Decimal("0.00")
        )
        
        original_commission = Commission(
            earning_id=earning.id,
            rate=Decimal("0.20"),
            amount=Decimal("200.00")
        )
        
        # Adjustment for new rate (15%)
        adjustment_commission = Commission(
            earning_id=earning.id,
            rate=Decimal("0.15"),
            amount=Decimal("-50.00"),  # Negative adjustment
            is_adjustment=True,
            adjustment_reason="Retroactive rate change to 15%"
        )
        
        # Total commission after adjustment
        total_commission = original_commission.amount + adjustment_commission.amount
        assert total_commission == Decimal("150.00")  # 15% of 1000