"""
Integration tests for analytics sync API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.domain.models import User, UserRole, ModelProfile
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionType,
    TransactionStatus
)
from modules.analytics.domain.models import (
    RevenueTransaction,
    MetricSnapshot
)
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_sync_analytics_data_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test the full analytics sync endpoint."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        user_id=uuid4(),
        agency_id=agency.id,
        username="testmodel",
        is_active=True
    )
    db_session.add(model)
    
    # Create financial transactions
    for i in range(5):
        tx = FinancialTransaction(
            id=uuid4(),
            model_id=model.id,
            amount=Decimal("100.00"),
            currency="USD",
            type=TransactionType.REVENUE,
            status=TransactionStatus.COMPLETED,
            transaction_date=datetime.utcnow() - timedelta(days=i),
            description="Test transaction",
            metadata={"type": "subscription"}
        )
        db_session.add(tx)
    
    await db_session.commit()
    
    # Call sync endpoint
    response = client.post(
        f"/api/v1/analytics/sync/{model.id}",
        params={"force": True, "lookback_days": 7},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["model_id"] == str(model.id)
    
    # Verify revenue transactions were created
    result = await db_session.execute(
        select(RevenueTransaction).where(
            RevenueTransaction.model_id == str(model.id)
        )
    )
    revenue_txs = result.scalars().all()
    assert len(revenue_txs) == 5
    
    # Verify metric snapshots were created
    result = await db_session.execute(
        select(MetricSnapshot).where(
            MetricSnapshot.model_id == str(model.id)
        )
    )
    snapshots = result.scalars().all()
    assert len(snapshots) > 0


@pytest.mark.asyncio
async def test_sync_revenue_data_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test the revenue-only sync endpoint."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        user_id=uuid4(),
        agency_id=agency.id,
        username="testmodel",
        is_active=True
    )
    db_session.add(model)
    
    # Create transactions
    cutoff = datetime.utcnow() - timedelta(days=2)
    
    # Old transaction
    old_tx = FinancialTransaction(
        id=uuid4(),
        model_id=model.id,
        amount=Decimal("50.00"),
        type=TransactionType.REVENUE,
        status=TransactionStatus.COMPLETED,
        transaction_date=cutoff - timedelta(days=1)
    )
    db_session.add(old_tx)
    
    # New transaction
    new_tx = FinancialTransaction(
        id=uuid4(),
        model_id=model.id,
        amount=Decimal("75.00"),
        type=TransactionType.REVENUE,
        status=TransactionStatus.COMPLETED,
        transaction_date=cutoff + timedelta(days=1)
    )
    db_session.add(new_tx)
    
    await db_session.commit()
    
    # Call sync endpoint with start date
    response = client.post(
        f"/api/v1/analytics/sync/{model.id}/revenue",
        params={
            "start_date": cutoff.isoformat(),
            "force": True
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Verify only new transaction was synced
    result = await db_session.execute(
        select(RevenueTransaction).where(
            RevenueTransaction.model_id == str(model.id)
        )
    )
    revenue_txs = result.scalars().all()
    assert len(revenue_txs) == 1
    assert revenue_txs[0].amount == Decimal("75.00")


@pytest.mark.asyncio
async def test_sync_permission_denied(
    client: TestClient,
    db_session: AsyncSession
):
    """Test that unauthorized users cannot sync analytics."""
    # Create a fan user (no analytics access)
    fan = await create_test_user(
        db_session,
        email="fan@test.com",
        role=UserRole.FAN
    )
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "fan@test.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to sync
    response = client.post(
        f"/api/v1/analytics/sync/{uuid4()}",
        headers=headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_model_not_found(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test sync with non-existent model."""
    fake_id = str(uuid4())
    
    response = client.post(
        f"/api/v1/analytics/sync/{fake_id}",
        headers=auth_headers
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_model_not_in_agency(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test that users can only sync models in their agency."""
    # Create another agency and model
    other_agency = await create_test_agency(
        db_session,
        name="Other Agency",
        domain="other.agency.com"
    )
    
    other_model = ModelProfile(
        id=uuid4(),
        user_id=uuid4(),
        agency_id=other_agency.id,
        username="othermodel",
        is_active=True
    )
    db_session.add(other_model)
    await db_session.commit()
    
    # Try to sync model from different agency
    response = client.post(
        f"/api/v1/analytics/sync/{other_model.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 403
    assert "not in your agency" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_with_model_user(
    client: TestClient,
    db_session: AsyncSession
):
    """Test that models can sync their own analytics."""
    # Create model user
    agency = await create_test_agency(db_session)
    model_user = await create_test_user(
        db_session,
        email="model@test.com",
        role=UserRole.MODEL,
        agency_id=agency.id
    )
    
    # Create model profile
    model_profile = ModelProfile(
        id=uuid4(),
        user_id=model_user.id,
        agency_id=agency.id,
        username="modeluser",
        is_active=True
    )
    db_session.add(model_profile)
    
    # Create transaction
    tx = FinancialTransaction(
        id=uuid4(),
        model_id=model_profile.id,
        amount=Decimal("200.00"),
        type=TransactionType.REVENUE,
        status=TransactionStatus.COMPLETED,
        transaction_date=datetime.utcnow()
    )
    db_session.add(tx)
    await db_session.commit()
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "model@test.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Sync own analytics
    response = client.post(
        f"/api/v1/analytics/sync/{model_profile.id}",
        headers=headers
    )
    
    assert response.status_code == 200
    
    # Try to sync another model (should fail)
    other_model = ModelProfile(
        id=uuid4(),
        user_id=uuid4(),
        agency_id=agency.id,
        username="othermodel"
    )
    db_session.add(other_model)
    await db_session.commit()
    
    response = client.post(
        f"/api/v1/analytics/sync/{other_model.id}",
        headers=headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_error_handling(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test error handling in sync endpoint."""
    # Create model with invalid data that will cause sync to fail
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        user_id=uuid4(),
        agency_id=agency.id,
        username="testmodel",
        is_active=True
    )
    db_session.add(model)
    
    # Create transaction with invalid metadata
    tx = FinancialTransaction(
        id=uuid4(),
        model_id=model.id,
        amount=Decimal("-100.00"),  # Negative amount
        type=TransactionType.REVENUE,
        status=TransactionStatus.COMPLETED,
        transaction_date=datetime.utcnow()
    )
    db_session.add(tx)
    await db_session.commit()
    
    # Mock the sync service to raise an error
    from unittest.mock import patch, AsyncMock
    
    with patch('modules.analytics.application.data_sync_service.AnalyticsDataSyncService.sync_all_model_data') as mock_sync:
        mock_sync.side_effect = Exception("Test sync error")
        
        response = client.post(
            f"/api/v1/analytics/sync/{model.id}",
            headers=auth_headers
        )
    
    assert response.status_code == 500
    assert "Failed to sync analytics data" in response.json()["detail"]