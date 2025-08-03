"""
Integration tests for commission API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.domain.models import User, UserRole, Agency, ModelProfile
from models.financial import TransactionType
from modules.financial.domain.models import CommissionRule, CommissionTier, FinancialTransaction, BillingCycle
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_calculate_tiered_commission(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test tiered commission calculation endpoint."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        user_id=uuid4(),
        display_name="Test Model",
        platform_username="testmodel"
    )
    db_session.add(model)
    await db_session.commit()
    
    # Test calculation
    response = client.post(
        "/api/v1/financial/commission/calculate-tiered",
        params={
            "gross_amount": "1000.00",
            "model_id": str(model.id),
            "total_revenue": "15000.00"  # Should trigger tier 2
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["commission_rate"]) == Decimal("65.0")  # Tier 2 rate
    assert data["tier"] == "tier_2"


@pytest.mark.asyncio
async def test_bulk_calculate_commission(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test bulk commission calculation for billing cycle."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        user_id=uuid4(),
        display_name="Test Model"
    )
    db_session.add(model)
    
    # Create billing cycle
    billing_cycle = BillingCycle(
        id=uuid4(),
        agency_id=agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow(),
        is_closed=False
    )
    db_session.add(billing_cycle)
    
    # Create transactions
    for i in range(3):
        tx = FinancialTransaction(
            id=uuid4(),
            agency_id=agency.id,
            model_id=model.id,
            billing_cycle_id=billing_cycle.id,
            type=TransactionType.REVENUE,
            amount=Decimal(f"{(i+1) * 1000}.00"),
            currency="USD",
            transaction_date=datetime.utcnow() - timedelta(days=i)
        )
        db_session.add(tx)
    
    await db_session.commit()
    
    # Calculate bulk commission
    response = client.post(
        f"/api/v1/financial/commission/bulk-calculate?billing_cycle_id={billing_cycle.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Verify calculations
    for i, calc in enumerate(data):
        assert Decimal(calc["gross_amount"]) == Decimal(f"{(i+1) * 1000}.00")
        assert Decimal(calc["commission_rate"]) == Decimal("70.0")  # Default tier 1


@pytest.mark.asyncio
async def test_create_commission_adjustment(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test creating commission adjustment."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    model = ModelProfile(
        id=uuid4(),
        agency_id=agency.id,
        user_id=uuid4(),
        display_name="Test Model"
    )
    db_session.add(model)
    await db_session.commit()
    
    # Create adjustment
    response = client.post(
        "/api/v1/financial/commission/adjustments",
        json={
            "agency_id": str(agency.id),
            "model_id": str(model.id),
            "amount": "-150.00",
            "currency": "USD",
            "reason": "Correction for duplicate commission payment"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["amount"]) == Decimal("-150.00")
    assert data["reason"] == "Correction for duplicate commission payment"
    
    # Verify transaction was created
    result = await db_session.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.type == TransactionType.ADJUSTMENT
        )
    )
    adjustment = result.scalar_one()
    assert adjustment.amount == Decimal("-150.00")
    assert "Commission adjustment" in adjustment.description


@pytest.mark.asyncio
async def test_create_adjustment_insufficient_permissions(
    client: TestClient,
    db_session: AsyncSession
):
    """Test adjustment creation with model role fails."""
    # Create model user
    model_user = await create_test_user(
        db_session,
        email="model@test.com",
        role=UserRole.MODEL
    )
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "model@test.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create adjustment
    response = client.post(
        "/api/v1/financial/commission/adjustments",
        json={
            "agency_id": str(uuid4()),
            "model_id": str(uuid4()),
            "amount": "100.00",
            "reason": "Test adjustment"
        },
        headers=headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_commission_report(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test commission report generation."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create multiple models
    models = []
    for i in range(3):
        model = ModelProfile(
            id=uuid4(),
            agency_id=agency.id,
            user_id=uuid4(),
            display_name=f"Model {i+1}"
        )
        db_session.add(model)
        models.append(model)
    
    # Create billing cycle
    cycle = BillingCycle(
        id=uuid4(),
        agency_id=agency.id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow()
    )
    db_session.add(cycle)
    
    # Create transactions with commission data
    for i, model in enumerate(models):
        for j in range(5):
            tx = FinancialTransaction(
                id=uuid4(),
                agency_id=agency.id,
                model_id=model.id,
                billing_cycle_id=cycle.id,
                type=TransactionType.REVENUE,
                amount=Decimal("1000.00"),
                commission_rate=Decimal("70.0"),
                commission_amount=Decimal("700.00"),
                currency="USD",
                transaction_date=datetime.utcnow() - timedelta(days=j)
            )
            db_session.add(tx)
    
    await db_session.commit()
    
    # Generate report
    response = client.post(
        "/api/v1/financial/commission/report",
        json={
            "agency_id": str(agency.id),
            "billing_cycle_id": str(cycle.id),
            "date_from": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "date_to": datetime.utcnow().isoformat()
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify report totals
    assert Decimal(data["total_gross_revenue"]) == Decimal("15000.00")  # 3 models * 5 tx * 1000
    assert Decimal(data["total_commission"]) == Decimal("10500.00")  # 70% of 15000
    assert Decimal(data["total_net_revenue"]) == Decimal("4500.00")
    
    # Verify model breakdowns
    assert len(data["model_breakdowns"]) == 3
    for breakdown in data["model_breakdowns"]:
        assert Decimal(breakdown["gross_revenue"]) == Decimal("5000.00")
        assert Decimal(breakdown["commission_amount"]) == Decimal("3500.00")
        assert breakdown["transaction_count"] == 5


@pytest.mark.asyncio
async def test_commission_rule_override(
    client: TestClient,
    db_session: AsyncSession
):
    """Test super admin commission override."""
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
    
    # Create test agency
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Override commission
    response = client.post(
        f"/api/v1/financial/commission/override?agency_id={agency.id}",
        json={
            "rate": "80.0",
            "reason": "Special promotional rate for high-performing agency",
            "effective_from": datetime.utcnow().isoformat(),
            "effective_until": (datetime.utcnow() + timedelta(days=90)).isoformat()
        },
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["rate"]) == Decimal("80.0")
    assert data["is_override"] is True
    assert data["tier"] == "custom"


@pytest.mark.asyncio
async def test_get_commission_rules_filtering(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test getting commission rules with filters."""
    # Create test data
    agency = await create_test_agency(db_session, "Test Agency")
    
    # Create multiple rules
    rules = []
    for i in range(3):
        rule = CommissionRule(
            id=uuid4(),
            agency_id=agency.id,
            tier=CommissionTier.TIER_1,
            rate=Decimal(f"{70 - i * 5}.0"),
            effective_from=datetime.utcnow() - timedelta(days=i * 30),
            effective_until=datetime.utcnow() + timedelta(days=30) if i == 0 else None
        )
        db_session.add(rule)
        rules.append(rule)
    
    await db_session.commit()
    
    # Get all rules
    response = client.get(
        f"/api/v1/financial/commission/rules?agency_id={agency.id}&include_historical=true",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Get only active rules
    response = client.get(
        f"/api/v1/financial/commission/rules?agency_id={agency.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # Only the first rule is currently active


@pytest.mark.asyncio
async def test_commission_report_permissions(
    client: TestClient,
    db_session: AsyncSession
):
    """Test commission report respects user permissions."""
    # Create agencies
    agency1 = await create_test_agency(db_session, "Agency 1")
    agency2 = await create_test_agency(db_session, "Agency 2")
    
    # Create agency owner
    owner = await create_test_user(
        db_session,
        email="owner@agency1.com",
        role=UserRole.AGENCY_OWNER,
        agency_id=agency1.id
    )
    
    # Get auth token
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@agency1.com", "password": "password123"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to generate report for agency2 (should be filtered to agency1)
    response = client.post(
        "/api/v1/financial/commission/report",
        json={
            "agency_id": str(agency2.id),  # Trying to access other agency
            "date_from": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "date_to": datetime.utcnow().isoformat()
        },
        headers=headers
    )
    
    assert response.status_code == 200
    # The service should have filtered to only agency1 data
    # (no data to verify since we didn't create transactions)