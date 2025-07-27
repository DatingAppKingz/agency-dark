"""
Integration tests for payment webhook endpoints.
"""
import pytest
import json
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionStatus,
    TransactionType
)
from modules.financial.application.payment_gateway_service import (
    PaymentGatewayService,
    CoinbaseCommerceProvider
)
from core.domain.models import ModelProfile


class TestPaymentWebhookEndpoints:
    
    @pytest.fixture
    async def test_transaction(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Create a test transaction."""
        transaction = FinancialTransaction(
            id=uuid4(),
            agency_id=test_model_profile.agency_id,
            model_id=test_model_profile.id,
            type=TransactionType.REVENUE,
            amount=Decimal("100.00"),
            currency="USD",
            status=TransactionStatus.PENDING,
            external_reference="test_charge_123",
            description="Test crypto payment",
            transaction_date=datetime.utcnow()
        )
        db_session.add(transaction)
        await db_session.commit()
        return transaction
    
    @pytest.fixture
    def coinbase_signature(self):
        """Generate Coinbase webhook signature."""
        def _sign(payload: bytes, secret: str = "test_webhook_secret"):
            return hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
        return _sign
    
    @pytest.mark.asyncio
    async def test_coinbase_webhook_payment_confirmed(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction,
        coinbase_signature,
        db_session: AsyncSession
    ):
        """Test Coinbase webhook for payment confirmation."""
        # Create webhook payload
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "code": test_transaction.external_reference,
                    "pricing": {
                        "local": {
                            "amount": "100.00",
                            "currency": "USD"
                        }
                    },
                    "payments": [{
                        "network": "bitcoin",
                        "transaction_id": "btc_tx_123",
                        "status": "confirmed"
                    }],
                    "metadata": {
                        "transaction_id": str(test_transaction.id)
                    }
                }
            }
        }
        
        payload = json.dumps(webhook_data).encode()
        signature = coinbase_signature(payload)
        
        # Mock payment gateway service
        with pytest.mock.patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = pytest.mock.AsyncMock(return_value=True)
            
            # Send webhook request
            response = await client.post(
                "/api/v1/payments/webhooks/coinbase",
                content=payload,
                headers={
                    "X-CC-Webhook-Signature": signature,
                    "Content-Type": "application/json"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "success"
        
        # Verify transaction was updated
        await db_session.refresh(test_transaction)
        assert test_transaction.status == TransactionStatus.COMPLETED
        assert test_transaction.processed_at is not None
        assert test_transaction.metadata.get("webhook_confirmed") is True
    
    @pytest.mark.asyncio
    async def test_coinbase_webhook_payment_failed(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction,
        coinbase_signature,
        db_session: AsyncSession
    ):
        """Test Coinbase webhook for payment failure."""
        webhook_data = {
            "event": {
                "type": "charge:failed",
                "data": {
                    "code": test_transaction.external_reference,
                    "failure_reason": "Payment window expired"
                }
            }
        }
        
        payload = json.dumps(webhook_data).encode()
        signature = coinbase_signature(payload)
        
        with pytest.mock.patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = pytest.mock.AsyncMock(return_value=True)
            
            response = await client.post(
                "/api/v1/payments/webhooks/coinbase",
                content=payload,
                headers={
                    "X-CC-Webhook-Signature": signature,
                    "Content-Type": "application/json"
                }
            )
            
            assert response.status_code == 200
        
        # Verify transaction was marked as failed
        await db_session.refresh(test_transaction)
        assert test_transaction.status == TransactionStatus.FAILED
        assert test_transaction.metadata.get("failure_reason") == "Payment window expired"
    
    @pytest.mark.asyncio
    async def test_coinbase_webhook_invalid_signature(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction
    ):
        """Test Coinbase webhook with invalid signature."""
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {"code": test_transaction.external_reference}
            }
        }
        
        with pytest.mock.patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = pytest.mock.AsyncMock(return_value=False)
            
            response = await client.post(
                "/api/v1/payments/webhooks/coinbase",
                json=webhook_data,
                headers={
                    "X-CC-Webhook-Signature": "invalid_signature"
                }
            )
            
            assert response.status_code == 401
            assert "Invalid signature" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_bitpay_webhook_invoice_confirmed(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction,
        db_session: AsyncSession
    ):
        """Test BitPay webhook for invoice confirmation."""
        webhook_data = {
            "event": {
                "name": "invoice_confirmed"
            },
            "data": {
                "id": test_transaction.external_reference,
                "price": 100.00,
                "currency": "USD",
                "status": "confirmed",
                "transactionCurrency": "BTC",
                "amountPaid": 0.0025
            }
        }
        
        response = await client.post(
            "/api/v1/payments/webhooks/bitpay",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify transaction was updated
        await db_session.refresh(test_transaction)
        assert test_transaction.status == TransactionStatus.COMPLETED
        assert test_transaction.processed_at is not None
    
    @pytest.mark.asyncio
    async def test_bitpay_webhook_invoice_expired(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction,
        db_session: AsyncSession
    ):
        """Test BitPay webhook for invoice expiration."""
        webhook_data = {
            "event": {
                "name": "invoice_expired"
            },
            "data": {
                "id": test_transaction.external_reference,
                "status": "expired"
            }
        }
        
        response = await client.post(
            "/api/v1/payments/webhooks/bitpay",
            json=webhook_data
        )
        
        assert response.status_code == 200
        
        # Verify transaction was marked as failed
        await db_session.refresh(test_transaction)
        assert test_transaction.status == TransactionStatus.FAILED
        assert test_transaction.metadata.get("failure_reason") == "Payment expired"
    
    @pytest.mark.asyncio
    async def test_webhook_for_nonexistent_transaction(
        self,
        client: AsyncClient
    ):
        """Test webhook for non-existent transaction."""
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "code": "non_existent_charge",
                    "pricing": {
                        "local": {
                            "amount": "50.00",
                            "currency": "USD"
                        }
                    }
                }
            }
        }
        
        with pytest.mock.patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = pytest.mock.AsyncMock(return_value=True)
            
            response = await client.post(
                "/api/v1/payments/webhooks/coinbase",
                json=webhook_data,
                headers={
                    "X-CC-Webhook-Signature": "valid_signature"
                }
            )
            
            # Should still return success (webhook processed, just no matching transaction)
            assert response.status_code == 200
            assert response.json()["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_webhook_notification_sent(
        self,
        client: AsyncClient,
        test_transaction: FinancialTransaction,
        coinbase_signature
    ):
        """Test that webhook sends proper notifications."""
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "code": test_transaction.external_reference,
                    "pricing": {
                        "local": {
                            "amount": "100.00",
                            "currency": "USD"
                        }
                    }
                }
            }
        }
        
        payload = json.dumps(webhook_data).encode()
        signature = coinbase_signature(payload)
        
        with pytest.mock.patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = pytest.mock.AsyncMock(return_value=True)
            
            with pytest.mock.patch('modules.financial.api.webhook_endpoints.send_notification') as mock_notify:
                mock_notify.return_value = pytest.mock.AsyncMock()
                
                response = await client.post(
                    "/api/v1/payments/webhooks/coinbase",
                    content=payload,
                    headers={
                        "X-CC-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                
                assert response.status_code == 200
                
                # Verify notification was sent
                mock_notify.assert_called_once()
                call_args = mock_notify.call_args[0]
                assert call_args[0] == "payment_confirmed"
                assert call_args[1]["transaction_id"] == str(test_transaction.id)
                assert call_args[1]["provider"] == "coinbase"
    
    @pytest.mark.asyncio
    async def test_stripe_webhook_placeholder(self, client: AsyncClient):
        """Test Stripe webhook placeholder endpoint."""
        response = await client.post(
            "/api/v1/payments/webhooks/stripe",
            json={"test": "data"},
            headers={"Stripe-Signature": "test_signature"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"
    
    @pytest.mark.asyncio
    async def test_paypal_webhook_placeholder(self, client: AsyncClient):
        """Test PayPal webhook placeholder endpoint."""
        response = await client.post(
            "/api/v1/payments/webhooks/paypal",
            json={"test": "data"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "not_implemented"