"""
Integration tests for payout API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.domain.models import User, UserRole, Agency, ModelProfile
from modules.financial.domain.models import (
    Payout,
    PayoutStatus,
    PayoutSchedule,
    BillingCycle,
    CryptoWallet,
    CryptoNetwork
)
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_create_payout_schedule(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test creating automatic payout schedule."""
    # Create test user and wallet
    user = await create_test_user(
        db_session,
        email="scheduled@test.com",
        role=UserRole.MODEL
    )
    
    wallet = CryptoWallet(
        id=uuid4(),
        user_id=user.id,
        network=CryptoNetwork.ETHEREUM,
        address="0x1234567890abcdef",
        is_active=True,
        is_verified=True
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Create schedule
    response = client.post(
        "/api/v1/financial/payouts/schedules",
        json={
            "recipient_id": str(user.id),
            "recipient_type": "model",
            "frequency": "weekly",
            "minimum_amount": "100.00",
            "payment_method": "crypto",
            "payment_details": {
                "wallet_id": str(wallet.id)
            }
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["frequency"] == "weekly"
    assert Decimal(data["minimum_amount"]) == Decimal("100.00")
    assert data["is_active"] is True
    
    # Verify in database
    result = await db_session.execute(
        select(PayoutSchedule).where(PayoutSchedule.recipient_id == user.id)
    )
    schedule = result.scalar_one()
    assert schedule.is_active is True


@pytest.mark.asyncio
async def test_create_duplicate_schedule_error(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test error when creating duplicate active schedule."""
    # Create test user with existing schedule
    user = await create_test_user(
        db_session,
        email="duplicate@test.com",
        role=UserRole.MODEL
    )
    
    wallet = CryptoWallet(
        id=uuid4(),
        user_id=user.id,
        network=CryptoNetwork.ETHEREUM,
        address="0xabcdef1234567890",
        is_active=True
    )
    db_session.add(wallet)
    
    # Create existing schedule
    existing_schedule = PayoutSchedule(
        id=uuid4(),
        recipient_id=user.id,
        recipient_type="model",
        frequency="daily",
        minimum_amount=Decimal("50.00"),
        payment_method="crypto",
        payment_details={'wallet_id': str(wallet.id)},
        next_payout_date=datetime.utcnow() + timedelta(days=1),
        is_active=True
    )
    db_session.add(existing_schedule)
    await db_session.commit()
    
    # Try to create duplicate
    response = client.post(
        "/api/v1/financial/payouts/schedules",
        json={
            "recipient_id": str(user.id),
            "recipient_type": "model",
            "frequency": "weekly",
            "minimum_amount": "100.00",
            "payment_method": "crypto",
            "payment_details": {
                "wallet_id": str(wallet.id)
            }
        },
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_scheduled_payouts_batch(
    client: TestClient,
    db_session: AsyncSession
):
    """Test batch processing endpoint (super admin only)."""
    # Create super admin
    super_admin = await create_test_user(
        db_session,
        email="super@admin.com",
        role=UserRole.SUPER_ADMIN
    )
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "super@admin.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Process batch
    response = client.post(
        "/api/v1/financial/payouts/batch/process",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "batch_id" in data
    assert "total_schedules" in data
    assert "payouts_created" in data
    assert "duration_seconds" in data


@pytest.mark.asyncio
async def test_batch_processing_permission_denied(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test batch processing requires super admin permission."""
    # Try with regular admin
    response = client.post(
        "/api/v1/financial/payouts/batch/process",
        headers=auth_headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_retry_failed_payouts(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test retrying failed payouts."""
    # Create failed payouts
    agency = await create_test_agency(db_session, "Test Agency")
    cycle = BillingCycle(
        id=uuid4(),
        agency_id=agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=True
    )
    db_session.add(cycle)
    
    for i in range(3):
        payout = Payout(
            id=uuid4(),
            billing_cycle_id=cycle.id,
            recipient_id=uuid4(),
            recipient_type="model",
            amount=Decimal("100.00"),
            status=PayoutStatus.FAILED,
            payment_method="crypto",
            payment_details={},
            retry_count=i,
            processed_at=datetime.utcnow() - timedelta(hours=3),
            failure_reason="Network error"
        )
        db_session.add(payout)
    
    await db_session.commit()
    
    # Retry failed payouts
    response = client.post(
        "/api/v1/financial/payouts/retry-failed?max_age_hours=24",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_failed"] >= 3
    assert "retried" in data
    assert "succeeded" in data


@pytest.mark.asyncio
async def test_approve_payout(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test payout approval workflow."""
    # Create pending payout
    agency = await create_test_agency(db_session, "Test Agency")
    cycle = BillingCycle(
        id=uuid4(),
        agency_id=agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=True
    )
    db_session.add(cycle)
    
    payout = Payout(
        id=uuid4(),
        billing_cycle_id=cycle.id,
        recipient_id=uuid4(),
        recipient_type="model",
        amount=Decimal("1000.00"),
        status=PayoutStatus.PENDING,
        payment_method="crypto",
        payment_details={},
        scheduled_at=datetime.utcnow() + timedelta(days=1)
    )
    db_session.add(payout)
    await db_session.commit()
    
    # Approve payout
    response = client.post(
        f"/api/v1/financial/payouts/{payout.id}/approve",
        json={
            "approved": True,
            "notes": "Verified and approved for processing",
            "process_immediately": True
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(payout.id)
    
    # Verify metadata was added
    await db_session.refresh(payout)
    assert payout.metadata["approval"]["approved"] is True
    assert "notes" in payout.metadata["approval"]


@pytest.mark.asyncio
async def test_reject_payout(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test payout rejection."""
    # Create pending payout
    agency = await create_test_agency(db_session, "Test Agency")
    cycle = BillingCycle(
        id=uuid4(),
        agency_id=agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=True
    )
    db_session.add(cycle)
    
    payout = Payout(
        id=uuid4(),
        billing_cycle_id=cycle.id,
        recipient_id=uuid4(),
        recipient_type="model",
        amount=Decimal("5000.00"),
        status=PayoutStatus.PENDING,
        payment_method="crypto",
        payment_details={}
    )
    db_session.add(payout)
    await db_session.commit()
    
    # Reject payout
    response = client.post(
        f"/api/v1/financial/payouts/{payout.id}/approve",
        json={
            "approved": False,
            "notes": "Amount exceeds expected range, requires investigation",
            "process_immediately": False
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    
    # Verify status changed
    await db_session.refresh(payout)
    assert payout.status == PayoutStatus.CANCELLED
    assert "Rejected by" in payout.failure_reason


@pytest.mark.asyncio
async def test_get_payout_schedules(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test getting payout schedules with filters."""
    # Create test schedules
    user1 = await create_test_user(db_session, "user1@test.com")
    user2 = await create_test_user(db_session, "user2@test.com")
    
    schedules = [
        PayoutSchedule(
            id=uuid4(),
            recipient_id=user1.id,
            recipient_type="model",
            frequency="weekly",
            minimum_amount=Decimal("100.00"),
            payment_method="crypto",
            payment_details={},
            next_payout_date=datetime.utcnow() + timedelta(days=7),
            is_active=True
        ),
        PayoutSchedule(
            id=uuid4(),
            recipient_id=user2.id,
            recipient_type="model",
            frequency="monthly",
            minimum_amount=Decimal("500.00"),
            payment_method="crypto",
            payment_details={},
            next_payout_date=datetime.utcnow() + timedelta(days=30),
            is_active=True
        ),
        PayoutSchedule(
            id=uuid4(),
            recipient_id=user1.id,
            recipient_type="model",
            frequency="daily",
            minimum_amount=Decimal("50.00"),
            payment_method="crypto",
            payment_details={},
            next_payout_date=datetime.utcnow() + timedelta(days=1),
            is_active=False,
            paused_at=datetime.utcnow() - timedelta(days=5),
            paused_reason="Temporary suspension"
        )
    ]
    
    for schedule in schedules:
        db_session.add(schedule)
    await db_session.commit()
    
    # Get all active schedules
    response = client.get(
        "/api/v1/financial/payouts/schedules?is_active=true",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(s["is_active"] for s in data)
    
    # Get schedules for specific recipient
    response = client.get(
        f"/api/v1/financial/payouts/schedules?recipient_id={user1.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Active and inactive for user1


@pytest.mark.asyncio
async def test_pause_payout_schedule(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test pausing an active payout schedule."""
    # Create active schedule
    user = await create_test_user(db_session, "pausetest@test.com")
    schedule = PayoutSchedule(
        id=uuid4(),
        recipient_id=user.id,
        recipient_type="model",
        frequency="weekly",
        minimum_amount=Decimal("100.00"),
        payment_method="crypto",
        payment_details={},
        next_payout_date=datetime.utcnow() + timedelta(days=7),
        is_active=True
    )
    db_session.add(schedule)
    await db_session.commit()
    
    # Pause schedule
    response = client.put(
        f"/api/v1/financial/payouts/schedules/{schedule.id}/pause",
        params={"reason": "Account under review for compliance"},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paused"
    
    # Verify in database
    await db_session.refresh(schedule)
    assert schedule.is_active is False
    assert schedule.paused_at is not None
    assert schedule.paused_reason == "Account under review for compliance"


@pytest.mark.asyncio
async def test_model_can_only_see_own_schedules(
    client: TestClient,
    db_session: AsyncSession
):
    """Test that models can only see their own payout schedules."""
    # Create model user
    model_user = await create_test_user(
        db_session,
        email="model@test.com",
        role=UserRole.MODEL
    )
    
    other_user = await create_test_user(
        db_session,
        email="other@test.com",
        role=UserRole.MODEL
    )
    
    # Create schedules for both users
    model_schedule = PayoutSchedule(
        id=uuid4(),
        recipient_id=model_user.id,
        recipient_type="model",
        frequency="weekly",
        minimum_amount=Decimal("100.00"),
        payment_method="crypto",
        payment_details={},
        next_payout_date=datetime.utcnow() + timedelta(days=7),
        is_active=True
    )
    
    other_schedule = PayoutSchedule(
        id=uuid4(),
        recipient_id=other_user.id,
        recipient_type="model",
        frequency="daily",
        minimum_amount=Decimal("50.00"),
        payment_method="crypto",
        payment_details={},
        next_payout_date=datetime.utcnow() + timedelta(days=1),
        is_active=True
    )
    
    db_session.add(model_schedule)
    db_session.add(other_schedule)
    await db_session.commit()
    
    # Get auth token for model
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "model@test.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get schedules
    response = client.get(
        "/api/v1/financial/payouts/schedules",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # Only own schedule
    assert data[0]["recipient_id"] == str(model_user.id)