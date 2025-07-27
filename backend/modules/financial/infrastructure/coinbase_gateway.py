"""
Coinbase Commerce payment gateway implementation.

Handles crypto payments through Coinbase Commerce, supporting
Bitcoin, Ethereum, USDC, and other cryptocurrencies.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import hmac
import hashlib
import json

import httpx
from fastapi import HTTPException

from .payment_gateway_base import (
    PaymentGatewayBase,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    WebhookData
)


logger = logging.getLogger(__name__)


class CoinbaseCommerceGateway(PaymentGatewayBase):
    """Coinbase Commerce payment gateway implementation."""
    
    BASE_URL = "https://api.commerce.coinbase.com"
    TEST_BASE_URL = "https://api.commerce.coinbase.com"  # Same for test
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Coinbase Commerce gateway."""
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.webhook_secret = config.get('webhook_secret')
        self.base_url = self.TEST_BASE_URL if self.is_test_mode else self.BASE_URL
        
        # Validate configuration
        self.validate_config()
        
    def get_required_config_keys(self) -> List[str]:
        """Get required configuration keys."""
        return ['api_key', 'webhook_secret']
        
    async def create_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Create a Coinbase Commerce charge.
        
        Supports crypto payments in BTC, ETH, USDC, etc.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Create charge request
                charge_data = {
                    'name': request.description,
                    'description': request.description,
                    'pricing_type': 'fixed_price',
                    'local_price': {
                        'amount': str(request.amount),
                        'currency': request.currency.upper()
                    },
                    'metadata': request.metadata or {}
                }
                
                # Add redirect URL if provided
                if request.redirect_url:
                    charge_data['redirect_url'] = request.redirect_url
                    charge_data['cancel_url'] = request.redirect_url
                    
                response = await client.post(
                    f"{self.base_url}/charges",
                    headers=self._get_headers(),
                    json=charge_data
                )
                
                if response.status_code != 201:
                    raise Exception(f"Coinbase API error: {response.text}")
                    
                data = response.json()['data']
                
                return PaymentResponse(
                    payment_id=data['id'],
                    provider_payment_id=data['code'],
                    status=self.map_status(data['timeline'][-1]['status']),
                    amount=request.amount,
                    currency=request.currency,
                    payment_url=data['hosted_url'],
                    expires_at=datetime.utcnow() + timedelta(minutes=request.expires_minutes or 60),
                    metadata=request.metadata
                )
                
            except Exception as e:
                logger.error(f"Coinbase payment creation failed: {e}")
                raise
                
    async def get_payment_status(self, payment_id: str) -> PaymentResponse:
        """Get current status of a Coinbase Commerce charge."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/charges/{payment_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    raise Exception(f"Payment not found: {payment_id}")
                    
                data = response.json()['data']
                
                # Get latest status from timeline
                latest_status = data['timeline'][-1]['status'] if data['timeline'] else 'NEW'
                
                # Extract payment details
                local_price = data.get('pricing', {}).get('local', {})
                amount = Decimal(local_price.get('amount', '0'))
                currency = local_price.get('currency', 'USD')
                
                # Get crypto payment info if available
                payment_info = {}
                if data.get('payments'):
                    # Get first confirmed payment
                    for payment in data['payments']:
                        if payment['status'] == 'CONFIRMED':
                            payment_info['transaction_hash'] = payment.get('transaction_id')
                            payment_info['crypto_amount'] = payment['value']['local']['amount']
                            payment_info['crypto_currency'] = payment['value']['local']['currency']
                            break
                
                response = PaymentResponse(
                    payment_id=data['id'],
                    provider_payment_id=data['code'],
                    status=self.map_status(latest_status),
                    amount=amount,
                    currency=currency,
                    payment_url=data['hosted_url'],
                    expires_at=datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00')),
                    metadata={**data.get('metadata', {}), **payment_info}
                )
                
                return response
                
            except Exception as e:
                logger.error(f"Failed to get Coinbase payment status: {e}")
                raise
                
    async def cancel_payment(self, payment_id: str) -> bool:
        """
        Cancel a Coinbase Commerce charge.
        
        Note: Charges can only be cancelled if no payment has been detected.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/charges/{payment_id}/cancel",
                    headers=self._get_headers()
                )
                
                return response.status_code == 200
                
            except Exception as e:
                logger.error(f"Failed to cancel Coinbase payment: {e}")
                return False
                
    async def verify_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        webhook_secret: str
    ) -> bool:
        """Verify Coinbase Commerce webhook signature."""
        signature = headers.get('x-cc-webhook-signature')
        if not signature:
            return False
            
        try:
            # Compute expected signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return False
            
    async def parse_webhook(self, body: Dict[str, Any]) -> WebhookData:
        """Parse Coinbase Commerce webhook data."""
        event_type = body.get('event', {}).get('type', '')
        data = body.get('event', {}).get('data', {})
        
        # Map Coinbase events to our event types
        event_map = {
            'charge:created': 'payment.created',
            'charge:confirmed': 'payment.completed',
            'charge:failed': 'payment.failed',
            'charge:delayed': 'payment.processing',
            'charge:pending': 'payment.pending',
            'charge:resolved': 'payment.completed',
            'charge:unresolved': 'payment.failed'
        }
        
        # Get latest status from timeline
        latest_status = data['timeline'][-1]['status'] if data.get('timeline') else 'NEW'
        
        # Extract payment details
        local_price = data.get('pricing', {}).get('local', {})
        amount = Decimal(local_price.get('amount', '0'))
        currency = local_price.get('currency', 'USD')
        
        # Get transaction details if payment confirmed
        transaction_hash = None
        confirmations = 0
        
        if data.get('payments'):
            for payment in data['payments']:
                if payment['status'] == 'CONFIRMED':
                    transaction_hash = payment.get('transaction_id')
                    confirmations = payment.get('confirmations', 0)
                    break
        
        return WebhookData(
            event_type=event_map.get(event_type, event_type),
            payment_id=data['id'],
            status=self.map_status(latest_status),
            amount=amount,
            currency=currency,
            transaction_hash=transaction_hash,
            confirmations=confirmations,
            metadata=data.get('metadata', {})
        )
        
    async def get_supported_currencies(self) -> List[str]:
        """Get Coinbase Commerce supported currencies."""
        # Fiat currencies for pricing
        fiat = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY']
        
        # Cryptocurrencies for payment
        crypto = ['BTC', 'ETH', 'USDC', 'DAI', 'DOGE', 'LTC', 'BCH']
        
        return fiat + crypto
        
    async def get_exchange_rates(self, base_currency: str = "USD") -> Dict[str, Decimal]:
        """
        Get exchange rates from Coinbase.
        
        Uses Coinbase public API for exchange rates.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.coinbase.com/v2/exchange-rates?currency={base_currency}"
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to get exchange rates: {response.text}")
                    
                data = response.json()['data']['rates']
                
                # Convert to Decimal and filter relevant currencies
                rates = {}
                relevant_currencies = await self.get_supported_currencies()
                
                for currency in relevant_currencies:
                    if currency in data:
                        rates[currency] = Decimal(data[currency])
                        
                return rates
                
            except Exception as e:
                logger.error(f"Failed to get exchange rates: {e}")
                # Return some default rates
                return {
                    'USD': Decimal('1.00'),
                    'EUR': Decimal('0.85'),
                    'BTC': Decimal('0.00002'),
                    'ETH': Decimal('0.0003')
                }
                
    def map_status(self, coinbase_status: str) -> PaymentStatus:
        """Map Coinbase status to unified status."""
        status_map = {
            'NEW': PaymentStatus.PENDING,
            'PENDING': PaymentStatus.PENDING,
            'CONFIRMED': PaymentStatus.COMPLETED,
            'UNRESOLVED': PaymentStatus.FAILED,
            'RESOLVED': PaymentStatus.COMPLETED,
            'EXPIRED': PaymentStatus.EXPIRED,
            'CANCELED': PaymentStatus.CANCELLED,
            'COMPLETED': PaymentStatus.COMPLETED,
            'FAILED': PaymentStatus.FAILED
        }
        
        return status_map.get(coinbase_status.upper(), PaymentStatus.PENDING)
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Coinbase Commerce API requests."""
        return {
            'X-CC-Api-Key': self.api_key,
            'X-CC-Version': '2018-03-22',
            'Content-Type': 'application/json'
        }
        
    async def get_payment_addresses(
        self,
        payment_id: str
    ) -> Dict[str, str]:
        """
        Get cryptocurrency payment addresses for a charge.
        
        Returns addresses for each supported cryptocurrency.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/charges/{payment_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    raise Exception(f"Payment not found: {payment_id}")
                    
                data = response.json()['data']
                addresses = data.get('addresses', {})
                
                return addresses
                
            except Exception as e:
                logger.error(f"Failed to get payment addresses: {e}")
                raise
                
    async def estimate_crypto_amount(
        self,
        fiat_amount: Decimal,
        fiat_currency: str,
        crypto_currency: str
    ) -> Dict[str, Any]:
        """
        Estimate cryptocurrency amount for fiat value.
        
        Useful for showing users how much crypto they need to pay.
        """
        rates = await self.get_exchange_rates(fiat_currency)
        
        if crypto_currency not in rates:
            raise ValueError(f"Unsupported cryptocurrency: {crypto_currency}")
            
        crypto_amount = fiat_amount * rates[crypto_currency]
        
        # Format based on currency
        if crypto_currency in ['BTC', 'ETH', 'LTC', 'BCH']:
            formatted = f"{crypto_amount:.8f}"
        else:
            formatted = f"{crypto_amount:.2f}"
            
        return {
            'amount': crypto_amount,
            'formatted': formatted,
            'currency': crypto_currency,
            'exchange_rate': rates[crypto_currency]
        }