"""
Unit tests for TransactionService.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from modules.financial.application.transaction_service import TransactionService
from models.financial import TransactionType
from modules.financial.domain.models import FinancialTransaction, BillingCycle
from modules.financial.domain.schemas import (
    TransactionCreate,
    TransactionFilter
)
from core.domain.models import User, UserRole, Agency, ModelProfile
from core.exceptions import ValidationError, NotFoundError, BusinessLogicError


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
        email="test@example.com",
        role=UserRole.AGENCY_ADMIN,
        full_name="Test User"
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
def transaction_service(mock_db):
    """Create a TransactionService instance."""
    return TransactionService(mock_db)


class TestTransactionService:
    """Test suite for TransactionService."""
    
    @pytest.mark.asyncio
    async def test_create_transaction_success(self, transaction_service, mock_user, mock_agency):
        """Test successful transaction creation."""
        # Arrange
        transaction_data = TransactionCreate(
            agency_id=str(mock_agency.id),
            type=TransactionType.REVENUE,
            amount=Decimal("100.00"),
            currency="USD",
            description="Test transaction"
        )
        
        # Mock agency lookup
        transaction_service.db.get = AsyncMock(return_value=mock_agency)
        transaction_service.db.add = MagicMock()
        transaction_service.db.commit = AsyncMock()
        transaction_service.db.refresh = AsyncMock()
        
        # Act
        result = await transaction_service.create_transaction(transaction_data, mock_user)
        
        # Assert
        assert transaction_service.db.add.called
        assert transaction_service.db.commit.called
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_transaction_negative_amount(self, transaction_service, mock_user):
        """Test that negative amounts are rejected."""
        # Arrange
        transaction_data = TransactionCreate(
            type=TransactionType.REVENUE,
            amount=Decimal("-100.00"),
            currency="USD"
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await transaction_service.create_transaction(transaction_data, mock_user)
        
        assert "positive" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_create_transaction_with_balance_tracking(self, transaction_service, mock_user, mock_agency):
        """Test transaction creation with balance tracking."""
        # Arrange
        transaction_data = TransactionCreate(
            agency_id=str(mock_agency.id),
            type=TransactionType.REVENUE,
            amount=Decimal("100.00"),
            track_balance=True
        )
        
        # Mock previous transaction with balance
        previous_transaction = FinancialTransaction(
            balance_after=Decimal("500.00")
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = previous_transaction
        
        transaction_service.db.get = AsyncMock(return_value=mock_agency)
        transaction_service.db.execute = AsyncMock(return_value=mock_result)
        transaction_service.db.add = MagicMock()
        transaction_service.db.commit = AsyncMock()
        transaction_service.db.refresh = AsyncMock()
        
        # Act
        result = await transaction_service.create_transaction(transaction_data, mock_user)
        
        # Assert
        # The service should calculate new balance: 500 + 100 = 600
        added_transaction = transaction_service.db.add.call_args[0][0]
        assert added_transaction.balance_before == Decimal("500.00")
        assert added_transaction.balance_after == Decimal("600.00")
    
    @pytest.mark.asyncio
    async def test_create_commission_transaction_without_model(self, transaction_service, mock_user):
        """Test that commission transactions require a model_id."""
        # Arrange
        transaction_data = TransactionCreate(
            type=TransactionType.COMMISSION,
            amount=Decimal("50.00")
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await transaction_service.create_transaction(transaction_data, mock_user)
        
        assert "model_id" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self, transaction_service, mock_user):
        """Test getting a non-existent transaction."""
        # Arrange
        transaction_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        transaction_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act & Assert
        with pytest.raises(NotFoundError):
            await transaction_service.get_transaction(transaction_id, mock_user)
    
    @pytest.mark.asyncio
    async def test_list_transactions_with_filters(self, transaction_service, mock_user):
        """Test listing transactions with various filters."""
        # Arrange
        filter_params = TransactionFilter(
            type=TransactionType.REVENUE,
            date_from=datetime.utcnow() - timedelta(days=7),
            date_to=datetime.utcnow(),
            amount_min=Decimal("100.00"),
            amount_max=Decimal("1000.00"),
            search="test"
        )
        
        # Mock transactions
        mock_transactions = [
            FinancialTransaction(
                id=uuid4(),
                type=TransactionType.REVENUE,
                amount=Decimal("500.00"),
                transaction_date=datetime.utcnow()
            )
        ]
        
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        
        # Mock transaction query
        transaction_result = MagicMock()
        transaction_result.scalars.return_value.all.return_value = mock_transactions
        
        # Set up execute to return different results for count and data queries
        transaction_service.db.execute = AsyncMock(
            side_effect=[count_result, transaction_result]
        )
        
        # Act
        transactions, total = await transaction_service.list_transactions(
            filter_params, mock_user, page=1, page_size=50
        )
        
        # Assert
        assert len(transactions) == 1
        assert total == 1
        assert transaction_service.db.execute.call_count == 2  # Count + data queries
    
    @pytest.mark.asyncio
    async def test_get_transaction_summary(self, transaction_service, mock_user):
        """Test getting transaction summary statistics."""
        # Arrange
        filter_params = TransactionFilter()
        
        # Mock summary data
        summary_data = [
            MagicMock(type=TransactionType.REVENUE, count=10, total=Decimal("5000.00")),
            MagicMock(type=TransactionType.COMMISSION, count=5, total=Decimal("1000.00")),
            MagicMock(type=TransactionType.PAYOUT, count=3, total=Decimal("2000.00"))
        ]
        
        mock_result = MagicMock()
        mock_result.all.return_value = summary_data
        transaction_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act
        summary = await transaction_service.get_transaction_summary(filter_params, mock_user)
        
        # Assert
        assert summary.total_count == 18  # 10 + 5 + 3
        assert summary.total_amount == Decimal("8000.00")  # 5000 + 1000 + 2000
        assert summary.net_revenue == Decimal("5000.00")  # Revenue - refunds
        assert summary.net_payout == Decimal("3000.00")  # Payouts + commissions
        assert summary.net_balance == Decimal("2000.00")  # Revenue - commissions - payouts
    
    @pytest.mark.asyncio
    async def test_validate_transaction_invalid_agency(self, transaction_service):
        """Test validation fails for non-existent agency."""
        # Arrange
        transaction_data = TransactionCreate(
            agency_id=str(uuid4()),
            type=TransactionType.REVENUE,
            amount=Decimal("100.00")
        )
        
        transaction_service.db.get = AsyncMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await transaction_service._validate_transaction_data(transaction_data)
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_model_agency_mismatch(self, transaction_service, mock_agency):
        """Test validation fails when model doesn't belong to agency."""
        # Arrange
        model = ModelProfile(
            id=uuid4(),
            agency_id=uuid4()  # Different agency
        )
        
        transaction_data = TransactionCreate(
            agency_id=str(mock_agency.id),
            model_id=str(model.id),
            type=TransactionType.REVENUE,
            amount=Decimal("100.00")
        )
        
        transaction_service.db.get = AsyncMock(
            side_effect=[mock_agency, model]
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await transaction_service._validate_transaction_data(transaction_data)
        
        assert "does not belong" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_update_transaction_status(self, transaction_service, mock_user):
        """Test updating transaction status with notes."""
        # Arrange
        transaction_id = uuid4()
        notes = "Payment processed successfully"
        
        mock_transaction = FinancialTransaction(
            id=transaction_id,
            description="Original description"
        )
        
        # Mock get_transaction
        with patch.object(
            transaction_service, 
            'get_transaction', 
            return_value=mock_transaction
        ):
            transaction_service.db.commit = AsyncMock()
            transaction_service.db.refresh = AsyncMock()
            
            # Act
            result = await transaction_service.update_transaction_status(
                transaction_id, "completed", mock_user, notes
            )
            
            # Assert
            assert notes in mock_transaction.description
            assert transaction_service.db.commit.called