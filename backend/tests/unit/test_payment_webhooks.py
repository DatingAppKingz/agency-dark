"""
Unit tests for payment webhook handlers.
"""
import pytest
import json
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from modules.financial.api.webhook_endpoints import (
    handle_coinbase_webhook,
    handle_bitpay_webhook,
    handle_payment_confirmed,
    handle_payment_failed,
    handle_payment_delayed,
    handle_payment_expired
)
from models.financial import TransactionStatus, TransactionType
from modules.financial.domain.models import FinancialTransaction
from modules.financial.application.payment_gateway_service import PaymentGatewayService
from core.domain.models import ModelProfile


class TestPaymentWebhooks:
    
    @pytest.fixture
    def mock_transaction(self):
        """Create a mock transaction."""
        return FinancialTransaction(
            id=uuid4(),
            model_id=uuid4(),
            agency_id=uuid4(),
            amount=Decimal("100.00"),
            currency="USD",
            type=TransactionType.REVENUE,
            status=TransactionStatus.PENDING,
            external_reference="test_payment_123",
            description="Test payment",
            metadata={}
        )
    
    @pytest.fixture
    def coinbase_webhook_data(self):
        """Sample Coinbase webhook payload."""
        return {
            "event": {
                "type": "charge:confirmed",
                "data": {
                    "code": "test_payment_123",
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
                    }]
                }
            }
        }
    
    @pytest.fixture
    def bitpay_webhook_data(self):
        """Sample BitPay webhook payload."""
        return {
            "event": {
                "name": "invoice_confirmed"
            },
            "data": {
                "id": "test_payment_123",
                "price": 100.00,
                "currency": "USD",
                "status": "confirmed"
            }
        }
    
    @pytest.mark.asyncio
    async def test_handle_payment_confirmed(self, db_session: AsyncSession, mock_transaction):
        """Test handling payment confirmation."""
        # Add transaction to db
        db_session.add(mock_transaction)
        await db_session.commit()
        
        # Mock transaction service
        with patch('modules.financial.api.webhook_endpoints.TransactionService') as mock_service:
            mock_service.return_value.get_transaction_by_external_ref = AsyncMock(
                return_value=mock_transaction
            )
            
            # Mock notification
            with patch('modules.financial.api.webhook_endpoints.send_notification') as mock_notify:
                mock_notify.return_value = AsyncMock()
                
                # Handle payment confirmation
                await handle_payment_confirmed(
                    db_session,
                    "coinbase",
                    {
                        "code": "test_payment_123",
                        "pricing": {
                            "local": {
                                "amount": "100.00",
                                "currency": "USD"
                            }
                        }
                    }
                )
                
                # Verify transaction was updated
                assert mock_transaction.status == TransactionStatus.COMPLETED
                assert mock_transaction.processed_at is not None
                assert mock_transaction.metadata.get("webhook_confirmed") is True
                
                # Verify notification was sent
                mock_notify.assert_called_once()
                call_args = mock_notify.call_args[0]
                assert call_args[0] == "payment_confirmed"
                assert call_args[1]["transaction_id"] == str(mock_transaction.id)
    
    @pytest.mark.asyncio
    async def test_handle_payment_failed(self, db_session: AsyncSession, mock_transaction):
        """Test handling payment failure."""
        db_session.add(mock_transaction)
        await db_session.commit()
        
        with patch('modules.financial.api.webhook_endpoints.TransactionService') as mock_service:
            mock_service.return_value.get_transaction_by_external_ref = AsyncMock(
                return_value=mock_transaction
            )
            
            with patch('modules.financial.api.webhook_endpoints.send_notification') as mock_notify:
                mock_notify.return_value = AsyncMock()
                
                await handle_payment_failed(
                    db_session,
                    "coinbase",
                    {
                        "code": "test_payment_123",
                        "failure_reason": "Insufficient funds"
                    }
                )
                
                assert mock_transaction.status == TransactionStatus.FAILED
                assert mock_transaction.metadata.get("failure_reason") == "Insufficient funds"
                
                mock_notify.assert_called_once()
                assert mock_notify.call_args[0][0] == "payment_failed"
    
    @pytest.mark.asyncio
    async def test_coinbase_webhook_signature_verification(self, db_session: AsyncSession):
        """Test Coinbase webhook signature verification."""
        # Create mock request
        webhook_data = {
            "event": {
                "type": "charge:confirmed",
                "data": {"code": "test_123"}
            }
        }
        body = json.dumps(webhook_data).encode()
        
        # Create valid signature
        secret = "test_secret"
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        mock_request.json = AsyncMock(return_value=webhook_data)
        
        # Mock gateway service
        with patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = AsyncMock(return_value=True)
            
            # Mock transaction service
            with patch('modules.financial.api.webhook_endpoints.TransactionService'):
                with patch('modules.financial.api.webhook_endpoints.handle_payment_confirmed') as mock_handler:
                    mock_handler.return_value = AsyncMock()
                    
                    # Should succeed with valid signature
                    result = await handle_coinbase_webhook(
                        mock_request,
                        signature,
                        db_session
                    )
                    
                    assert result["status"] == "success"
                    mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_coinbase_webhook_invalid_signature(self, db_session: AsyncSession):
        """Test Coinbase webhook with invalid signature."""
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"test": "data"}')
        
        with patch('modules.financial.api.webhook_endpoints.PaymentGatewayService') as mock_gateway:
            mock_gateway.return_value.verify_webhook_signature = AsyncMock(return_value=False)
            
            with pytest.raises(HTTPException) as exc_info:
                await handle_coinbase_webhook(
                    mock_request,
                    "invalid_signature",
                    db_session
                )
            
            assert exc_info.value.status_code == 401
            assert "Invalid signature" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_payment_delayed(self, db_session: AsyncSession, mock_transaction):
        """Test handling payment delay notification."""
        db_session.add(mock_transaction)
        await db_session.commit()
        
        with patch('modules.financial.api.webhook_endpoints.TransactionService') as mock_service:
            mock_service.return_value.get_transaction_by_external_ref = AsyncMock(
                return_value=mock_transaction
            )
            
            with patch('modules.financial.api.webhook_endpoints.send_notification') as mock_notify:
                mock_notify.return_value = AsyncMock()
                
                await handle_payment_delayed(
                    db_session,
                    "coinbase",
                    {
                        "code": "test_payment_123",
                        "reason": "Network congestion"
                    }
                )
                
                assert mock_transaction.metadata.get("payment_delayed") is True
                assert mock_transaction.metadata.get("delay_reason") == "Network congestion"
                
                mock_notify.assert_called_once()
                assert mock_notify.call_args[0][0] == "payment_delayed"
    
    @pytest.mark.asyncio
    async def test_bitpay_webhook_handling(self, db_session: AsyncSession, bitpay_webhook_data):
        """Test BitPay webhook handling."""
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=bitpay_webhook_data)
        
        with patch('modules.financial.api.webhook_endpoints.handle_payment_confirmed') as mock_handler:
            mock_handler.return_value = AsyncMock()
            
            result = await handle_bitpay_webhook(mock_request, db_session)
            
            assert result["status"] == "success"
            mock_handler.assert_called_once_with(
                db_session,
                "bitpay",
                bitpay_webhook_data["data"]
            )
    
    @pytest.mark.asyncio
    async def test_transaction_not_found(self, db_session: AsyncSession):
        """Test handling webhook for non-existent transaction."""
        with patch('modules.financial.api.webhook_endpoints.TransactionService') as mock_service:
            mock_service.return_value.get_transaction_by_external_ref = AsyncMock(
                return_value=None
            )
            
            # Should not raise error, just log warning
            await handle_payment_confirmed(
                db_session,
                "coinbase",
                {"code": "non_existent_123"}
            )
            
            # No exception should be raised
    
    @pytest.mark.asyncio
    async def test_handle_payment_expired(self, db_session: AsyncSession, mock_transaction):
        """Test handling payment expiration."""
        db_session.add(mock_transaction)
        await db_session.commit()
        
        with patch('modules.financial.api.webhook_endpoints.TransactionService') as mock_service:
            mock_service.return_value.get_transaction_by_external_ref = AsyncMock(
                return_value=mock_transaction
            )
            
            with patch('modules.financial.api.webhook_endpoints.send_notification') as mock_notify:
                mock_notify.return_value = AsyncMock()
                
                await handle_payment_expired(
                    db_session,
                    "bitpay",
                    {"id": "test_payment_123"}
                )
                
                assert mock_transaction.status == TransactionStatus.FAILED
                assert mock_transaction.metadata.get("failure_reason") == "Payment expired"
                
                mock_notify.assert_called_once()
                assert mock_notify.call_args[0][0] == "payment_expired"