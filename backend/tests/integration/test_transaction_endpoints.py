"""
Integration tests for transaction API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.models import User, UserRole, Agency, ModelProfile
from modules.financial.domain.models import FinancialTransaction, TransactionType
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_create_transaction(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test creating a new transaction."""
    # Create test agency
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create transaction
    response = client.post(
        "/api/v1/financial/transactions",
        json={
            "agency_id": str(agency.id),
            "type": "revenue",
            "amount": "150.00",
            "currency": "USD",
            "description": "Test revenue transaction"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "revenue"
    assert Decimal(data["amount"]) == Decimal("150.00")
    assert data["description"] == "Test revenue transaction"


@pytest.mark.asyncio
async def test_create_transaction_insufficient_permissions(
    client: TestClient,
    db_session: AsyncSession
):
    """Test that regular members cannot create transactions."""
    # Create user with limited permissions
    user = await create_test_user(
        db_session, 
        email="member@test.com",
        role=UserRole.MEMBER
    )
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create transaction
    response = client.post(
        "/api/v1/financial/transactions",
        json={
            "type": "revenue",
            "amount": "100.00"
        },
        headers=headers
    )
    
    assert response.status_code == 403
    assert "permissions" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_transactions_with_filters(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test listing transactions with various filters."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create multiple transactions
    transactions = []
    for i in range(5):
        transaction = FinancialTransaction(
            id=uuid4(),
            agency_id=agency.id,
            type=TransactionType.REVENUE if i % 2 == 0 else TransactionType.COMMISSION,
            amount=Decimal(f"{(i+1) * 100}.00"),
            currency="USD",
            description=f"Transaction {i+1}",
            transaction_date=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(transaction)
        transactions.append(transaction)
    
    await db_session.commit()
    
    # Test filter by type
    response = client.get(
        "/api/v1/financial/transactions?type=revenue",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # Should only return revenue transactions
    assert all(t["type"] == "revenue" for t in data)
    
    # Test filter by amount range
    response = client.get(
        "/api/v1/financial/transactions?amount_min=200&amount_max=400",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # Transactions with amounts 200, 300, 400
    
    # Test search
    response = client.get(
        "/api/v1/financial/transactions?search=Transaction%202",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "Transaction 2" in data[0]["description"]


@pytest.mark.asyncio
async def test_get_transaction_summary(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test getting transaction summary statistics."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create transactions of different types
    transactions_data = [
        (TransactionType.REVENUE, Decimal("1000.00")),
        (TransactionType.REVENUE, Decimal("2000.00")),
        (TransactionType.COMMISSION, Decimal("300.00")),
        (TransactionType.PAYOUT, Decimal("1500.00")),
        (TransactionType.REFUND, Decimal("200.00")),
    ]
    
    for trans_type, amount in transactions_data:
        transaction = FinancialTransaction(
            id=uuid4(),
            agency_id=agency.id,
            type=trans_type,
            amount=amount,
            currency="USD",
            transaction_date=datetime.utcnow()
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Get summary
    response = client.get(
        "/api/v1/financial/transactions/summary/stats",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify calculations
    assert data["total_count"] == 5
    assert Decimal(data["total_amount"]) == Decimal("5000.00")
    assert Decimal(data["net_revenue"]) == Decimal("2800.00")  # 3000 - 200
    assert Decimal(data["net_payout"]) == Decimal("1800.00")  # 1500 + 300
    assert Decimal(data["net_balance"]) == Decimal("1200.00")  # 3000 + 200 - 300 - 1500


@pytest.mark.asyncio
async def test_bulk_import_transactions(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test bulk importing transactions."""
    # Create test agency
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Prepare bulk data
    transactions_data = [
        {
            "agency_id": str(agency.id),
            "type": "revenue",
            "amount": "100.00",
            "description": f"Bulk transaction {i}"
        }
        for i in range(5)
    ]
    
    # Add one invalid transaction
    transactions_data.append({
        "type": "revenue",
        "amount": "-50.00",  # Invalid negative amount
        "description": "Invalid transaction"
    })
    
    # Bulk import
    response = client.post(
        "/api/v1/financial/transactions/bulk/import",
        json=transactions_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success_count"] == 5
    assert data["error_count"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 5


@pytest.mark.asyncio
async def test_update_transaction(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test updating transaction details."""
    # Create test transaction
    agency = await create_test_agency(db_session, "Test Agency")
    transaction = FinancialTransaction(
        id=uuid4(),
        agency_id=agency.id,
        type=TransactionType.REVENUE,
        amount=Decimal("100.00"),
        currency="USD",
        description="Original description",
        transaction_date=datetime.utcnow()
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Update transaction
    response = client.patch(
        f"/api/v1/financial/transactions/{transaction.id}",
        json={
            "description": "Updated description",
            "external_reference": "EXT-12345"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "Updated description" in data["description"]


@pytest.mark.asyncio
async def test_transaction_pagination(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test transaction list pagination."""
    # Create test agency
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create 15 transactions
    for i in range(15):
        transaction = FinancialTransaction(
            id=uuid4(),
            agency_id=agency.id,
            type=TransactionType.REVENUE,
            amount=Decimal(f"{(i+1) * 10}.00"),
            currency="USD",
            transaction_date=datetime.utcnow() - timedelta(hours=i)
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Get first page
    response = client.get(
        "/api/v1/financial/transactions?page=1&page_size=10",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    
    # Get second page
    response = client.get(
        "/api/v1/financial/transactions?page=2&page_size=10",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


@pytest.mark.asyncio
async def test_transaction_date_filtering(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test filtering transactions by date range."""
    # Create test agency
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create transactions across different dates
    dates = [
        datetime.utcnow() - timedelta(days=10),
        datetime.utcnow() - timedelta(days=5),
        datetime.utcnow() - timedelta(days=2),
        datetime.utcnow(),
    ]
    
    for i, date in enumerate(dates):
        transaction = FinancialTransaction(
            id=uuid4(),
            agency_id=agency.id,
            type=TransactionType.REVENUE,
            amount=Decimal("100.00"),
            currency="USD",
            transaction_date=date
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Filter last 7 days
    date_from = (datetime.utcnow() - timedelta(days=7)).isoformat()
    date_to = datetime.utcnow().isoformat()
    
    response = client.get(
        f"/api/v1/financial/transactions?date_from={date_from}&date_to={date_to}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # Should exclude the transaction from 10 days ago