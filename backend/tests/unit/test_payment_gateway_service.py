"""
Unit tests for PaymentGatewayService.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import json
import hmac
import hashlib

from modules.financial.application.payment_gateway_service import (
    PaymentGatewayService,
    CoinbaseCommerceProvider,
    BitPayProvider
)
from modules.financial.domain.models import (
    PaymentGatewayConfig,
    CryptoPayment,
    CryptoPaymentStatus,
    Payout,
    PayoutStatus
)
from modules.financial.domain.schemas import (
    PaymentGatewayConfigCreate,
    CryptoPaymentRequest
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_gateway_config():
    """Create a mock payment gateway configuration."""
    return PaymentGatewayConfig(
        id=uuid4(),
        provider="coinbase_commerce",
        api_key="test_api_key",
        webhook_secret="test_webhook_secret",
        is_test_mode=True,
        is_active=True,
        supported_currencies=["USD", "BTC", "ETH"]
    )


@pytest.fixture
def payment_gateway_service(mock_db):
    """Create a PaymentGatewayService instance."""
    return PaymentGatewayService(mock_db)


class TestPaymentGatewayService:
    """Test suite for PaymentGatewayService."""
    
    @pytest.mark.asyncio
    async def test_create_gateway_config(self, payment_gateway_service):
        """Test creating payment gateway configuration."""
        # Arrange
        config_data = PaymentGatewayConfigCreate(
            provider="coinbase_commerce",
            api_key="test_api_key",
            webhook_secret="test_secret",
            is_test_mode=True,
            supported_currencies=["USD", "BTC", "ETH"]
        )
        
        # Mock no existing config
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        payment_gateway_service.db.execute = AsyncMock(return_value=mock_result)
        payment_gateway_service.db.add = MagicMock()
        payment_gateway_service.db.commit = AsyncMock()
        payment_gateway_service.db.refresh = AsyncMock()
        
        # Act
        result = await payment_gateway_service.create_gateway_config(config_data)
        
        # Assert
        assert payment_gateway_service.db.add.called
        added_config = payment_gateway_service.db.add.call_args[0][0]
        assert added_config.provider == "coinbase_commerce"
        assert added_config.is_active is True
    
    @pytest.mark.asyncio
    async def test_create_duplicate_config_error(self, payment_gateway_service):
        """Test error when creating duplicate active configuration."""
        # Arrange
        config_data = PaymentGatewayConfigCreate(
            provider="coinbase_commerce",
            api_key="test_api_key"
        )
        
        # Mock existing config
        existing_config = PaymentGatewayConfig(id=uuid4(), provider="coinbase_commerce")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_config
        payment_gateway_service.db.execute = AsyncMock(return_value=mock_result)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await payment_gateway_service.create_gateway_config(config_data)
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_payment(self, payment_gateway_service, mock_gateway_config):
        """Test creating a payment with provider."""
        # Arrange
        payment_request = CryptoPaymentRequest(
            amount=Decimal("100.00"),
            currency="USD",
            description="Test payment",
            recipient_wallet_id=str(uuid4()),
            metadata={"order_id": "12345"}
        )
        
        # Mock get_provider
        mock_provider = AsyncMock()
        mock_provider.create_payment.return_value = {
            "payment_id": "test_payment_123",
            "payment_url": "https://commerce.coinbase.com/charges/test123",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "addresses": {"bitcoin": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        }
        
        with patch.object(payment_gateway_service, 'get_provider', return_value=mock_provider):
            payment_gateway_service.db.add = MagicMock()
            payment_gateway_service.db.commit = AsyncMock()
            payment_gateway_service.db.refresh = AsyncMock()
            
            # Act
            result = await payment_gateway_service.create_payment(
                payment_request,
                "coinbase_commerce"
            )
        
        # Assert
        assert result.payment_id == "test_payment_123"
        assert result.payment_url == "https://commerce.coinbase.com/charges/test123"
        assert result.amount == Decimal("100.00")
        assert payment_gateway_service.db.add.called
    
    @pytest.mark.asyncio
    async def test_process_webhook_success(self, payment_gateway_service):
        """Test processing valid webhook."""
        # Arrange
        provider_name = "coinbase_commerce"
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "id": "test_payment_123",
                    "payments": [{
                        "transaction_id": "0x123abc",
                        "value": {"local": {"amount": "100.00"}}
                    }],
                    "metadata": {"payout_id": str(uuid4())}
                }
            }
        }
        body = json.dumps(webhook_data).encode()
        headers = {"X-CC-Webhook-Signature": "valid_signature"}
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.verify_webhook.return_value = True
        mock_provider.process_webhook.return_value = {
            "payment_id": "test_payment_123",
            "status": CryptoPaymentStatus.CONFIRMED,
            "transaction_hash": "0x123abc",
            "amount_paid": "100.00",
            "metadata": webhook_data["event"]["data"]["metadata"]
        }
        
        # Mock payment record
        mock_payment = CryptoPayment(
            payment_id="test_payment_123",
            status=CryptoPaymentStatus.PENDING,
            metadata=webhook_data["event"]["data"]["metadata"]
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_payment
        
        with patch.object(payment_gateway_service, 'get_provider', return_value=mock_provider):
            payment_gateway_service.db.execute = AsyncMock(return_value=mock_result)
            payment_gateway_service.db.get = AsyncMock(return_value=None)  # No payout
            payment_gateway_service.db.commit = AsyncMock()
            
            # Act
            result = await payment_gateway_service.process_webhook(
                provider_name,
                headers,
                body
            )
        
        # Assert
        assert result['success'] is True
        assert result['payment_id'] == "test_payment_123"
        assert mock_payment.status == CryptoPaymentStatus.CONFIRMED
        assert mock_payment.transaction_hash == "0x123abc"
    
    @pytest.mark.asyncio
    async def test_process_webhook_invalid_signature(self, payment_gateway_service):
        """Test rejecting webhook with invalid signature."""
        # Arrange
        provider_name = "coinbase_commerce"
        body = b'{"test": "data"}'
        headers = {"X-CC-Webhook-Signature": "invalid_signature"}
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.verify_webhook.return_value = False
        
        with patch.object(payment_gateway_service, 'get_provider', return_value=mock_provider):
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                await payment_gateway_service.process_webhook(
                    provider_name,
                    headers,
                    body
                )
            
            assert "Invalid webhook signature" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_payment_status(self, payment_gateway_service):
        """Test checking payment status with provider."""
        # Arrange
        payment_id = "test_payment_123"
        
        # Mock payment record
        mock_payment = CryptoPayment(
            payment_id=payment_id,
            provider="coinbase_commerce",
            status=CryptoPaymentStatus.PENDING
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_payment
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.get_payment_status.return_value = {
            "status": CryptoPaymentStatus.COMPLETED,
            "transaction_hash": "0x456def"
        }
        
        payment_gateway_service.db.execute = AsyncMock(return_value=mock_result)
        payment_gateway_service.db.commit = AsyncMock()
        
        with patch.object(payment_gateway_service, 'get_provider', return_value=mock_provider):
            # Act
            status = await payment_gateway_service.check_payment_status(payment_id)
        
        # Assert
        assert status == CryptoPaymentStatus.COMPLETED
        assert mock_payment.transaction_hash == "0x456def"


class TestCoinbaseCommerceProvider:
    """Test suite for CoinbaseCommerceProvider."""
    
    @pytest.mark.asyncio
    async def test_create_payment(self, mock_gateway_config):
        """Test creating Coinbase Commerce payment."""
        # Arrange
        provider = CoinbaseCommerceProvider(mock_gateway_config)
        amount = Decimal("100.00")
        currency = "USD"
        description = "Test payment"
        metadata = {"order_id": "12345"}
        
        # Mock HTTP response
        mock_response = {
            "data": {
                "id": "charge_123",
                "hosted_url": "https://commerce.coinbase.com/charges/charge_123",
                "expires_at": "2024-01-01T12:00:00Z",
                "addresses": {
                    "bitcoin": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "ethereum": "0x123..."
                },
                "pricing": {
                    "local": {"amount": "100.00", "currency": "USD"},
                    "bitcoin": {"amount": "0.0025", "currency": "BTC"}
                }
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.status = 201
            mock_post.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_post
            
            # Act
            result = await provider.create_payment(amount, currency, description, metadata)
        
        # Assert
        assert result["payment_id"] == "charge_123"
        assert result["payment_url"] == "https://commerce.coinbase.com/charges/charge_123"
        assert result["expires_at"] == "2024-01-01T12:00:00Z"
        assert "bitcoin" in result["addresses"]
    
    def test_verify_webhook(self, mock_gateway_config):
        """Test Coinbase Commerce webhook verification."""
        # Arrange
        provider = CoinbaseCommerceProvider(mock_gateway_config)
        body = b'{"test": "data"}'
        
        # Calculate correct signature
        correct_signature = hmac.new(
            mock_gateway_config.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        headers = {"X-CC-Webhook-Signature": correct_signature}
        
        # Act
        result = provider.verify_webhook(headers, body)
        
        # Assert
        assert result is True
        
        # Test with wrong signature
        headers["X-CC-Webhook-Signature"] = "wrong_signature"
        assert provider.verify_webhook(headers, body) is False
    
    @pytest.mark.asyncio
    async def test_process_webhook(self):
        """Test processing Coinbase Commerce webhook."""
        # Arrange
        provider = CoinbaseCommerceProvider(MagicMock())
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "id": "charge_123",
                    "payments": [{
                        "transaction_id": "0x123abc",
                        "value": {"local": {"amount": "100.00"}}
                    }],
                    "metadata": {"order_id": "12345"}
                }
            }
        }
        
        # Act
        result = await provider.process_webhook(webhook_data)
        
        # Assert
        assert result["payment_id"] == "charge_123"
        assert result["status"] == CryptoPaymentStatus.CONFIRMED
        assert result["transaction_hash"] == "0x123abc"
        assert result["metadata"]["order_id"] == "12345"


class TestBitPayProvider:
    """Test suite for BitPayProvider."""
    
    @pytest.mark.asyncio
    async def test_create_payment(self, mock_gateway_config):
        """Test creating BitPay payment."""
        # Arrange
        mock_gateway_config.provider = "bitpay"
        provider = BitPayProvider(mock_gateway_config)
        amount = Decimal("100.00")
        currency = "USD"
        description = "Test payment"
        metadata = {"order_id": "12345", "webhook_url": "https://example.com/webhook"}
        
        # Mock HTTP response
        mock_response = {
            "data": {
                "id": "invoice_123",
                "url": "https://bitpay.com/invoice?id=invoice_123",
                "expirationTime": 1704110400000,  # Unix timestamp
                "bitcoinAddress": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "supportedTransactionCurrencies": ["BTC", "ETH"]
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.status = 200
            mock_post.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_post
            
            # Act
            result = await provider.create_payment(amount, currency, description, metadata)
        
        # Assert
        assert result["payment_id"] == "invoice_123"
        assert result["payment_url"] == "https://bitpay.com/invoice?id=invoice_123"
        assert "BTC" in result["addresses"]