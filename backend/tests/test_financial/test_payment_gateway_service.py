"""
Tests for payment gateway service.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import json
from uuid import uuid4

from modules.financial.application.payment_gateway_service import PaymentGatewayService
from models.financial import TransactionType
from modules.financial.domain.models import PaymentGatewayConfig, CryptoPayment, CryptoPaymentStatus, FinancialTransaction
from modules.financial.domain.schemas import (
    PaymentGatewayConfigCreate,
    CryptoPaymentRequest
)
from modules.financial.infrastructure.payment_gateway_base import PaymentStatus
from core.domain.models import Agency


@pytest.fixture
async def payment_service(db_session):
    """Create payment gateway service instance."""
    return PaymentGatewayService(db_session)


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
async def stripe_config(db_session, test_agency):
    """Create Stripe gateway configuration."""
    config = PaymentGatewayConfig(
        gateway_type="stripe",
        agency_id=test_agency.id,
        config={
            'api_key': 'test_stripe_key',
            'webhook_secret': 'test_webhook_secret'
        },
        is_active=True,
        is_test_mode=True
    )
    db_session.add(config)
    await db_session.commit()
    return config


@pytest.fixture
async def coinbase_config(db_session, test_agency):
    """Create Coinbase Commerce gateway configuration."""
    config = PaymentGatewayConfig(
        gateway_type="coinbase_commerce",
        agency_id=test_agency.id,
        config={
            'api_key': 'test_coinbase_key',
            'webhook_secret': 'test_webhook_secret'
        },
        is_active=True,
        is_test_mode=True
    )
    db_session.add(config)
    await db_session.commit()
    return config


class TestPaymentGatewayService:
    """Test payment gateway service functionality."""
    
    async def test_create_gateway_config(
        self,
        payment_service,
        test_agency
    ):
        """Test creating gateway configuration."""
        config_data = PaymentGatewayConfigCreate(
            gateway_type="stripe",
            agency_id=str(test_agency.id),
            config={
                'api_key': 'sk_test_123',
                'webhook_secret': 'whsec_test_123'
            },
            is_active=True,
            is_test_mode=True
        )
        
        config = await payment_service.create_gateway_config(config_data)
        
        assert config.gateway_type == "stripe"
        assert config.agency_id == str(test_agency.id)
        assert config.is_active is True
        assert config.is_test_mode is True
        assert config.config['api_key'] == 'sk_test_123'
    
    async def test_create_duplicate_config(
        self,
        payment_service,
        test_agency,
        stripe_config
    ):
        """Test creating duplicate active configuration."""
        config_data = PaymentGatewayConfigCreate(
            gateway_type="stripe",
            agency_id=str(test_agency.id),
            config={
                'api_key': 'sk_test_456',
                'webhook_secret': 'whsec_test_456'
            },
            is_active=True,
            is_test_mode=True
        )
        
        with pytest.raises(ValueError, match="Active stripe configuration already exists"):
            await payment_service.create_gateway_config(config_data)
    
    async def test_get_active_configs(
        self,
        payment_service,
        test_agency,
        stripe_config,
        coinbase_config
    ):
        """Test getting active gateway configurations."""
        # Get all configs for agency
        configs = await payment_service.get_active_configs(str(test_agency.id))
        assert len(configs) == 2
        
        gateway_types = {c.gateway_type for c in configs}
        assert "stripe" in gateway_types
        assert "coinbase_commerce" in gateway_types
    
    async def test_get_gateway(
        self,
        payment_service,
        test_agency,
        stripe_config
    ):
        """Test getting initialized gateway instance."""
        gateway = await payment_service.get_gateway("stripe", str(test_agency.id))
        
        assert gateway is not None
        assert gateway.api_key == stripe_config.config['api_key']
        assert gateway.is_test_mode is True
        
        # Test caching
        gateway2 = await payment_service.get_gateway("stripe", str(test_agency.id))
        assert gateway is gateway2  # Same instance
    
    async def test_get_gateway_not_found(
        self,
        payment_service,
        test_agency
    ):
        """Test getting gateway with no configuration."""
        with pytest.raises(ValueError, match="No active configuration found"):
            await payment_service.get_gateway("paypal", str(test_agency.id))
    
    async def test_create_payment(
        self,
        payment_service,
        test_agency,
        stripe_config,
        monkeypatch
    ):
        """Test creating a payment."""
        # Mock gateway create_payment
        async def mock_create_payment(self, request):
            from modules.financial.infrastructure.payment_gateway_base import PaymentResponse
            return PaymentResponse(
                payment_id="pi_test123",
                provider_payment_id="pi_test123",
                status=PaymentStatus.PENDING,
                amount=request.amount,
                currency=request.currency,
                payment_url="https://checkout.stripe.com/test123",
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.create_payment",
            mock_create_payment
        )
        
        payment_request = CryptoPaymentRequest(
            amount=Decimal("100.00"),
            currency="USD",
            description="Test payment",
            model_id=str(uuid4()),
            fan_id=str(uuid4()),
            customer_email="customer@test.com",
            payment_type="tip",
            redirect_url="https://example.com/success"
        )
        
        payment = await payment_service.create_payment(
            payment_request,
            "stripe",
            str(test_agency.id)
        )
        
        assert payment.provider == "stripe"
        assert payment.amount == Decimal("100.00")
        assert payment.currency == "USD"
        assert payment.status == CryptoPaymentStatus.PENDING
        assert payment.payment_url == "https://checkout.stripe.com/test123"
    
    async def test_get_payment_status(
        self,
        payment_service,
        test_agency,
        stripe_config,
        db_session,
        monkeypatch
    ):
        """Test getting payment status."""
        # Create payment record
        payment = CryptoPayment(
            provider="stripe",
            provider_payment_id="pi_test123",
            amount=Decimal("100.00"),
            currency="USD",
            status=CryptoPaymentStatus.PENDING,
            payment_url="https://checkout.stripe.com/test123",
            metadata={'gateway_payment_id': 'pi_test123'}
        )
        db_session.add(payment)
        await db_session.commit()
        
        # Mock gateway get_payment_status
        async def mock_get_status(self, payment_id):
            from modules.financial.infrastructure.payment_gateway_base import PaymentResponse
            return PaymentResponse(
                payment_id=payment_id,
                provider_payment_id=payment_id,
                status=PaymentStatus.COMPLETED,
                amount=Decimal("100.00"),
                currency="USD",
                metadata={'transaction_hash': '0xabc123'}
            )
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.get_payment_status",
            mock_get_status
        )
        
        status = await payment_service.get_payment_status(str(payment.id))
        
        assert status.status == CryptoPaymentStatus.COMPLETED
        assert status.transaction_hash == '0xabc123'
    
    async def test_process_webhook(
        self,
        payment_service,
        test_agency,
        stripe_config,
        db_session,
        monkeypatch
    ):
        """Test processing payment webhook."""
        # Create payment record
        payment = CryptoPayment(
            provider="stripe",
            provider_payment_id="pi_test123",
            amount=Decimal("100.00"),
            currency="USD",
            status=CryptoPaymentStatus.PENDING,
            payment_url="https://checkout.stripe.com/test123",
            metadata={'gateway_payment_id': 'pi_test123'},
            model_id=uuid4(),
            fan_id=uuid4()
        )
        db_session.add(payment)
        await db_session.commit()
        
        # Mock gateway webhook verification and parsing
        async def mock_verify_webhook(self, headers, body, webhook_secret):
            return True
        
        async def mock_parse_webhook(self, body):
            from modules.financial.infrastructure.payment_gateway_base import WebhookData
            return WebhookData(
                event_type="payment.completed",
                payment_id="pi_test123",
                status=PaymentStatus.COMPLETED,
                amount=Decimal("100.00"),
                currency="USD",
                transaction_hash="0xdef456"
            )
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.verify_webhook",
            mock_verify_webhook
        )
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.parse_webhook",
            mock_parse_webhook
        )
        
        # Process webhook
        webhook_body = json.dumps({
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_test123'}}
        })
        
        result = await payment_service.process_webhook(
            "stripe",
            {'stripe-signature': 'test_sig'},
            webhook_body.encode()
        )
        
        assert result['success'] is True
        assert result['payment_id'] == str(payment.id)
        
        # Verify payment was updated
        await db_session.refresh(payment)
        assert payment.status == CryptoPaymentStatus.COMPLETED
        assert payment.transaction_hash == "0xdef456"
        
        # Verify transaction was created
        transactions = await db_session.execute(
            "SELECT * FROM financial_transactions WHERE crypto_payment_id = :payment_id",
            {"payment_id": payment.id}
        )
        tx = transactions.first()
        assert tx is not None
        assert tx.type == TransactionType.REVENUE
        assert tx.amount == Decimal("100.00")
    
    async def test_cancel_payment(
        self,
        payment_service,
        test_agency,
        stripe_config,
        db_session,
        monkeypatch
    ):
        """Test cancelling a payment."""
        # Create payment record
        payment = CryptoPayment(
            provider="stripe",
            provider_payment_id="pi_test123",
            amount=Decimal("100.00"),
            currency="USD",
            status=CryptoPaymentStatus.PENDING,
            payment_url="https://checkout.stripe.com/test123",
            metadata={'gateway_payment_id': 'pi_test123'}
        )
        db_session.add(payment)
        await db_session.commit()
        
        # Mock gateway cancel_payment
        async def mock_cancel(self, payment_id):
            return True
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.cancel_payment",
            mock_cancel
        )
        
        success = await payment_service.cancel_payment(str(payment.id))
        
        assert success is True
        
        # Verify payment was cancelled
        await db_session.refresh(payment)
        assert payment.status == CryptoPaymentStatus.CANCELLED
    
    async def test_get_supported_currencies(
        self,
        payment_service,
        test_agency,
        stripe_config,
        monkeypatch
    ):
        """Test getting supported currencies."""
        # Mock gateway method
        async def mock_currencies(self):
            return ['USD', 'EUR', 'GBP', 'BTC', 'ETH']
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.get_supported_currencies",
            mock_currencies
        )
        
        currencies = await payment_service.get_supported_currencies("stripe")
        
        assert 'USD' in currencies
        assert 'EUR' in currencies
        assert 'BTC' in currencies
        assert len(currencies) == 5
    
    async def test_get_exchange_rates(
        self,
        payment_service,
        test_agency,
        stripe_config,
        monkeypatch
    ):
        """Test getting exchange rates."""
        # Mock gateway method
        async def mock_rates(self, base_currency):
            return {
                'USD': Decimal('1.00'),
                'EUR': Decimal('0.85'),
                'GBP': Decimal('0.73'),
                'BTC': Decimal('0.00002')
            }
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.get_exchange_rates",
            mock_rates
        )
        
        rates = await payment_service.get_exchange_rates("stripe", "USD")
        
        assert rates['USD'] == 1.0
        assert rates['EUR'] == 0.85
        assert rates['BTC'] == 0.00002
        assert all(isinstance(rate, float) for rate in rates.values())
    
    async def test_test_gateway_connection(
        self,
        payment_service,
        monkeypatch
    ):
        """Test testing gateway connection."""
        # Mock gateway health check
        async def mock_health_check(self):
            return {
                'status': 'healthy',
                'provider': 'StripeGateway',
                'test_mode': True
            }
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.health_check",
            mock_health_check
        )
        
        result = await payment_service.test_gateway_connection(
            "stripe",
            {
                'api_key': 'test_key',
                'webhook_secret': 'test_secret'
            }
        )
        
        assert result['success'] is True
        assert result['details']['status'] == 'healthy'
    
    async def test_webhook_invalid_signature(
        self,
        payment_service,
        stripe_config,
        monkeypatch
    ):
        """Test webhook with invalid signature."""
        # Mock gateway webhook verification to fail
        async def mock_verify_webhook(self, headers, body, webhook_secret):
            return False
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.verify_webhook",
            mock_verify_webhook
        )
        
        result = await payment_service.process_webhook(
            "stripe",
            {'stripe-signature': 'invalid_sig'},
            b'{"test": "data"}'
        )
        
        assert result['success'] is False
        assert result['error'] == 'Invalid signature'
    
    async def test_webhook_payment_not_found(
        self,
        payment_service,
        stripe_config,
        monkeypatch
    ):
        """Test webhook for non-existent payment."""
        # Mock gateway methods
        async def mock_verify_webhook(self, headers, body, webhook_secret):
            return True
        
        async def mock_parse_webhook(self, body):
            from modules.financial.infrastructure.payment_gateway_base import WebhookData
            return WebhookData(
                event_type="payment.completed",
                payment_id="pi_notfound",
                status=PaymentStatus.COMPLETED
            )
        
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.verify_webhook",
            mock_verify_webhook
        )
        monkeypatch.setattr(
            "modules.financial.infrastructure.stripe_gateway.StripeGateway.parse_webhook",
            mock_parse_webhook
        )
        
        result = await payment_service.process_webhook(
            "stripe",
            {'stripe-signature': 'test_sig'},
            b'{"test": "data"}'
        )
        
        assert result['success'] is False
        assert result['error'] == 'Payment not found'
    
    async def test_global_vs_agency_config(
        self,
        payment_service,
        test_agency,
        db_session
    ):
        """Test global vs agency-specific configuration priority."""
        # Create global config
        global_config = PaymentGatewayConfig(
            gateway_type="stripe",
            agency_id=None,  # Global
            config={
                'api_key': 'global_key',
                'webhook_secret': 'global_secret'
            },
            is_active=True,
            is_test_mode=True
        )
        db_session.add(global_config)
        
        # Create agency-specific config
        agency_config = PaymentGatewayConfig(
            gateway_type="stripe",
            agency_id=test_agency.id,
            config={
                'api_key': 'agency_key',
                'webhook_secret': 'agency_secret'
            },
            is_active=True,
            is_test_mode=True
        )
        db_session.add(agency_config)
        await db_session.commit()
        
        # Get gateway with agency ID (should use agency-specific)
        gateway = await payment_service.get_gateway("stripe", str(test_agency.id))
        assert gateway.api_key == 'agency_key'
        
        # Get gateway without agency ID (should use global)
        payment_service._gateway_cache.clear()  # Clear cache
        gateway = await payment_service.get_gateway("stripe", None)
        assert gateway.api_key == 'global_key'