"""
Tests for commission calculator service.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from modules.financial.application.commission_calculator import CommissionCalculator
from modules.financial.domain.models import (
    CommissionRule,
    CommissionTier,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    CommissionRuleCreate,
    CommissionOverrideRequest
)
from core.domain.models import User, Agency, ModelProfile


@pytest.fixture
async def commission_calculator(db_session):
    """Create commission calculator instance."""
    return CommissionCalculator(db_session)


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
async def test_model(db_session, test_agency):
    """Create test model profile."""
    user = User(
        email="model@test.com",
        username="testmodel",
        full_name="Test Model",
        role="model",
        agency_id=test_agency.id
    )
    db_session.add(user)
    await db_session.flush()
    
    model = ModelProfile(
        user_id=user.id,
        agency_id=test_agency.id,
        display_name="Test Model",
        bio="Test bio"
    )
    db_session.add(model)
    await db_session.commit()
    return model


class TestCommissionCalculator:
    """Test commission calculator functionality."""
    
    async def test_calculate_commission_default_tier(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test commission calculation with default tier."""
        # Create default commission rule
        rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),  # 70% to model
            is_active=True
        )
        commission_calculator.db.add(rule)
        await commission_calculator.db.commit()
        
        # Calculate commission
        gross_amount = Decimal("1000.00")
        calculation = await commission_calculator.calculate_commission(
            gross_amount=gross_amount,
            agency_id=test_agency.id
        )
        
        # Verify calculation
        assert calculation.gross_amount == gross_amount
        assert calculation.commission_rate == Decimal("30.00")  # 30% to agency
        assert calculation.commission_amount == Decimal("300.00")
        assert calculation.net_amount == Decimal("700.00")  # 70% to model
        assert calculation.tier == CommissionTier.TIER_1
    
    async def test_calculate_commission_model_specific(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test commission calculation with model-specific rule."""
        # Create agency-wide rule
        agency_rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),
            is_active=True
        )
        commission_calculator.db.add(agency_rule)
        
        # Create model-specific rule (higher priority)
        model_rule = CommissionRule(
            agency_id=test_agency.id,
            model_id=test_model.id,
            tier=CommissionTier.TIER_2,
            rate=Decimal("65.00"),  # 65% to model
            is_active=True
        )
        commission_calculator.db.add(model_rule)
        await commission_calculator.db.commit()
        
        # Calculate commission
        gross_amount = Decimal("1000.00")
        calculation = await commission_calculator.calculate_commission(
            gross_amount=gross_amount,
            agency_id=test_agency.id,
            model_id=test_model.id
        )
        
        # Should use model-specific rule
        assert calculation.commission_rate == Decimal("35.00")  # 35% to agency
        assert calculation.commission_amount == Decimal("350.00")
        assert calculation.net_amount == Decimal("650.00")  # 65% to model
        assert calculation.tier == CommissionTier.TIER_2
    
    async def test_calculate_commission_custom_rate(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test commission calculation with custom rate."""
        # Create custom rate rule
        rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.CUSTOM,
            rate=Decimal("80.00"),  # 80% to model
            is_active=True
        )
        commission_calculator.db.add(rule)
        await commission_calculator.db.commit()
        
        # Calculate commission
        gross_amount = Decimal("1000.00")
        calculation = await commission_calculator.calculate_commission(
            gross_amount=gross_amount,
            agency_id=test_agency.id
        )
        
        # Verify custom rate
        assert calculation.commission_rate == Decimal("20.00")  # 20% to agency
        assert calculation.commission_amount == Decimal("200.00")
        assert calculation.net_amount == Decimal("800.00")  # 80% to model
        assert calculation.tier == CommissionTier.CUSTOM
    
    async def test_calculate_tiered_commission(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test tiered commission calculation based on revenue."""
        # Create tiered rules
        rules = [
            CommissionRule(
                agency_id=test_agency.id,
                tier=CommissionTier.TIER_1,
                rate=Decimal("70.00"),
                revenue_threshold=Decimal("0.00"),
                is_active=True
            ),
            CommissionRule(
                agency_id=test_agency.id,
                tier=CommissionTier.TIER_2,
                rate=Decimal("65.00"),
                revenue_threshold=Decimal("5000.00"),
                is_active=True
            ),
            CommissionRule(
                agency_id=test_agency.id,
                tier=CommissionTier.TIER_3,
                rate=Decimal("60.00"),
                revenue_threshold=Decimal("10000.00"),
                is_active=True
            )
        ]
        for rule in rules:
            commission_calculator.db.add(rule)
        await commission_calculator.db.commit()
        
        # Test Tier 1 (revenue < 5000)
        calculation = await commission_calculator.calculate_tiered_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id,
            model_id=test_model.id,
            total_revenue=Decimal("3000.00")
        )
        assert calculation.tier == CommissionTier.TIER_1
        assert calculation.commission_rate == Decimal("30.00")
        
        # Test Tier 2 (5000 <= revenue < 10000)
        calculation = await commission_calculator.calculate_tiered_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id,
            model_id=test_model.id,
            total_revenue=Decimal("7000.00")
        )
        assert calculation.tier == CommissionTier.TIER_2
        assert calculation.commission_rate == Decimal("35.00")
        
        # Test Tier 3 (revenue >= 10000)
        calculation = await commission_calculator.calculate_tiered_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id,
            model_id=test_model.id,
            total_revenue=Decimal("15000.00")
        )
        assert calculation.tier == CommissionTier.TIER_3
        assert calculation.commission_rate == Decimal("40.00")
    
    async def test_create_commission_rule(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test creating a new commission rule."""
        creator = User(
            email="admin@test.com",
            username="admin",
            full_name="Admin User",
            role="super_admin"
        )
        commission_calculator.db.add(creator)
        await commission_calculator.db.flush()
        
        rule_data = CommissionRuleCreate(
            agency_id=str(test_agency.id),
            model_id=str(test_model.id),
            tier=CommissionTier.TIER_2,
            rate=Decimal("65.00"),
            effective_from=datetime.utcnow(),
            notes="Special rate for top performer"
        )
        
        rule = await commission_calculator.create_commission_rule(
            rule_data=rule_data,
            created_by_id=creator.id
        )
        
        assert rule.agency_id == test_agency.id
        assert rule.model_id == test_model.id
        assert rule.tier == CommissionTier.TIER_2
        assert rule.rate == Decimal("65.00")
        assert rule.is_active is True
        assert rule.notes == "Special rate for top performer"
    
    async def test_override_commission(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test commission override functionality."""
        # Create base rule
        base_rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),
            is_active=True
        )
        commission_calculator.db.add(base_rule)
        await commission_calculator.db.commit()
        
        # Create override
        override_user = User(
            email="super@test.com",
            username="superadmin",
            full_name="Super Admin",
            role="super_admin"
        )
        commission_calculator.db.add(override_user)
        await commission_calculator.db.flush()
        
        override_request = CommissionOverrideRequest(
            rate=Decimal("60.00"),  # Override to 60% for model
            reason="Promotional rate for new model",
            effective_from=datetime.utcnow(),
            effective_until=datetime.utcnow() + timedelta(days=90)
        )
        
        override_rule = await commission_calculator.override_commission(
            agency_id=test_agency.id,
            model_id=test_model.id,
            override_request=override_request,
            override_by_id=override_user.id
        )
        
        assert override_rule.rate == Decimal("60.00")
        assert override_rule.is_override is True
        assert override_rule.override_reason == "Promotional rate for new model"
        assert override_rule.effective_until is not None
    
    async def test_commission_adjustment(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test creating commission adjustments."""
        creator = User(
            email="admin@test.com",
            username="admin",
            full_name="Admin User",
            role="agency_owner",
            agency_id=test_agency.id
        )
        commission_calculator.db.add(creator)
        await commission_calculator.db.flush()
        
        from modules.financial.domain.schemas import CommissionAdjustmentCreate
        
        adjustment_data = CommissionAdjustmentCreate(
            agency_id=str(test_agency.id),
            model_id=str(test_model.id),
            amount=Decimal("-50.00"),  # Debit adjustment
            type=TransactionType.ADJUSTMENT,
            reason="Refund for disputed transaction",
            description="Customer dispute resolved in customer favor"
        )
        
        transaction = await commission_calculator.create_commission_adjustment(
            adjustment_data=adjustment_data,
            created_by_id=creator.id
        )
        
        assert transaction.type == TransactionType.ADJUSTMENT
        assert transaction.amount == Decimal("-50.00")
        assert transaction.description == "Customer dispute resolved in customer favor"
        assert transaction.metadata["adjustment_reason"] == "Refund for disputed transaction"
    
    async def test_bulk_calculate_commission(
        self,
        commission_calculator,
        test_agency,
        test_model,
        db_session
    ):
        """Test bulk commission calculation for billing cycle."""
        # Create commission rule
        rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),
            is_active=True
        )
        db_session.add(rule)
        
        # Create billing cycle
        from modules.financial.domain.models import BillingCycle
        cycle = BillingCycle(
            agency_id=test_agency.id,
            cycle_start=datetime.utcnow() - timedelta(days=30),
            cycle_end=datetime.utcnow()
        )
        db_session.add(cycle)
        await db_session.flush()
        
        # Create test transactions
        transactions = [
            FinancialTransaction(
                agency_id=test_agency.id,
                model_id=test_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("500.00"),
                billing_cycle_id=cycle.id,
                transaction_date=datetime.utcnow() - timedelta(days=15)
            ),
            FinancialTransaction(
                agency_id=test_agency.id,
                model_id=test_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("750.00"),
                billing_cycle_id=cycle.id,
                transaction_date=datetime.utcnow() - timedelta(days=10)
            ),
            FinancialTransaction(
                agency_id=test_agency.id,
                model_id=test_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("250.00"),
                billing_cycle_id=cycle.id,
                transaction_date=datetime.utcnow() - timedelta(days=5)
            )
        ]
        for tx in transactions:
            db_session.add(tx)
        await db_session.commit()
        
        # Calculate bulk commission
        calculations = await commission_calculator.bulk_calculate_commission(
            billing_cycle_id=cycle.id
        )
        
        assert len(calculations) == 1  # One model
        calc = calculations[0]
        assert calc.gross_amount == Decimal("1500.00")  # Total revenue
        assert calc.commission_amount == Decimal("450.00")  # 30% commission
        assert calc.net_amount == Decimal("1050.00")  # 70% to model
        assert calc.tier == CommissionTier.TIER_1
    
    async def test_commission_report_generation(
        self,
        commission_calculator,
        test_agency,
        test_model,
        db_session
    ):
        """Test commission report generation."""
        # Create commission rule
        rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),
            is_active=True
        )
        db_session.add(rule)
        
        # Create test transactions
        transactions = [
            FinancialTransaction(
                agency_id=test_agency.id,
                model_id=test_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("1000.00"),
                commission_amount=Decimal("300.00"),
                transaction_date=datetime.utcnow() - timedelta(days=5)
            ),
            FinancialTransaction(
                agency_id=test_agency.id,
                model_id=test_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("1500.00"),
                commission_amount=Decimal("450.00"),
                transaction_date=datetime.utcnow() - timedelta(days=3)
            )
        ]
        for tx in transactions:
            db_session.add(tx)
        await db_session.commit()
        
        # Generate report
        from modules.financial.domain.schemas import CommissionReportFilter
        
        filter_params = CommissionReportFilter(
            agency_id=str(test_agency.id),
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow()
        )
        
        creator = User(
            email="reporter@test.com",
            username="reporter",
            full_name="Reporter",
            role="agency_owner",
            agency_id=test_agency.id
        )
        db_session.add(creator)
        await db_session.flush()
        
        report = await commission_calculator.generate_commission_report(
            filter_params=filter_params,
            generated_by_id=creator.id
        )
        
        assert report.total_revenue == Decimal("2500.00")
        assert report.total_commission == Decimal("750.00")
        assert report.total_net_payout == Decimal("1750.00")
        assert report.average_commission_rate == Decimal("30.00")
        assert report.transaction_count == 2
        assert len(report.model_breakdowns) == 1
        
        model_breakdown = report.model_breakdowns[0]
        assert model_breakdown["model_id"] == str(test_model.id)
        assert model_breakdown["total_revenue"] == Decimal("2500.00")
        assert model_breakdown["total_commission"] == Decimal("750.00")
    
    async def test_commission_rate_validation(
        self,
        commission_calculator,
        test_agency
    ):
        """Test commission rate validation."""
        creator = User(
            email="admin@test.com",
            username="admin",
            full_name="Admin User",
            role="super_admin"
        )
        commission_calculator.db.add(creator)
        await commission_calculator.db.flush()
        
        # Test invalid rate (> 100%)
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 100"):
            rule_data = CommissionRuleCreate(
                agency_id=str(test_agency.id),
                tier=CommissionTier.CUSTOM,
                rate=Decimal("101.00")
            )
            await commission_calculator.create_commission_rule(
                rule_data=rule_data,
                created_by_id=creator.id
            )
        
        # Test invalid rate (< 0%)
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 100"):
            rule_data = CommissionRuleCreate(
                agency_id=str(test_agency.id),
                tier=CommissionTier.CUSTOM,
                rate=Decimal("-5.00")
            )
            await commission_calculator.create_commission_rule(
                rule_data=rule_data,
                created_by_id=creator.id
            )
    
    async def test_effective_date_rules(
        self,
        commission_calculator,
        test_agency,
        test_model
    ):
        """Test commission rules with effective dates."""
        # Create past rule
        past_rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.00"),
            effective_from=datetime.utcnow() - timedelta(days=60),
            effective_until=datetime.utcnow() - timedelta(days=30),
            is_active=True
        )
        commission_calculator.db.add(past_rule)
        
        # Create current rule
        current_rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_2,
            rate=Decimal("65.00"),
            effective_from=datetime.utcnow() - timedelta(days=15),
            is_active=True
        )
        commission_calculator.db.add(current_rule)
        
        # Create future rule
        future_rule = CommissionRule(
            agency_id=test_agency.id,
            tier=CommissionTier.TIER_3,
            rate=Decimal("60.00"),
            effective_from=datetime.utcnow() + timedelta(days=15),
            is_active=True
        )
        commission_calculator.db.add(future_rule)
        await commission_calculator.db.commit()
        
        # Calculate with current date (should use current rule)
        calculation = await commission_calculator.calculate_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id
        )
        assert calculation.tier == CommissionTier.TIER_2
        assert calculation.commission_rate == Decimal("35.00")
        
        # Calculate with past date (should use past rule)
        calculation = await commission_calculator.calculate_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id,
            calculation_date=datetime.utcnow() - timedelta(days=45)
        )
        assert calculation.tier == CommissionTier.TIER_1
        assert calculation.commission_rate == Decimal("30.00")
        
        # Calculate with future date (should use future rule)
        calculation = await commission_calculator.calculate_commission(
            gross_amount=Decimal("1000.00"),
            agency_id=test_agency.id,
            calculation_date=datetime.utcnow() + timedelta(days=30)
        )
        assert calculation.tier == CommissionTier.TIER_3
        assert calculation.commission_rate == Decimal("40.00")