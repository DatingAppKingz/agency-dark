"""
Integration tests for Inflow sync API endpoints.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.domain.models import User, UserRole, ModelProfile, Agency
from modules.financial.domain.models import FinancialTransaction
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_sync_all_data_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test the full Inflow sync endpoint."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        onlyfans_user_id="of_123",
        inflow_api_key="test_api_key",
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Mock the sync service
    with patch('modules.inflow_wrapper.api.InflowSyncService') as MockSyncService:
        mock_instance = MockSyncService.return_value
        mock_instance.sync_all_data = AsyncMock(return_value={
            'subscribers': 10,
            'content': 5,
            'transactions': 20,
            'messages': 15
        })
        
        # Call sync endpoint
        response = client.post(
            f"/api/v1/inflow/models/{model.id}/sync/all",
            params={"force": True},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_id"] == str(model.id)
        assert data["sync_results"]["subscribers"] == 10
        assert data["sync_results"]["transactions"] == 20


@pytest.mark.asyncio
async def test_sync_transactions_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test the transaction-only sync endpoint."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key="test_api_key",
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Mock the sync service
    with patch('modules.inflow_wrapper.api.InflowSyncService') as MockSyncService:
        mock_instance = MockSyncService.return_value
        mock_instance.sync_transactions = AsyncMock(return_value=15)
        
        # Call sync endpoint
        today = date.today()
        start_date = today - timedelta(days=7)
        
        response = client.post(
            f"/api/v1/inflow/models/{model.id}/sync/transactions",
            params={
                "start_date": start_date.isoformat(),
                "end_date": today.isoformat()
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["synced_count"] == 15
        assert data["period"]["start"] == start_date.isoformat()


@pytest.mark.asyncio
async def test_sync_status_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test the sync status endpoint."""
    # Create test model with recent sync
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key="test_api_key",
        last_sync_at=datetime.utcnow() - timedelta(minutes=30),
        subscriber_count=150,
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Get sync status
    response = client.get(
        f"/api/v1/inflow/models/{model.id}/sync/status",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["model_id"] == str(model.id)
    assert data["has_api_key"] is True
    assert data["is_fresh"] is True  # Synced 30 minutes ago
    assert data["subscriber_count"] == 150
    assert 1700 < data["sync_age_seconds"] < 1900  # Around 30 minutes


@pytest.mark.asyncio
async def test_sync_rate_limiting(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test rate limiting on sync endpoint."""
    # Create test model with very recent sync
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key="test_api_key",
        last_sync_at=datetime.utcnow() - timedelta(seconds=30),  # 30 seconds ago
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Try to sync without force flag
    response = client.post(
        f"/api/v1/inflow/models/{model.id}/sync/all",
        params={"force": False},
        headers=auth_headers
    )
    
    assert response.status_code == 429
    assert "was synced" in response.json()["detail"]
    assert "Wait 5 minutes" in response.json()["detail"]
    
    # Should work with force flag
    with patch('modules.inflow_wrapper.api.InflowSyncService') as MockSyncService:
        mock_instance = MockSyncService.return_value
        mock_instance.sync_all_data = AsyncMock(return_value={})
        
        response = client.post(
            f"/api/v1/inflow/models/{model.id}/sync/all",
            params={"force": True},
            headers=auth_headers
        )
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_sync_without_api_key(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test sync fails without API key."""
    # Create test model without API key
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key=None,  # No API key
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Try to sync
    response = client.post(
        f"/api/v1/inflow/models/{model.id}/sync/all",
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "API key not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sync_permission_denied(
    client: TestClient,
    db_session: AsyncSession
):
    """Test that only authorized roles can sync."""
    # Create a fan user (no sync permission)
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
        f"/api/v1/inflow/models/{uuid4()}/sync/all",
        headers=headers
    )
    
    assert response.status_code == 403
    assert "Not authorized to sync data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sync_model_not_in_agency(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test users can only sync models in their agency."""
    # Create another agency and model
    other_agency = await create_test_agency(
        db_session,
        name="Other Agency",
        domain="other.agency.com"
    )
    
    other_model = ModelProfile(
        id=uuid4(),
        agency_id=other_agency.id,
        onlyfans_username="othermodel",
        inflow_api_key="test_key",
        is_active=True
    )
    db_session.add(other_model)
    await db_session.commit()
    
    # Try to sync model from different agency
    response = client.post(
        f"/api/v1/inflow/models/{other_model.id}/sync/all",
        headers=auth_headers
    )
    
    assert response.status_code == 403
    assert "Not authorized to access models from other agencies" in response.json()["detail"]


@pytest.mark.asyncio
async def test_send_message_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test sending message through Inflow."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key="test_api_key",
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Mock the Inflow service
    with patch('modules.inflow_wrapper.api.InflowService') as MockInflowService:
        mock_instance = MockInflowService.return_value
        mock_message = MagicMock()
        mock_message.id = "msg_123"
        mock_message.created_at = datetime.utcnow()
        mock_instance.send_message = AsyncMock(return_value=mock_message)
        
        # Send message
        fan_id = str(uuid4())
        response = client.post(
            f"/api/v1/inflow/models/{model.id}/messages",
            params={
                "fan_id": fan_id,
                "content": "Hello! Check out my new content!",
                "price": 10.0
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message_id"] == "msg_123"


@pytest.mark.asyncio
async def test_get_analytics_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test getting analytics from Inflow."""
    # Create test model
    agency = await create_test_agency(db_session)
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        onlyfans_username="testmodel",
        inflow_api_key="test_api_key",
        is_active=True
    )
    db_session.add(model)
    await db_session.commit()
    
    # Mock the Inflow service
    with patch('modules.inflow_wrapper.api.InflowService') as MockInflowService:
        mock_instance = MockInflowService.return_value
        mock_analytics = MagicMock()
        mock_analytics.total_revenue = 5000.0
        mock_analytics.total_subscribers = 150
        mock_analytics.new_subscribers = 20
        mock_analytics.lost_subscribers = 5
        mock_instance.get_analytics = AsyncMock(return_value=mock_analytics)
        
        # Get analytics
        today = date.today()
        start_date = today - timedelta(days=30)
        
        response = client.get(
            f"/api/v1/inflow/models/{model.id}/analytics",
            params={
                "start_date": start_date.isoformat(),
                "end_date": today.isoformat()
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        # Response should be the analytics object