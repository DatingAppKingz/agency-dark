"""
Payment gateway integration service for multiple providers.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from abc import ABC, abstractmethod
import hmac
import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from modules.financial.domain.models import (
    PaymentGatewayConfig,
    CryptoPayment,
    CryptoPaymentStatus,
    Payout,
    PayoutStatus,
    BillingCycle
)
from modules.financial.domain.schemas import (
    PaymentGatewayConfigCreate,
    PaymentGatewayConfigResponse,
    CryptoPaymentRequest,
    CryptoPaymentResponse
)
from core.domain.models import Agency


logger = logging.getLogger(__name__)


class PaymentProvider(ABC):
    """Abstract base class for payment providers."""
    
    @abstractmethod
    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a payment request."""
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify webhook signature."""
        pass
    
    @abstractmethod
    async def process_webhook(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process webhook data."""
        pass
    
    @abstractmethod
    async def get_payment_status(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """Get payment status."""
        pass


class CoinbaseCommerceProvider(PaymentProvider):
    """Coinbase Commerce payment provider."""
    
    def __init__(self, config: PaymentGatewayConfig):
        self.config = config
        self.api_key = config.api_key
        self.webhook_secret = config.webhook_secret
        self.base_url = "https://api.commerce.coinbase.com"
        
    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a Coinbase Commerce charge."""
        import aiohttp
        
        headers = {
            "X-CC-Api-Key": self.api_key,
            "X-CC-Version": "2018-03-22",
            "Content-Type": "application/json"
        }
        
        data = {
            "name": description,
            "description": description,
            "pricing_type": "fixed_price",
            "local_price": {
                "amount": str(amount),
                "currency": currency.upper()
            },
            "metadata": metadata
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/charges",
                headers=headers,
                json=data
            ) as response:
                if response.status != 201:
                    error = await response.text()
                    raise Exception(f"Coinbase Commerce error: {error}")
                
                result = await response.json()
                return {
                    "payment_id": result["data"]["id"],
                    "payment_url": result["data"]["hosted_url"],
                    "expires_at": result["data"]["expires_at"],
                    "addresses": result["data"]["addresses"],
                    "pricing": result["data"]["pricing"]
                }
    
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify Coinbase Commerce webhook signature."""
        signature = headers.get("X-CC-Webhook-Signature", "")
        
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def process_webhook(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process Coinbase Commerce webhook."""
        event_type = data.get("event", {}).get("type")
        charge_data = data.get("event", {}).get("data", {})
        
        status_mapping = {
            "charge:created": CryptoPaymentStatus.PENDING,
            "charge:confirmed": CryptoPaymentStatus.CONFIRMED,
            "charge:failed": CryptoPaymentStatus.FAILED,
            "charge:delayed": CryptoPaymentStatus.PENDING,
            "charge:resolved": CryptoPaymentStatus.COMPLETED
        }
        
        return {
            "payment_id": charge_data.get("id"),
            "status": status_mapping.get(event_type, CryptoPaymentStatus.PENDING),
            "transaction_hash": charge_data.get("payments", [{}])[0].get("transaction_id"),
            "amount_paid": charge_data.get("payments", [{}])[0].get("value", {}).get("local", {}).get("amount"),
            "metadata": charge_data.get("metadata", {})
        }
    
    async def get_payment_status(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """Get Coinbase Commerce charge status."""
        import aiohttp
        
        headers = {
            "X-CC-Api-Key": self.api_key,
            "X-CC-Version": "2018-03-22"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/charges/{payment_id}",
                headers=headers
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"Coinbase Commerce error: {error}")
                
                result = await response.json()
                charge = result["data"]
                
                # Map timeline events to our status
                timeline = charge.get("timeline", [])
                latest_status = timeline[-1]["status"] if timeline else "NEW"
                
                status_mapping = {
                    "NEW": CryptoPaymentStatus.PENDING,
                    "PENDING": CryptoPaymentStatus.PENDING,
                    "COMPLETED": CryptoPaymentStatus.COMPLETED,
                    "EXPIRED": CryptoPaymentStatus.EXPIRED,
                    "UNRESOLVED": CryptoPaymentStatus.FAILED,
                    "RESOLVED": CryptoPaymentStatus.COMPLETED,
                    "CANCELED": CryptoPaymentStatus.FAILED
                }
                
                return {
                    "status": status_mapping.get(latest_status, CryptoPaymentStatus.PENDING),
                    "amount_paid": charge.get("payments", [{}])[0].get("value", {}).get("local", {}).get("amount"),
                    "transaction_hash": charge.get("payments", [{}])[0].get("transaction_id")
                }


class BitPayProvider(PaymentProvider):
    """BitPay payment provider."""
    
    def __init__(self, config: PaymentGatewayConfig):
        self.config = config
        self.api_key = config.api_key
        self.base_url = "https://bitpay.com/api" if not config.is_test_mode else "https://test.bitpay.com/api"
        
    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a BitPay invoice."""
        import aiohttp
        
        headers = {
            "X-BitPay-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "price": float(amount),
            "currency": currency.upper(),
            "itemDesc": description,
            "notificationURL": metadata.get("webhook_url"),
            "redirectURL": metadata.get("redirect_url"),
            "posData": json.dumps(metadata)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/invoice",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"BitPay error: {error}")
                
                result = await response.json()
                return {
                    "payment_id": result["data"]["id"],
                    "payment_url": result["data"]["url"],
                    "expires_at": result["data"]["expirationTime"],
                    "addresses": {
                        currency: result["data"]["bitcoinAddress"]
                        for currency in result["data"]["supportedTransactionCurrencies"]
                    }
                }
    
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify BitPay webhook signature."""
        # BitPay uses a different verification method
        # This is a simplified version
        return True  # Implement proper verification
    
    async def process_webhook(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process BitPay webhook."""
        status = data.get("status")
        
        status_mapping = {
            "new": CryptoPaymentStatus.PENDING,
            "paid": CryptoPaymentStatus.PENDING,
            "confirmed": CryptoPaymentStatus.CONFIRMED,
            "complete": CryptoPaymentStatus.COMPLETED,
            "expired": CryptoPaymentStatus.EXPIRED,
            "invalid": CryptoPaymentStatus.FAILED
        }
        
        pos_data = json.loads(data.get("posData", "{}"))
        
        return {
            "payment_id": data.get("id"),
            "status": status_mapping.get(status, CryptoPaymentStatus.PENDING),
            "transaction_hash": data.get("transactionId"),
            "amount_paid": data.get("amountPaid"),
            "metadata": pos_data
        }
    
    async def get_payment_status(
        self,
        payment_id: str
    ) -> Dict[str, Any]:
        """Get BitPay invoice status."""
        import aiohttp
        
        headers = {
            "X-BitPay-Token": self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/invoice/{payment_id}",
                headers=headers
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"BitPay error: {error}")
                
                result = await response.json()
                invoice = result["data"]
                
                status_mapping = {
                    "new": CryptoPaymentStatus.PENDING,
                    "paid": CryptoPaymentStatus.PENDING,
                    "confirmed": CryptoPaymentStatus.CONFIRMED,
                    "complete": CryptoPaymentStatus.COMPLETED,
                    "expired": CryptoPaymentStatus.EXPIRED,
                    "invalid": CryptoPaymentStatus.FAILED
                }
                
                return {
                    "status": status_mapping.get(invoice["status"], CryptoPaymentStatus.PENDING),
                    "amount_paid": invoice.get("amountPaid"),
                    "transaction_hash": invoice.get("transactionId")
                }


class PaymentGatewayService:
    """Manages payment gateway integrations."""
    
    SUPPORTED_PROVIDERS = {
        "coinbase_commerce": CoinbaseCommerceProvider,
        "bitpay": BitPayProvider
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._providers: Dict[str, PaymentProvider] = {}
    
    async def create_gateway_config(
        self,
        config_data: PaymentGatewayConfigCreate,
        agency_id: Optional[str] = None
    ) -> PaymentGatewayConfigResponse:
        """Create payment gateway configuration."""
        if config_data.provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {config_data.provider}")
        
        # Check for existing config
        existing = await self.db.execute(
            select(PaymentGatewayConfig).where(
                and_(
                    PaymentGatewayConfig.provider == config_data.provider,
                    PaymentGatewayConfig.agency_id == agency_id,
                    PaymentGatewayConfig.is_active == True
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise ValueError(f"Active {config_data.provider} configuration already exists")
        
        # Create config
        config = PaymentGatewayConfig(
            agency_id=agency_id,
            provider=config_data.provider,
            api_key=config_data.api_key,
            api_secret=config_data.api_secret,
            webhook_secret=config_data.webhook_secret,
            merchant_id=config_data.merchant_id,
            is_test_mode=config_data.is_test_mode,
            supported_currencies=config_data.supported_currencies,
            config=config_data.config,
            is_active=True
        )
        
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(f"Payment gateway config created for {config_data.provider}")
        
        return PaymentGatewayConfigResponse.model_validate(config)
    
    async def get_provider(
        self,
        provider_name: str,
        agency_id: Optional[str] = None
    ) -> PaymentProvider:
        """Get payment provider instance."""
        cache_key = f"{provider_name}:{agency_id or 'global'}"
        
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # Get config from database
        result = await self.db.execute(
            select(PaymentGatewayConfig).where(
                and_(
                    PaymentGatewayConfig.provider == provider_name,
                    PaymentGatewayConfig.agency_id == agency_id,
                    PaymentGatewayConfig.is_active == True
                )
            )
        )
        
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError(f"No active configuration for {provider_name}")
        
        # Create provider instance
        provider_class = self.SUPPORTED_PROVIDERS[provider_name]
        provider = provider_class(config)
        
        # Cache it
        self._providers[cache_key] = provider
        
        return provider
    
    async def create_payment(
        self,
        payment_request: CryptoPaymentRequest,
        provider_name: str,
        agency_id: Optional[str] = None
    ) -> CryptoPaymentResponse:
        """Create a payment with specified provider."""
        provider = await self.get_provider(provider_name, agency_id)
        
        # Create payment with provider
        result = await provider.create_payment(
            amount=payment_request.amount,
            currency=payment_request.currency,
            description=payment_request.description,
            metadata=payment_request.metadata
        )
        
        # Store payment record
        payment = CryptoPayment(
            provider=provider_name,
            payment_id=result["payment_id"],
            amount=payment_request.amount,
            currency=payment_request.currency,
            recipient_wallet_id=payment_request.recipient_wallet_id,
            payment_url=result.get("payment_url"),
            expires_at=datetime.fromisoformat(result["expires_at"]) if result.get("expires_at") else None,
            addresses=result.get("addresses", {}),
            metadata=payment_request.metadata,
            status=CryptoPaymentStatus.PENDING
        )
        
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        
        return CryptoPaymentResponse(
            payment_id=payment.payment_id,
            amount=payment.amount,
            currency=payment.currency,
            network=None,  # Will be determined by actual payment
            recipient_address=None,  # Will be set from addresses
            status=payment.status.value,
            transaction_hash=None,
            expires_at=payment.expires_at,
            payment_url=payment.payment_url
        )
    
    async def process_webhook(
        self,
        provider_name: str,
        headers: Dict[str, str],
        body: bytes
    ) -> Dict[str, Any]:
        """Process payment webhook from provider."""
        provider = await self.get_provider(provider_name)
        
        # Verify webhook signature
        if not await provider.verify_webhook(headers, body):
            raise ValueError("Invalid webhook signature")
        
        # Parse webhook data
        data = json.loads(body)
        
        # Process webhook
        result = await provider.process_webhook(data)
        
        # Update payment record
        payment = await self.db.execute(
            select(CryptoPayment).where(
                CryptoPayment.payment_id == result["payment_id"]
            )
        )
        payment = payment.scalar_one_or_none()
        
        if payment:
            payment.status = result["status"]
            payment.transaction_hash = result.get("transaction_hash")
            payment.confirmed_at = datetime.utcnow() if result["status"] == CryptoPaymentStatus.CONFIRMED else None
            payment.completed_at = datetime.utcnow() if result["status"] == CryptoPaymentStatus.COMPLETED else None
            
            # Update associated payout if exists
            if payment.metadata and payment.metadata.get("payout_id"):
                payout = await self.db.get(Payout, payment.metadata["payout_id"])
                if payout:
                    if result["status"] == CryptoPaymentStatus.COMPLETED:
                        payout.status = PayoutStatus.COMPLETED
                        payout.completed_at = datetime.utcnow()
                        payout.transaction_hash = result.get("transaction_hash")
                    elif result["status"] == CryptoPaymentStatus.FAILED:
                        payout.status = PayoutStatus.FAILED
                        payout.failure_reason = "Payment failed"
            
            await self.db.commit()
        
        return {
            "success": True,
            "payment_id": result["payment_id"],
            "status": result["status"].value if hasattr(result["status"], "value") else result["status"]
        }
    
    async def check_payment_status(
        self,
        payment_id: str
    ) -> CryptoPaymentStatus:
        """Check payment status with provider."""
        # Get payment record
        result = await self.db.execute(
            select(CryptoPayment).where(
                CryptoPayment.payment_id == payment_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise ValueError("Payment not found")
        
        # Get provider
        provider = await self.get_provider(payment.provider)
        
        # Check status
        status_result = await provider.get_payment_status(payment_id)
        
        # Update payment record
        payment.status = status_result["status"]
        if status_result.get("transaction_hash"):
            payment.transaction_hash = status_result["transaction_hash"]
        
        await self.db.commit()
        
        return payment.status
    
    async def get_active_configs(
        self,
        agency_id: Optional[str] = None
    ) -> List[PaymentGatewayConfigResponse]:
        """Get active payment gateway configurations."""
        query = select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.is_active == True
        )
        
        if agency_id:
            query = query.where(PaymentGatewayConfig.agency_id == agency_id)
        
        result = await self.db.execute(query)
        configs = result.scalars().all()
        
        return [PaymentGatewayConfigResponse.model_validate(c) for c in configs]