"""
Payment gateway management service.

Coordinates payment operations across different gateways,
handles webhook processing, and manages gateway configurations.
"""
import logging
from typing import Dict, Any, Optional, List, Type
from datetime import datetime
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from modules.financial.infrastructure.payment_gateway_base import (
    PaymentGatewayBase,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus
)
from modules.financial.infrastructure.stripe_gateway import StripeGateway
from modules.financial.infrastructure.coinbase_gateway import CoinbaseCommerceGateway
from modules.financial.domain.models import (
    PaymentGatewayConfig,
    CryptoPayment,
    CryptoPaymentStatus,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    PaymentGatewayConfigCreate,
    PaymentGatewayConfigResponse,
    CryptoPaymentRequest,
    CryptoPaymentResponse
)
from core.domain.models import Agency


logger = logging.getLogger(__name__)


class PaymentGatewayService:
    """Manages payment gateways and payment processing."""
    
    # Registry of available gateway implementations
    GATEWAY_REGISTRY: Dict[str, Type[PaymentGatewayBase]] = {
        'stripe': StripeGateway,
        'coinbase_commerce': CoinbaseCommerceGateway
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._gateway_cache: Dict[str, PaymentGatewayBase] = {}
        
    async def create_gateway_config(
        self,
        config_data: PaymentGatewayConfigCreate
    ) -> PaymentGatewayConfigResponse:
        """
        Create a new payment gateway configuration.
        
        Args:
            config_data: Gateway configuration details
            
        Returns:
            Created configuration
        """
        # Verify gateway type is supported
        if config_data.gateway_type not in self.GATEWAY_REGISTRY:
            raise ValueError(f"Unsupported gateway type: {config_data.gateway_type}")
            
        # Verify agency exists if specified
        if config_data.agency_id:
            agency = await self.db.get(Agency, config_data.agency_id)
            if not agency:
                raise ValueError("Agency not found")
                
        # Check for duplicate active config
        existing = await self.db.execute(
            select(PaymentGatewayConfig).where(
                and_(
                    PaymentGatewayConfig.gateway_type == config_data.gateway_type,
                    PaymentGatewayConfig.agency_id == config_data.agency_id,
                    PaymentGatewayConfig.is_active == True
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Active {config_data.gateway_type} configuration already exists")
            
        # Create configuration
        config = PaymentGatewayConfig(
            gateway_type=config_data.gateway_type,
            agency_id=config_data.agency_id,
            config=config_data.config,
            is_active=config_data.is_active,
            is_test_mode=config_data.is_test_mode
        )
        
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(f"Created {config_data.gateway_type} gateway config for agency {config_data.agency_id}")
        
        return PaymentGatewayConfigResponse.model_validate(config)
        
    async def get_active_configs(
        self,
        agency_id: Optional[str] = None
    ) -> List[PaymentGatewayConfigResponse]:
        """Get active gateway configurations."""
        query = select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.is_active == True
        )
        
        if agency_id:
            query = query.where(
                or_(
                    PaymentGatewayConfig.agency_id == agency_id,
                    PaymentGatewayConfig.agency_id.is_(None)  # Global configs
                )
            )
            
        result = await self.db.execute(query)
        configs = result.scalars().all()
        
        return [PaymentGatewayConfigResponse.model_validate(c) for c in configs]
        
    async def get_gateway(
        self,
        gateway_type: str,
        agency_id: Optional[str] = None
    ) -> PaymentGatewayBase:
        """
        Get initialized gateway instance.
        
        Args:
            gateway_type: Type of gateway (stripe, coinbase_commerce)
            agency_id: Optional agency ID for agency-specific config
            
        Returns:
            Initialized gateway instance
        """
        cache_key = f"{gateway_type}:{agency_id or 'global'}"
        
        # Check cache
        if cache_key in self._gateway_cache:
            return self._gateway_cache[cache_key]
            
        # Get configuration
        query = select(PaymentGatewayConfig).where(
            and_(
                PaymentGatewayConfig.gateway_type == gateway_type,
                PaymentGatewayConfig.is_active == True
            )
        )
        
        if agency_id:
            # Try agency-specific first, then global
            query = query.where(
                or_(
                    PaymentGatewayConfig.agency_id == agency_id,
                    PaymentGatewayConfig.agency_id.is_(None)
                )
            ).order_by(PaymentGatewayConfig.agency_id.desc())  # Agency-specific first
        else:
            query = query.where(PaymentGatewayConfig.agency_id.is_(None))
            
        result = await self.db.execute(query.limit(1))
        config = result.scalar_one_or_none()
        
        if not config:
            raise ValueError(f"No active configuration found for {gateway_type}")
            
        # Get gateway class
        gateway_class = self.GATEWAY_REGISTRY.get(gateway_type)
        if not gateway_class:
            raise ValueError(f"Unknown gateway type: {gateway_type}")
            
        # Initialize gateway
        gateway_config = config.config.copy()
        gateway_config['is_test_mode'] = config.is_test_mode
        
        gateway = gateway_class(gateway_config)
        
        # Cache it
        self._gateway_cache[cache_key] = gateway
        
        return gateway
        
    async def create_payment(
        self,
        payment_request: CryptoPaymentRequest,
        provider: str,
        agency_id: Optional[str] = None
    ) -> CryptoPaymentResponse:
        """
        Create a payment using specified provider.
        
        Args:
            payment_request: Payment details
            provider: Payment provider (stripe, coinbase_commerce)
            agency_id: Optional agency ID
            
        Returns:
            Payment response with payment URL
        """
        # Get gateway
        gateway = await self.get_gateway(provider, agency_id)
        
        # Convert to gateway request
        gateway_request = PaymentRequest(
            amount=payment_request.amount,
            currency=payment_request.currency,
            description=payment_request.description,
            recipient_email=payment_request.customer_email,
            metadata={
                'model_id': payment_request.model_id,
                'fan_id': payment_request.fan_id,
                'agency_id': agency_id,
                'payment_type': payment_request.payment_type
            },
            redirect_url=payment_request.redirect_url,
            webhook_url=payment_request.webhook_url
        )
        
        # Create payment with gateway
        gateway_response = await gateway.create_payment(gateway_request)
        
        # Store payment record
        crypto_payment = CryptoPayment(
            provider=provider,
            provider_payment_id=gateway_response.provider_payment_id,
            amount=gateway_response.amount,
            currency=gateway_response.currency,
            status=self._map_to_crypto_status(gateway_response.status),
            payment_url=gateway_response.payment_url,
            expires_at=gateway_response.expires_at,
            metadata={
                **gateway_response.metadata,
                'gateway_payment_id': gateway_response.payment_id
            },
            model_id=payment_request.model_id,
            fan_id=payment_request.fan_id,
            created_at=datetime.utcnow()
        )
        
        self.db.add(crypto_payment)
        await self.db.commit()
        await self.db.refresh(crypto_payment)
        
        logger.info(f"Created {provider} payment: {crypto_payment.id}")
        
        return CryptoPaymentResponse(
            id=str(crypto_payment.id),
            provider=crypto_payment.provider,
            payment_url=crypto_payment.payment_url,
            amount=crypto_payment.amount,
            currency=crypto_payment.currency,
            status=crypto_payment.status,
            expires_at=crypto_payment.expires_at
        )
        
    async def get_payment_status(
        self,
        payment_id: str
    ) -> CryptoPaymentResponse:
        """Get current payment status."""
        # Get payment record
        payment = await self.db.get(CryptoPayment, payment_id)
        if not payment:
            raise ValueError("Payment not found")
            
        # Get gateway
        gateway = await self.get_gateway(payment.provider)
        
        # Get status from gateway
        gateway_payment_id = payment.metadata.get('gateway_payment_id')
        if not gateway_payment_id:
            raise ValueError("Gateway payment ID not found")
            
        gateway_response = await gateway.get_payment_status(gateway_payment_id)
        
        # Update payment record
        payment.status = self._map_to_crypto_status(gateway_response.status)
        
        # Update transaction hash if completed
        if gateway_response.metadata.get('transaction_hash'):
            payment.transaction_hash = gateway_response.metadata['transaction_hash']
            
        await self.db.commit()
        await self.db.refresh(payment)
        
        return CryptoPaymentResponse(
            id=str(payment.id),
            provider=payment.provider,
            payment_url=payment.payment_url,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            expires_at=payment.expires_at,
            transaction_hash=payment.transaction_hash
        )
        
    async def process_webhook(
        self,
        provider: str,
        headers: Dict[str, str],
        body: bytes
    ) -> Dict[str, Any]:
        """
        Process payment webhook from provider.
        
        Args:
            provider: Payment provider
            headers: Request headers
            body: Raw request body
            
        Returns:
            Processing result
        """
        try:
            # Get gateway config to get webhook secret
            result = await self.db.execute(
                select(PaymentGatewayConfig).where(
                    and_(
                        PaymentGatewayConfig.gateway_type == provider,
                        PaymentGatewayConfig.is_active == True
                    )
                ).limit(1)
            )
            config = result.scalar_one_or_none()
            
            if not config:
                logger.error(f"No active configuration for {provider}")
                return {'success': False, 'error': 'Configuration not found'}
                
            webhook_secret = config.config.get('webhook_secret')
            if not webhook_secret:
                logger.error(f"No webhook secret configured for {provider}")
                return {'success': False, 'error': 'Webhook secret not configured'}
                
            # Get gateway
            gateway = await self.get_gateway(provider)
            
            # Verify webhook
            if not await gateway.verify_webhook(headers, body, webhook_secret):
                logger.warning(f"Invalid webhook signature for {provider}")
                return {'success': False, 'error': 'Invalid signature'}
                
            # Parse webhook data
            webhook_data = await gateway.parse_webhook(json.loads(body))
            
            # Find payment by provider payment ID
            result = await self.db.execute(
                select(CryptoPayment).where(
                    CryptoPayment.metadata['gateway_payment_id'].astext == webhook_data.payment_id
                )
            )
            payment = result.scalar_one_or_none()
            
            if not payment:
                logger.warning(f"Payment not found for webhook: {webhook_data.payment_id}")
                return {'success': False, 'error': 'Payment not found'}
                
            # Update payment status
            old_status = payment.status
            payment.status = self._map_to_crypto_status(webhook_data.status)
            
            if webhook_data.transaction_hash:
                payment.transaction_hash = webhook_data.transaction_hash
                
            if webhook_data.confirmations:
                payment.confirmations = webhook_data.confirmations
                
            # Create transaction if payment completed
            if (old_status != CryptoPaymentStatus.COMPLETED and 
                payment.status == CryptoPaymentStatus.COMPLETED):
                
                transaction = FinancialTransaction(
                    agency_id=payment.metadata.get('agency_id'),
                    model_id=payment.model_id,
                    fan_id=payment.fan_id,
                    type=TransactionType.REVENUE,
                    amount=payment.amount,
                    crypto_payment_id=payment.id,
                    description=f"Crypto payment via {provider}",
                    metadata={
                        'provider': provider,
                        'transaction_hash': payment.transaction_hash,
                        'currency': payment.currency
                    },
                    transaction_date=datetime.utcnow()
                )
                
                self.db.add(transaction)
                logger.info(f"Created transaction for completed payment: {payment.id}")
                
            await self.db.commit()
            
            logger.info(f"Processed webhook for payment {payment.id}: {old_status} -> {payment.status}")
            
            return {'success': True, 'payment_id': str(payment.id)}
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return {'success': False, 'error': str(e)}
            
    async def cancel_payment(
        self,
        payment_id: str
    ) -> bool:
        """
        Cancel a pending payment.
        
        Args:
            payment_id: Payment ID to cancel
            
        Returns:
            Success status
        """
        payment = await self.db.get(CryptoPayment, payment_id)
        if not payment:
            raise ValueError("Payment not found")
            
        if payment.status != CryptoPaymentStatus.PENDING:
            raise ValueError(f"Cannot cancel payment in {payment.status} status")
            
        # Get gateway
        gateway = await self.get_gateway(payment.provider)
        
        # Cancel with gateway
        gateway_payment_id = payment.metadata.get('gateway_payment_id')
        if gateway_payment_id:
            success = await gateway.cancel_payment(gateway_payment_id)
            
            if success:
                payment.status = CryptoPaymentStatus.CANCELLED
                await self.db.commit()
                logger.info(f"Cancelled payment: {payment_id}")
                
            return success
            
        return False
        
    async def get_supported_currencies(
        self,
        provider: str
    ) -> List[str]:
        """Get supported currencies for a provider."""
        gateway = await self.get_gateway(provider)
        return await gateway.get_supported_currencies()
        
    async def get_exchange_rates(
        self,
        provider: str,
        base_currency: str = "USD"
    ) -> Dict[str, float]:
        """Get current exchange rates."""
        gateway = await self.get_gateway(provider)
        rates = await gateway.get_exchange_rates(base_currency)
        
        # Convert Decimal to float for JSON serialization
        return {currency: float(rate) for currency, rate in rates.items()}
        
    def _map_to_crypto_status(self, gateway_status: PaymentStatus) -> CryptoPaymentStatus:
        """Map gateway status to crypto payment status."""
        status_map = {
            PaymentStatus.PENDING: CryptoPaymentStatus.PENDING,
            PaymentStatus.PROCESSING: CryptoPaymentStatus.PENDING,
            PaymentStatus.COMPLETED: CryptoPaymentStatus.COMPLETED,
            PaymentStatus.FAILED: CryptoPaymentStatus.FAILED,
            PaymentStatus.CANCELLED: CryptoPaymentStatus.CANCELLED,
            PaymentStatus.EXPIRED: CryptoPaymentStatus.EXPIRED,
            PaymentStatus.REFUNDED: CryptoPaymentStatus.REFUNDED
        }
        
        return status_map.get(gateway_status, CryptoPaymentStatus.PENDING)
        
    async def test_gateway_connection(
        self,
        gateway_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Test gateway configuration.
        
        Args:
            gateway_type: Type of gateway
            config: Configuration to test
            
        Returns:
            Test results
        """
        try:
            # Get gateway class
            gateway_class = self.GATEWAY_REGISTRY.get(gateway_type)
            if not gateway_class:
                return {
                    'success': False,
                    'error': f"Unknown gateway type: {gateway_type}"
                }
                
            # Initialize gateway
            gateway = gateway_class(config)
            
            # Test health check
            health = await gateway.health_check()
            
            return {
                'success': health.get('status') == 'healthy',
                'details': health
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }