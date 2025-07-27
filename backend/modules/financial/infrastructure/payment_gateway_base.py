"""
Base payment gateway abstraction.

Provides a common interface for all payment gateway implementations
with standard methods for processing payments, handling webhooks, etc.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from ..domain.models import CryptoPayment, CryptoPaymentStatus


class PaymentStatus(str, Enum):
    """Unified payment status across gateways."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"


@dataclass
class PaymentRequest:
    """Standard payment request data."""
    amount: Decimal
    currency: str
    description: str
    recipient_address: Optional[str] = None
    recipient_email: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    redirect_url: Optional[str] = None
    webhook_url: Optional[str] = None
    expires_minutes: Optional[int] = 60


@dataclass
class PaymentResponse:
    """Standard payment response data."""
    payment_id: str
    provider_payment_id: str
    status: PaymentStatus
    amount: Decimal
    currency: str
    payment_url: Optional[str] = None
    payment_address: Optional[str] = None
    qr_code_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WebhookData:
    """Webhook payload data."""
    event_type: str
    payment_id: str
    status: PaymentStatus
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    transaction_hash: Optional[str] = None
    confirmations: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentGatewayBase(ABC):
    """Abstract base class for payment gateways."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize gateway with configuration.
        
        Args:
            config: Gateway-specific configuration including API keys
        """
        self.config = config
        self.is_test_mode = config.get('is_test_mode', False)
        
    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a new payment request.
        
        Args:
            request: Payment request data
            
        Returns:
            Payment response with provider details
        """
        pass
        
    @abstractmethod
    async def get_payment_status(self, payment_id: str) -> PaymentResponse:
        """
        Get current status of a payment.
        
        Args:
            payment_id: Provider's payment ID
            
        Returns:
            Current payment details
        """
        pass
        
    @abstractmethod
    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancel a pending payment.
        
        Args:
            payment_id: Provider's payment ID
            
        Returns:
            Success status
        """
        pass
        
    @abstractmethod
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        webhook_secret: str
    ) -> bool:
        """
        Verify webhook signature.
        
        Args:
            headers: Request headers
            body: Raw request body
            webhook_secret: Webhook secret for verification
            
        Returns:
            True if webhook is valid
        """
        pass
        
    @abstractmethod
    async def parse_webhook(self, body: Dict[str, Any]) -> WebhookData:
        """
        Parse webhook data into standard format.
        
        Args:
            body: Parsed webhook body
            
        Returns:
            Standardized webhook data
        """
        pass
        
    @abstractmethod
    async def get_supported_currencies(self) -> List[str]:
        """
        Get list of supported currencies.
        
        Returns:
            List of currency codes
        """
        pass
        
    @abstractmethod
    async def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """
        Get current exchange rates.
        
        Args:
            base_currency: Base currency for rates
            
        Returns:
            Dictionary of currency -> rate
        """
        pass
        
    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> bool:
        """
        Refund a payment (if supported).
        
        Args:
            payment_id: Provider's payment ID
            amount: Amount to refund (None for full refund)
            reason: Refund reason
            
        Returns:
            Success status
        """
        # Default implementation - override if gateway supports refunds
        raise NotImplementedError(f"{self.__class__.__name__} does not support refunds")
        
    def map_status(self, provider_status: str) -> PaymentStatus:
        """
        Map provider-specific status to unified status.
        
        Args:
            provider_status: Provider's status string
            
        Returns:
            Unified payment status
        """
        # Default mapping - override in subclasses
        status_map = {
            'pending': PaymentStatus.PENDING,
            'processing': PaymentStatus.PROCESSING,
            'completed': PaymentStatus.COMPLETED,
            'confirmed': PaymentStatus.COMPLETED,
            'failed': PaymentStatus.FAILED,
            'cancelled': PaymentStatus.CANCELLED,
            'canceled': PaymentStatus.CANCELLED,
            'expired': PaymentStatus.EXPIRED,
            'refunded': PaymentStatus.REFUNDED
        }
        
        return status_map.get(provider_status.lower(), PaymentStatus.PENDING)
        
    def validate_config(self) -> bool:
        """
        Validate gateway configuration.
        
        Returns:
            True if configuration is valid
        """
        required_keys = self.get_required_config_keys()
        
        for key in required_keys:
            if key not in self.config or not self.config[key]:
                raise ValueError(f"Missing required configuration: {key}")
                
        return True
        
    @abstractmethod
    def get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys.
        
        Returns:
            List of required config keys
        """
        pass
        
    def format_amount(self, amount: Decimal, currency: str) -> str:
        """
        Format amount for display.
        
        Args:
            amount: Amount to format
            currency: Currency code
            
        Returns:
            Formatted amount string
        """
        # Handle crypto currencies with more decimals
        if currency in ['BTC', 'ETH']:
            return f"{amount:.8f}"
        elif currency in ['USD', 'EUR', 'GBP', 'USDT', 'USDC']:
            return f"{amount:.2f}"
        else:
            return str(amount)
            
    async def health_check(self) -> Dict[str, Any]:
        """
        Check gateway health/availability.
        
        Returns:
            Health status information
        """
        try:
            # Try to get exchange rates as a basic health check
            rates = await self.get_exchange_rates()
            return {
                'status': 'healthy',
                'provider': self.__class__.__name__,
                'test_mode': self.is_test_mode,
                'currencies_available': len(rates) > 0
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'provider': self.__class__.__name__,
                'error': str(e)
            }