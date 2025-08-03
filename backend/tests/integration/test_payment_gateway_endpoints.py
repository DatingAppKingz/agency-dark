"""
Integration tests for payment gateway API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import json
import hmac
import hashlib

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import MagicMock

from core.domain.models import User, UserRole
from modules.financial.domain.models import (\n    PaymentGatewayConfig,\n    CryptoWallet,\n    CryptoNetwork,\n    CryptoPayment,\n    CryptoPaymentStatus\n)
from tests.conftest import create_test_user, create_test_agency


@pytest.mark.asyncio
async def test_create_payment_gateway_config(
    client: TestClient,
    db_session: AsyncSession
):
    """Test creating payment gateway configuration (super admin only)."""
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
    
    # Create gateway config
    response = client.post(
        "/api/v1/financial/payment-gateways",
        json={
            "provider": "coinbase_commerce",
            "api_key": "test_api_key_123",
            "webhook_secret": "test_webhook_secret",
            "is_test_mode": True,
            "supported_currencies": ["USD", "BTC", "ETH", "USDT"]
        },
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "coinbase_commerce"
    assert data["is_test_mode"] is True
    assert data["is_active"] is True
    
    # Verify in database
    result = await db_session.execute(
        select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.provider == "coinbase_commerce"
        )
    )
    config = result.scalar_one()
    assert config.api_key == "test_api_key_123"


@pytest.mark.asyncio
async def test_create_gateway_config_permission_denied(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test that only super admin can create gateway config."""
    # Try with regular admin
    response = client.post(
        "/api/v1/financial/payment-gateways",
        json={
            "provider": "bitpay",
            "api_key": "test_key"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_payment_gateways(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test getting payment gateway configurations."""
    # Create test configs
    configs = [
        PaymentGatewayConfig(
            id=uuid4(),
            provider="coinbase_commerce",
            api_key="key1",
            is_active=True,
            is_test_mode=True,
            supported_currencies=["USD", "BTC"]
        ),
        PaymentGatewayConfig(
            id=uuid4(),
            provider="bitpay",
            api_key="key2",
            is_active=True,
            is_test_mode=False,
            supported_currencies=["USD", "ETH"]
        ),
        PaymentGatewayConfig(
            id=uuid4(),
            provider="stripe",
            api_key="key3",
            is_active=False,  # Inactive
            is_test_mode=True
        )
    ]
    
    for config in configs:
        db_session.add(config)
    await db_session.commit()
    
    # Get active configs
    response = client.get(
        "/api/v1/financial/payment-gateways",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Only active configs
    providers = [c["provider"] for c in data]
    assert "coinbase_commerce" in providers
    assert "bitpay" in providers
    assert "stripe" not in providers


@pytest.mark.asyncio
async def test_create_crypto_payment(
    client: TestClient,
    db_session: AsyncSession,
    auth_headers: dict
):
    """Test creating a crypto payment request."""
    # Create gateway config
    config = PaymentGatewayConfig(
        id=uuid4(),
        provider="coinbase_commerce",
        api_key="test_api_key",
        webhook_secret="test_secret",
        is_active=True,
        is_test_mode=True,
        supported_currencies=["USD", "BTC", "ETH"]
    )
    db_session.add(config)
    
    # Create wallet
    wallet = CryptoWallet(
        id=uuid4(),
        user_id=uuid4(),
        network=CryptoNetwork.BITCOIN,
        address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        is_active=True
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Mock the payment gateway service
    from unittest.mock import patch, AsyncMock
    
    mock_response = MagicMock()
    mock_response.payment_id = "test_payment_123"
    mock_response.payment_url = "https://commerce.coinbase.com/charges/test123"
    mock_response.amount = Decimal("100.00")
    mock_response.currency = "USD"
    mock_response.status = "pending"
    mock_response.expires_at = datetime.utcnow() + timedelta(hours=1)
    
    with patch('modules.financial.application.payment_gateway_service.PaymentGatewayService.create_payment') as mock_create:
        mock_create.return_value = mock_response
        
        # Create payment
        response = client.post(
            "/api/v1/financial/payments/crypto?provider=coinbase_commerce",
            json={
                "amount": "100.00",
                "currency": "USD",
                "description": "Test payment",
                "recipient_wallet_id": str(wallet.id),
                "metadata": {"order_id": "12345"}
            },
            headers=auth_headers
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["payment_id"] == "test_payment_123"
    assert data["payment_url"] == "https://commerce.coinbase.com/charges/test123"


@pytest.mark.asyncio
async def test_payment_webhook_coinbase(
    client: TestClient,
    db_session: AsyncSession
):
    """Test handling Coinbase Commerce webhook."""
    # Create gateway config
    webhook_secret = "test_webhook_secret"
    config = PaymentGatewayConfig(
        id=uuid4(),
        provider="coinbase_commerce",
        api_key="test_api_key",
        webhook_secret=webhook_secret,
        is_active=True
    )
    db_session.add(config)
    
    # Create payment record
    payment = CryptoPayment(
        id=uuid4(),
        provider="coinbase_commerce",
        payment_id="test_payment_123",
        amount=Decimal("100.00"),
        currency="USD",
        status=CryptoPaymentStatus.PENDING,
        metadata={"payout_id": str(uuid4())}
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Prepare webhook data
    webhook_data = {
        "event": {
            "type": "charge:confirmed",
            "data": {
                "id": "test_payment_123",
                "payments": [{
                    "transaction_id": "0x123abc",
                    "value": {"local": {"amount": "100.00"}}
                }],
                "metadata": payment.metadata
            }
        }
    }
    
    body = json.dumps(webhook_data).encode()
    
    # Calculate signature
    signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Send webhook
    response = client.post(
        "/api/v1/financial/webhooks/coinbase_commerce",
        content=body,
        headers={
            "X-CC-Webhook-Signature": signature,
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # Verify payment was updated
    await db_session.refresh(payment)
    assert payment.status == CryptoPaymentStatus.CONFIRMED
    assert payment.transaction_hash == "0x123abc"


@pytest.mark.asyncio
async def test_payment_webhook_invalid_signature(
    client: TestClient,
    db_session: AsyncSession
):
    """Test rejecting webhook with invalid signature."""
    # Create gateway config
    config = PaymentGatewayConfig(
        id=uuid4(),
        provider="coinbase_commerce",
        api_key="test_api_key",
        webhook_secret="test_webhook_secret",
        is_active=True
    )
    db_session.add(config)
    await db_session.commit()
    
    # Send webhook with wrong signature
    webhook_data = {"event": {"type": "charge:confirmed"}}
    body = json.dumps(webhook_data).encode()
    
    response = client.post(
        "/api/v1/financial/webhooks/coinbase_commerce",
        content=body,
        headers={
            "X-CC-Webhook-Signature": "wrong_signature",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_payment_webhook_bitpay(
    client: TestClient,
    db_session: AsyncSession
):
    """Test handling BitPay webhook."""
    # Create gateway config
    config = PaymentGatewayConfig(
        id=uuid4(),
        provider="bitpay",
        api_key="test_api_key",
        is_active=True
    )
    db_session.add(config)
    
    # Create payment record
    payment = CryptoPayment(
        id=uuid4(),
        provider="bitpay",
        payment_id="invoice_123",
        amount=Decimal("100.00"),
        currency="USD",
        status=CryptoPaymentStatus.PENDING
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Prepare webhook data
    webhook_data = {
        "id": "invoice_123",
        "status": "complete",
        "transactionId": "btc_tx_123",
        "amountPaid": 100000000,  # Satoshis
        "posData": json.dumps({"order_id": "12345"})
    }
    
    body = json.dumps(webhook_data).encode()
    
    # Send webhook
    response = client.post(
        "/api/v1/financial/webhooks/bitpay",
        content=body,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    
    # Verify payment was updated
    await db_session.refresh(payment)
    assert payment.status == CryptoPaymentStatus.COMPLETED
    assert payment.transaction_hash == "btc_tx_123"


@pytest.mark.asyncio
async def test_duplicate_gateway_config_error(
    client: TestClient,
    db_session: AsyncSession
):
    """Test error when creating duplicate active gateway config."""
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
    
    # Create first config
    config = PaymentGatewayConfig(
        id=uuid4(),
        provider="coinbase_commerce",
        api_key="existing_key",
        is_active=True
    )
    db_session.add(config)
    await db_session.commit()
    
    # Try to create duplicate
    response = client.post(
        "/api/v1/financial/payment-gateways",
        json={
            "provider": "coinbase_commerce",
            "api_key": "new_key",
            "is_test_mode": True
        },
        headers=headers
    )
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unsupported_provider_error(
    client: TestClient,
    db_session: AsyncSession
):
    """Test error when using unsupported payment provider."""
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
    
    # Try unsupported provider
    response = client.post(
        "/api/v1/financial/payment-gateways",
        json={
            "provider": "unknown_provider",
            "api_key": "test_key"
        },
        headers=headers
    )
    
    assert response.status_code == 400
    assert "Unsupported provider" in response.json()["detail"]