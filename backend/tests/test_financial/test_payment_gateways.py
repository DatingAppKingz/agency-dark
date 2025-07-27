"""
Tests for payment gateway implementations.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import json
import hmac
import hashlib

from modules.financial.infrastructure.stripe_gateway import StripeGateway
from modules.financial.infrastructure.coinbase_gateway import CoinbaseCommerceGateway
from modules.financial.infrastructure.payment_gateway_base import (
    PaymentRequest,
    PaymentStatus,
    WebhookData
)


class TestStripeGateway:
    """Test Stripe payment gateway functionality."""
    
    @pytest.fixture
    def stripe_config(self):
        """Stripe gateway configuration."""
        return {
            'api_key': 'test_stripe_api_key',
            'webhook_secret': 'test_webhook_secret',
            'is_test_mode': True
        }
    
    @pytest.fixture
    def stripe_gateway(self, stripe_config):
        """Create Stripe gateway instance."""
        return StripeGateway(stripe_config)
    
    def test_stripe_initialization(self, stripe_gateway, stripe_config):
        """Test Stripe gateway initialization."""
        assert stripe_gateway.api_key == stripe_config['api_key']
        assert stripe_gateway.webhook_secret == stripe_config['webhook_secret']
        assert stripe_gateway.is_test_mode is True
        assert stripe_gateway.base_url == StripeGateway.TEST_BASE_URL
    
    def test_stripe_required_config_keys(self, stripe_gateway):
        """Test Stripe required configuration keys."""
        required_keys = stripe_gateway.get_required_config_keys()
        assert 'api_key' in required_keys
        assert 'webhook_secret' in required_keys
    
    async def test_stripe_supported_currencies(self, stripe_gateway):
        """Test Stripe supported currencies."""
        currencies = await stripe_gateway.get_supported_currencies()
        assert 'USD' in currencies
        assert 'EUR' in currencies
        assert 'GBP' in currencies
        assert len(currencies) > 10  # Stripe supports many currencies
    
    async def test_stripe_exchange_rates(self, stripe_gateway):
        """Test Stripe exchange rates (demo rates)."""
        rates = await stripe_gateway.get_exchange_rates('USD')
        assert rates['USD'] == Decimal('1.00')
        assert 'EUR' in rates
        assert 'GBP' in rates
        assert all(isinstance(rate, Decimal) for rate in rates.values())
    
    def test_stripe_status_mapping(self, stripe_gateway):
        """Test Stripe status mapping."""
        assert stripe_gateway.map_status('succeeded') == PaymentStatus.COMPLETED
        assert stripe_gateway.map_status('processing') == PaymentStatus.PROCESSING
        assert stripe_gateway.map_status('canceled') == PaymentStatus.CANCELLED
        assert stripe_gateway.map_status('failed') == PaymentStatus.FAILED
        assert stripe_gateway.map_status('unknown') == PaymentStatus.PENDING
    
    async def test_stripe_webhook_verification(self, stripe_gateway):
        """Test Stripe webhook signature verification."""
        # Create test payload
        payload = json.dumps({'test': 'data'})
        timestamp = str(int(datetime.utcnow().timestamp()))
        
        # Create signature
        signed_payload = f"{timestamp}.{payload}"
        expected_signature = hmac.new(
            stripe_gateway.webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Create Stripe signature header
        signature = f"t={timestamp},v1={expected_signature}"
        
        headers = {'stripe-signature': signature}
        
        # Verify webhook
        is_valid = await stripe_gateway.verify_webhook(
            headers,
            payload.encode('utf-8'),
            stripe_gateway.webhook_secret
        )
        
        assert is_valid is True
        
        # Test invalid signature
        headers['stripe-signature'] = 't=123,v1=invalid'
        is_valid = await stripe_gateway.verify_webhook(
            headers,
            payload.encode('utf-8'),
            stripe_gateway.webhook_secret
        )
        assert is_valid is False
    
    async def test_stripe_webhook_parsing(self, stripe_gateway):
        """Test Stripe webhook parsing."""
        # Test payment intent succeeded
        webhook_body = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test123',
                    'object': 'payment_intent',
                    'amount': 10000,  # $100.00 in cents
                    'currency': 'usd',
                    'status': 'succeeded',
                    'metadata': {'order_id': '123'}
                }
            }
        }
        
        webhook_data = await stripe_gateway.parse_webhook(webhook_body)
        
        assert webhook_data.event_type == 'payment.completed'
        assert webhook_data.payment_id == 'pi_test123'
        assert webhook_data.status == PaymentStatus.COMPLETED
        assert webhook_data.amount == Decimal('100.00')
        assert webhook_data.currency == 'USD'
        assert webhook_data.metadata == {'order_id': '123'}
        
        # Test checkout session completed
        webhook_body = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test456',
                    'object': 'checkout.session',
                    'amount_total': 5000,  # $50.00 in cents
                    'currency': 'eur',
                    'payment_status': 'paid',
                    'metadata': {'customer_id': '456'}
                }
            }
        }
        
        webhook_data = await stripe_gateway.parse_webhook(webhook_body)
        
        assert webhook_data.event_type == 'payment.completed'
        assert webhook_data.payment_id == 'cs_test456'
        assert webhook_data.status == PaymentStatus.COMPLETED
        assert webhook_data.amount == Decimal('50.00')
        assert webhook_data.currency == 'EUR'


class TestCoinbaseCommerceGateway:
    """Test Coinbase Commerce payment gateway functionality."""
    
    @pytest.fixture
    def coinbase_config(self):
        """Coinbase Commerce gateway configuration."""
        return {
            'api_key': 'test_coinbase_api_key',
            'webhook_secret': 'test_webhook_secret',
            'is_test_mode': True
        }
    
    @pytest.fixture
    def coinbase_gateway(self, coinbase_config):
        """Create Coinbase Commerce gateway instance."""
        return CoinbaseCommerceGateway(coinbase_config)
    
    def test_coinbase_initialization(self, coinbase_gateway, coinbase_config):
        """Test Coinbase Commerce gateway initialization."""
        assert coinbase_gateway.api_key == coinbase_config['api_key']
        assert coinbase_gateway.webhook_secret == coinbase_config['webhook_secret']
        assert coinbase_gateway.is_test_mode is True
    
    def test_coinbase_required_config_keys(self, coinbase_gateway):
        """Test Coinbase Commerce required configuration keys."""
        required_keys = coinbase_gateway.get_required_config_keys()
        assert 'api_key' in required_keys
        assert 'webhook_secret' in required_keys
    
    async def test_coinbase_supported_currencies(self, coinbase_gateway):
        """Test Coinbase Commerce supported currencies."""
        currencies = await coinbase_gateway.get_supported_currencies()
        # Fiat currencies
        assert 'USD' in currencies
        assert 'EUR' in currencies
        # Crypto currencies
        assert 'BTC' in currencies
        assert 'ETH' in currencies
        assert 'USDC' in currencies
    
    def test_coinbase_status_mapping(self, coinbase_gateway):
        """Test Coinbase Commerce status mapping."""
        assert coinbase_gateway.map_status('NEW') == PaymentStatus.PENDING
        assert coinbase_gateway.map_status('PENDING') == PaymentStatus.PENDING
        assert coinbase_gateway.map_status('CONFIRMED') == PaymentStatus.COMPLETED
        assert coinbase_gateway.map_status('COMPLETED') == PaymentStatus.COMPLETED
        assert coinbase_gateway.map_status('UNRESOLVED') == PaymentStatus.FAILED
        assert coinbase_gateway.map_status('EXPIRED') == PaymentStatus.EXPIRED
        assert coinbase_gateway.map_status('CANCELED') == PaymentStatus.CANCELLED
    
    async def test_coinbase_webhook_verification(self, coinbase_gateway):
        """Test Coinbase Commerce webhook signature verification."""
        # Create test payload
        payload = json.dumps({'test': 'data'})
        
        # Create signature
        expected_signature = hmac.new(
            coinbase_gateway.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'x-cc-webhook-signature': expected_signature}
        
        # Verify webhook
        is_valid = await coinbase_gateway.verify_webhook(
            headers,
            payload.encode('utf-8'),
            coinbase_gateway.webhook_secret
        )
        
        assert is_valid is True
        
        # Test invalid signature
        headers['x-cc-webhook-signature'] = 'invalid_signature'
        is_valid = await coinbase_gateway.verify_webhook(
            headers,
            payload.encode('utf-8'),
            coinbase_gateway.webhook_secret
        )
        assert is_valid is False
    
    async def test_coinbase_webhook_parsing(self, coinbase_gateway):
        """Test Coinbase Commerce webhook parsing."""
        # Test charge confirmed
        webhook_body = {
            'event': {
                'type': 'charge:confirmed',
                'data': {
                    'id': 'charge_test123',
                    'code': 'TESTCODE123',
                    'pricing': {
                        'local': {
                            'amount': '100.00',
                            'currency': 'USD'
                        }
                    },
                    'timeline': [
                        {'status': 'NEW'},
                        {'status': 'PENDING'},
                        {'status': 'CONFIRMED'}
                    ],
                    'payments': [{
                        'status': 'CONFIRMED',
                        'transaction_id': '0x123abc',
                        'confirmations': 6,
                        'value': {
                            'local': {
                                'amount': '100.00',
                                'currency': 'USD'
                            }
                        }
                    }],
                    'metadata': {'order_id': '789'}
                }
            }
        }
        
        webhook_data = await coinbase_gateway.parse_webhook(webhook_body)
        
        assert webhook_data.event_type == 'payment.completed'
        assert webhook_data.payment_id == 'charge_test123'
        assert webhook_data.status == PaymentStatus.COMPLETED
        assert webhook_data.amount == Decimal('100.00')
        assert webhook_data.currency == 'USD'
        assert webhook_data.transaction_hash == '0x123abc'
        assert webhook_data.confirmations == 6
        assert webhook_data.metadata == {'order_id': '789'}
    
    async def test_coinbase_estimate_crypto_amount(self, coinbase_gateway):
        """Test crypto amount estimation."""
        # Mock exchange rates
        coinbase_gateway.get_exchange_rates = lambda base: {
            'USD': Decimal('1.00'),
            'BTC': Decimal('0.00002'),  # 1 BTC = $50,000
            'ETH': Decimal('0.0003'),    # 1 ETH = $3,333
            'USDC': Decimal('1.00')      # 1 USDC = $1
        }
        
        # Test BTC estimation
        estimate = await coinbase_gateway.estimate_crypto_amount(
            fiat_amount=Decimal('100.00'),
            fiat_currency='USD',
            crypto_currency='BTC'
        )
        
        assert estimate['amount'] == Decimal('0.002')  # $100 worth of BTC
        assert estimate['formatted'] == '0.00200000'
        assert estimate['currency'] == 'BTC'
        
        # Test USDC estimation
        estimate = await coinbase_gateway.estimate_crypto_amount(
            fiat_amount=Decimal('100.00'),
            fiat_currency='USD',
            crypto_currency='USDC'
        )
        
        assert estimate['amount'] == Decimal('100.00')
        assert estimate['formatted'] == '100.00'
        assert estimate['currency'] == 'USDC'


class TestPaymentGatewayBase:
    """Test base payment gateway functionality."""
    
    def test_format_amount(self):
        """Test amount formatting for different currencies."""
        from modules.financial.infrastructure.payment_gateway_base import PaymentGatewayBase
        
        # Create a mock gateway
        class MockGateway(PaymentGatewayBase):
            def get_required_config_keys(self):
                return []
            async def create_payment(self, request):
                pass
            async def get_payment_status(self, payment_id):
                pass
            async def cancel_payment(self, payment_id):
                pass
            async def verify_webhook(self, headers, body, webhook_secret):
                pass
            async def parse_webhook(self, body):
                pass
            async def get_supported_currencies(self):
                pass
            async def get_exchange_rates(self, base_currency='USD'):
                pass
        
        gateway = MockGateway({'is_test_mode': True})
        
        # Test crypto currencies (8 decimals)
        assert gateway.format_amount(Decimal('0.12345678'), 'BTC') == '0.12345678'
        assert gateway.format_amount(Decimal('1.23456789'), 'ETH') == '1.23456789'
        
        # Test fiat currencies (2 decimals)
        assert gateway.format_amount(Decimal('100.00'), 'USD') == '100.00'
        assert gateway.format_amount(Decimal('50.50'), 'EUR') == '50.50'
        assert gateway.format_amount(Decimal('123.456'), 'GBP') == '123.46'
        
        # Test stablecoins (2 decimals)
        assert gateway.format_amount(Decimal('100.00'), 'USDT') == '100.00'
        assert gateway.format_amount(Decimal('50.00'), 'USDC') == '50.00'
        
        # Test unknown currency (no formatting)
        assert gateway.format_amount(Decimal('123.456789'), 'XYZ') == '123.456789'
    
    def test_payment_request_dataclass(self):
        """Test PaymentRequest dataclass."""
        request = PaymentRequest(
            amount=Decimal('100.00'),
            currency='USD',
            description='Test payment',
            recipient_email='test@example.com',
            metadata={'order_id': '123'},
            redirect_url='https://example.com/success',
            webhook_url='https://example.com/webhook',
            expires_minutes=60
        )
        
        assert request.amount == Decimal('100.00')
        assert request.currency == 'USD'
        assert request.description == 'Test payment'
        assert request.recipient_email == 'test@example.com'
        assert request.metadata == {'order_id': '123'}
        assert request.redirect_url == 'https://example.com/success'
        assert request.webhook_url == 'https://example.com/webhook'
        assert request.expires_minutes == 60