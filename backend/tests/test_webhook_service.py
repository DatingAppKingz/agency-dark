"""Tests for webhook service."""

import pytest
import json
import hmac
import hashlib
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from services.webhook_service import WebhookService
from models.webhook import Webhook, WebhookStatus


class TestWebhookService:
    """Test webhook service functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=AsyncSession)
    
    @pytest.fixture
    def webhook_service(self, mock_db):
        """Create webhook service instance."""
        return WebhookService(mock_db)
    
    def test_verify_signature_sha256(self, webhook_service):
        """Test SHA256 signature verification."""
        payload = b'{"event": "test.webhook", "data": {"id": 123}}'
        secret = "webhook_secret_key"
        
        # Generate correct signature
        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Verify correct signature
        assert webhook_service.verify_signature(payload, expected_sig, secret) is True
        
        # Verify incorrect signature
        assert webhook_service.verify_signature(payload, "wrong_signature", secret) is False
    
    def test_verify_signature_sha1(self, webhook_service):
        """Test SHA1 signature verification (OnlyFans style)."""
        payload = b'{"type": "subscription.create", "data": {"user_id": "123"}}'
        secret = "onlyfans_secret"
        
        # Generate correct signature
        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha1
        ).hexdigest()
        
        # Verify correct signature
        assert webhook_service.verify_signature(payload, expected_sig, secret, "sha1") is True
    
    def test_verify_stripe_signature(self, webhook_service):
        """Test Stripe signature verification with timestamp."""
        payload = b'{"id": "evt_123", "type": "payment_intent.succeeded"}'
        secret = "whsec_test_secret"
        
        # Generate Stripe-style signature
        timestamp = int(datetime.utcnow().timestamp())
        signed_payload = f"{timestamp}.{payload.decode()}"
        signature = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        stripe_signature = f"t={timestamp},v1={signature}"
        
        # Verify correct signature
        assert webhook_service.verify_stripe_signature(
            payload, stripe_signature, secret
        ) is True
        
        # Test expired timestamp (> 5 minutes old)
        old_timestamp = timestamp - 400  # 6+ minutes ago
        old_signed_payload = f"{old_timestamp}.{payload.decode()}"
        old_signature = hmac.new(
            secret.encode(),
            old_signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        old_stripe_signature = f"t={old_timestamp},v1={old_signature}"
        
        # Should fail due to old timestamp
        assert webhook_service.verify_stripe_signature(
            payload, old_stripe_signature, secret
        ) is False
    
    def test_extract_event_type(self, webhook_service):
        """Test event type extraction for different providers."""
        # Stripe
        stripe_data = {"type": "payment_intent.succeeded", "data": {}}
        assert webhook_service._extract_event_type("stripe", stripe_data) == "payment_intent.succeeded"
        
        # OnlyFans
        of_data = {"type": "subscription.create", "data": {}}
        assert webhook_service._extract_event_type("onlyfans", of_data) == "subscription.create"
        
        # Inflow
        inflow_data = {"event": "subscriber.new", "data": {}}
        assert webhook_service._extract_event_type("inflow", inflow_data) == "subscriber.new"
        
        # Custom
        custom_data = {"event_type": "custom.event", "data": {}}
        assert webhook_service._extract_event_type("custom", custom_data) == "custom.event"
        
        # Unknown
        unknown_data = {"data": {}}
        assert webhook_service._extract_event_type("unknown", unknown_data) == "unknown"
    
    @pytest.mark.asyncio
    async def test_receive_webhook_with_signature_validation(self, webhook_service, mock_db):
        """Test receiving webhook with signature validation."""
        # Mock webhook config
        webhook = Mock(spec=Webhook)
        webhook.id = 1
        webhook.secret = "test_secret"
        webhook.url = "https://example.com/webhook"
        webhook.events = ["*"]
        webhook.headers = {}
        webhook.timeout_seconds = 30
        webhook.max_retries = 3
        webhook.total_calls = 0
        webhook.successful_calls = 0
        webhook.failed_calls = 0
        
        # Mock database queries
        mock_db.execute = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [webhook]
        mock_db.execute.return_value = mock_result
        mock_db.add = Mock()
        mock_db.commit = AsyncMock()
        
        # Prepare webhook payload
        payload_dict = {"event": "test.event", "data": {"id": 123}}
        payload = json.dumps(payload_dict).encode()
        
        # Generate correct signature
        signature = hmac.new(
            webhook.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-Webhook-Signature": signature,
            "Content-Type": "application/json"
        }
        
        # Mock is_subscribed_to to return True
        webhook.is_subscribed_to = Mock(return_value=True)
        
        # Test receive webhook
        result = await webhook_service.receive_webhook(
            provider="custom",
            headers=headers,
            body=payload
        )
        
        assert result["status"] == "received"
        assert result["provider"] == "custom"
        
        # Verify database was queried
        mock_db.execute.assert_called()
        
        # Verify delivery record was created
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_receive_webhook_invalid_signature(self, webhook_service, mock_db):
        """Test receiving webhook with invalid signature."""
        # Mock webhook config
        webhook = Mock(spec=Webhook)
        webhook.id = 1
        webhook.secret = "test_secret"
        webhook.events = ["*"]
        
        # Mock database queries
        mock_db.execute = AsyncMock()
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [webhook]
        mock_db.execute.return_value = mock_result
        
        # Prepare webhook payload
        payload = b'{"event": "test.event", "data": {"id": 123}}'
        
        headers = {
            "X-Webhook-Signature": "invalid_signature",
            "Content-Type": "application/json"
        }
        
        # Test should still return success (to prevent retry storms)
        result = await webhook_service.receive_webhook(
            provider="custom",
            headers=headers,
            body=payload
        )
        
        assert result["status"] == "received"
    
    def test_verify_signature_unsupported_algorithm(self, webhook_service):
        """Test signature verification with unsupported algorithm."""
        payload = b'{"test": "data"}'
        
        with pytest.raises(Exception) as exc_info:
            webhook_service.verify_signature(payload, "signature", "secret", "md5")
        
        assert "Unsupported algorithm" in str(exc_info.value)