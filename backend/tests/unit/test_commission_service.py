"""
Unit tests for enhanced CommissionService.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from modules.financial.application.commission_service import CommissionService
from modules.financial.domain.models import (
    CommissionRule,
    CommissionTier,
    FinancialTransaction,
    TransactionType,
    BillingCycle
)
from modules.financial.domain.schemas import (
    CommissionRuleCreate,
    CommissionAdjustmentCreate,
    CommissionReportFilter
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
def mock_agency():
    """Create a mock agency."""
    return Agency(
        id=uuid4(),
        name="Test Agency",
        slug="test-agency"
    )


@pytest.fixture
def mock_model():
    """Create a mock model profile."""
    return ModelProfile(
        id=uuid4(),
        agency_id=uuid4(),
        user_id=uuid4(),
        display_name="Test Model",
        platform_username="testmodel"
    )


@pytest.fixture
def commission_service(mock_db):
    """Create a CommissionService instance."""
    return CommissionService(mock_db)


class TestCommissionService:
    """Test suite for enhanced CommissionService."""
    
    @pytest.mark.asyncio
    async def test_calculate_tiered_commission_tier1(self, commission_service, mock_model):
        """Test tiered commission calculation for tier 1."""
        # Arrange
        model_id = str(mock_model.id)
        gross_amount = Decimal("1000.00")
        total_revenue = Decimal("5000.00")  # Below tier 2 threshold
        
        # Mock model lookup
        commission_service.db.get = AsyncMock(return_value=mock_model)
        
        # Mock no custom rule
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        commission_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act
        with patch.object(commission_service, 'calculate_commission') as mock_calc:
            mock_calc.return_value = MagicMock(
                gross_amount=gross_amount,
                commission_rate=Decimal("70.0"),
                commission_amount=Decimal("700.00"),
                net_amount=Decimal("300.00"),
                tier=CommissionTier.TIER_1,
                is_override=False,
                calculation_date=datetime.utcnow()
            )
            
            result = await commission_service.calculate_tiered_commission(
                gross_amount, model_id, total_revenue
            )
        
        # Assert
        assert result.commission_rate == Decimal("70.0")
        assert result.tier == CommissionTier.TIER_1
    
    @pytest.mark.asyncio
    async def test_calculate_tiered_commission_tier2(self, commission_service, mock_model):
        """Test automatic tier upgrade to tier 2."""
        # Arrange
        model_id = str(mock_model.id)
        gross_amount = Decimal("2000.00")
        total_revenue = Decimal("15000.00")  # Above tier 2 threshold
        
        # Mock model lookup
        commission_service.db.get = AsyncMock(return_value=mock_model)
        
        # Mock existing tier 1 rule that needs upgrade
        existing_rule = CommissionRule(
            tier=CommissionTier.TIER_1,
            rate=Decimal("70.0"),
            is_override=False
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_rule
        commission_service.db.execute = AsyncMock(return_value=mock_result)
        commission_service.db.add = MagicMock()
        commission_service.db.commit = AsyncMock()
        
        # Act
        with patch.object(commission_service, 'calculate_commission') as mock_calc:
            mock_calc.return_value = MagicMock(
                gross_amount=gross_amount,
                commission_rate=Decimal("65.0"),
                commission_amount=Decimal("1300.00"),
                net_amount=Decimal("700.00"),
                tier=CommissionTier.TIER_2,
                is_override=False,
                calculation_date=datetime.utcnow()
            )
            
            result = await commission_service.calculate_tiered_commission(
                gross_amount, model_id, total_revenue
            )
        
        # Assert
        assert existing_rule.tier == CommissionTier.TIER_2
        assert existing_rule.rate == Decimal("65.0")
        assert commission_service.db.add.called
        assert commission_service.db.commit.called
    
    @pytest.mark.asyncio
    async def test_bulk_calculate_commission(self, commission_service, mock_model):
        """Test bulk commission calculation for billing cycle."""
        # Arrange
        billing_cycle_id = str(uuid4())
        
        # Mock transactions
        transactions = [
            FinancialTransaction(
                id=uuid4(),
                model_id=mock_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("1000.00"),
                transaction_date=datetime.utcnow()
            ),
            FinancialTransaction(
                id=uuid4(),
                model_id=mock_model.id,
                type=TransactionType.REVENUE,
                amount=Decimal("2000.00"),
                transaction_date=datetime.utcnow()
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = transactions
        commission_service.db.execute = AsyncMock(return_value=mock_result)
        commission_service.db.add = MagicMock()
        commission_service.db.commit = AsyncMock()
        
        # Mock calculate_tiered_commission
        with patch.object(commission_service, 'calculate_tiered_commission') as mock_calc:
            mock_calc.side_effect = [
                MagicMock(
                    commission_rate=Decimal("70.0"),
                    commission_amount=Decimal("700.00")
                ),
                MagicMock(
                    commission_rate=Decimal("70.0"),
                    commission_amount=Decimal("1400.00")
                )
            ]
            
            # Act
            results = await commission_service.bulk_calculate_commission(billing_cycle_id)
        
        # Assert
        assert len(results) == 2
        assert transactions[0].commission_rate == Decimal("70.0")
        assert transactions[0].commission_amount == Decimal("700.00")
        assert transactions[1].commission_rate == Decimal("70.0")
        assert transactions[1].commission_amount == Decimal("1400.00")
        assert commission_service.db.commit.called
    
    @pytest.mark.asyncio
    async def test_create_commission_adjustment(self, commission_service, mock_user):
        """Test creating commission adjustment."""
        # Arrange
        adjustment_data = CommissionAdjustmentCreate(
            agency_id=str(uuid4()),
            model_id=str(uuid4()),
            amount=Decimal("-100.00"),  # Debit adjustment
            reason="Correction for overpayment in previous cycle",
            billing_cycle_id=str(uuid4())
        )
        
        mock_user.role = UserRole.AGENCY_ADMIN
        commission_service.db.add = MagicMock()
        commission_service.db.commit = AsyncMock()
        commission_service.db.refresh = AsyncMock()
        
        # Act
        result = await commission_service.create_commission_adjustment(
            adjustment_data,
            mock_user
        )
        
        # Assert
        added_tx = commission_service.db.add.call_args[0][0]
        assert added_tx.type == TransactionType.ADJUSTMENT
        assert added_tx.amount == Decimal("-100.00")
        assert "Commission adjustment" in added_tx.description
        assert added_tx.metadata["adjustment_type"] == "commission"
        assert commission_service.db.commit.called
    
    @pytest.mark.asyncio
    async def test_create_adjustment_insufficient_permissions(self, commission_service, mock_user):
        """Test adjustment creation with insufficient permissions."""
        # Arrange
        adjustment_data = CommissionAdjustmentCreate(
            agency_id=str(uuid4()),
            model_id=str(uuid4()),
            amount=Decimal("100.00"),
            reason="Test adjustment"
        )
        
        mock_user.role = UserRole.MODEL  # Insufficient permissions
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await commission_service.create_commission_adjustment(
                adjustment_data,
                mock_user
            )
        
        assert "Insufficient permissions" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_commission_report(self, commission_service, mock_user, mock_model):
        """Test commission report generation."""
        # Arrange
        filter_params = CommissionReportFilter(
            agency_id=str(uuid4()),
            date_from=datetime.utcnow() - timedelta(days=30),
            date_to=datetime.utcnow()
        )
        
        # Mock transaction summary
        summary_data = [
            MagicMock(
                model_id=mock_model.id,
                gross_revenue=Decimal("10000.00"),
                total_commission=Decimal("7000.00"),
                transaction_count=10,
                avg_commission_rate=Decimal("70.0")
            )
        ]
        
        mock_result = MagicMock()
        mock_result.all.return_value = summary_data
        
        # Mock tier distribution
        tier_data = [
            (CommissionTier.TIER_1, 5),
            (CommissionTier.TIER_2, 3)
        ]
        
        tier_result = MagicMock()
        tier_result.all.return_value = tier_data
        
        commission_service.db.execute = AsyncMock(side_effect=[mock_result, tier_result])
        commission_service.db.get = AsyncMock(return_value=mock_model)
        
        # Act
        report = await commission_service.generate_commission_report(
            filter_params,
            mock_user
        )
        
        # Assert
        assert report.total_gross_revenue == Decimal("10000.00")
        assert report.total_commission == Decimal("7000.00")
        assert report.total_net_revenue == Decimal("3000.00")
        assert len(report.model_breakdowns) == 1
        assert report.model_breakdowns[0]['model_name'] == mock_model.display_name
        assert report.tier_distribution['tier_1'] == 5
        assert report.tier_distribution['tier_2'] == 3
        assert report.generated_by == mock_user.username
    
    @pytest.mark.asyncio
    async def test_process_billing_cycle_commission(self, commission_service):
        """Test processing commission for entire billing cycle."""
        # Arrange
        billing_cycle_id = str(uuid4())
        cycle = BillingCycle(
            id=uuid4(),
            agency_id=uuid4(),
            is_closed=False
        )
        
        commission_service.db.get = AsyncMock(return_value=cycle)
        
        # Mock revenue transactions
        transactions = [
            FinancialTransaction(
                model_id=uuid4(),
                type=TransactionType.REVENUE,
                amount=Decimal("1000.00"),
                transaction_date=datetime.utcnow()
            ),
            FinancialTransaction(
                model_id=uuid4(),
                type=TransactionType.REVENUE,
                amount=Decimal("500.00"),
                transaction_date=datetime.utcnow()
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = transactions
        commission_service.db.execute = AsyncMock(return_value=mock_result)
        commission_service.db.add = MagicMock()
        commission_service.db.commit = AsyncMock()
        
        # Mock calculate_commission
        with patch.object(commission_service, 'calculate_commission') as mock_calc:
            mock_calc.side_effect = [
                MagicMock(
                    gross_amount=Decimal("1000.00"),
                    commission_amount=Decimal("700.00"),
                    net_amount=Decimal("300.00")
                ),
                MagicMock(
                    gross_amount=Decimal("500.00"),
                    commission_amount=Decimal("350.00"),
                    net_amount=Decimal("150.00")
                )
            ]
            
            # Act
            result = await commission_service.process_billing_cycle_commission(
                billing_cycle_id
            )
        
        # Assert
        assert result['total_gross'] == Decimal("1500.00")
        assert result['total_commission'] == Decimal("1050.00")
        assert result['total_net'] == Decimal("450.00")
        assert len(result['models']) == 2
        assert cycle.gross_revenue == Decimal("1500.00")
        assert cycle.total_commission == Decimal("1050.00")
        assert cycle.net_revenue == Decimal("450.00")
        assert commission_service.db.commit.called
    
    @pytest.mark.asyncio
    async def test_process_closed_billing_cycle_error(self, commission_service):
        """Test error when processing closed billing cycle."""
        # Arrange
        billing_cycle_id = str(uuid4())
        cycle = BillingCycle(
            id=uuid4(),
            is_closed=True  # Already closed
        )
        
        commission_service.db.get = AsyncMock(return_value=cycle)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await commission_service.process_billing_cycle_commission(billing_cycle_id)
        
        assert "already closed" in str(exc_info.value)