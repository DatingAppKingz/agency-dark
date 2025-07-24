"""
Cryptocurrency payment service for handling crypto transactions.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from modules.financial.domain.models import (
    CryptoWallet,
    CryptoNetwork,
    PaymentGatewayConfig,
    Payout,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    CryptoWalletCreate,
    CryptoWalletResponse,
    CryptoWalletVerification,
    CryptoPaymentRequest,
    CryptoPaymentResponse
)
from core.domain.models import User
from core.config import settings


logger = logging.getLogger(__name__)


class CryptoService:
    """Handles cryptocurrency payments and wallet management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._gateway_clients = {}
    
    async def create_wallet(
        self,
        user: User,
        wallet_data: CryptoWalletCreate
    ) -> CryptoWalletResponse:
        """
        Create a new crypto wallet for a user.
        
        Args:
            user: User creating the wallet
            wallet_data: Wallet details
            
        Returns:
            Created wallet
        """
        # Check if user already has a wallet for this network
        existing = await self.db.execute(
            select(CryptoWallet).where(
                and_(
                    CryptoWallet.user_id == user.id,
                    CryptoWallet.network == wallet_data.network,
                    CryptoWallet.address == wallet_data.address
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Wallet already exists for this network and address")
        
        # If setting as default, unset other defaults
        if wallet_data.is_default:
            await self.db.execute(
                select(CryptoWallet).where(
                    and_(
                        CryptoWallet.user_id == user.id,
                        CryptoWallet.network == wallet_data.network,
                        CryptoWallet.is_default == True
                    )
                ).update({"is_default": False})
            )
        
        # Create wallet
        wallet = CryptoWallet(
            user_id=user.id,
            network=wallet_data.network,
            address=wallet_data.address,
            label=wallet_data.label,
            is_default=wallet_data.is_default
        )
        
        self.db.add(wallet)
        await self.db.commit()
        await self.db.refresh(wallet)
        
        logger.info(f"Created {wallet_data.network} wallet for user {user.id}")
        
        return CryptoWalletResponse.model_validate(wallet)
    
    async def verify_wallet(
        self,
        wallet_id: str,
        user: User,
        verification: CryptoWalletVerification
    ) -> CryptoWalletResponse:
        """
        Verify ownership of a crypto wallet.
        
        Args:
            wallet_id: Wallet ID
            user: User verifying the wallet
            verification: Verification details
            
        Returns:
            Updated wallet
        """
        wallet = await self.db.get(CryptoWallet, wallet_id)
        if not wallet or wallet.user_id != user.id:
            raise ValueError("Wallet not found")
        
        if wallet.is_verified:
            raise ValueError("Wallet is already verified")
        
        # In production, this would verify the signature against the address
        # For MVP, we'll do a simple verification
        expected_message = f"Verify wallet ownership for AgencyDark: {wallet.address}"
        
        # TODO: Implement proper signature verification for each network
        # For now, just check if signature is provided
        if not verification.signature:
            raise ValueError("Invalid signature")
        
        # Mark as verified
        wallet.is_verified = True
        wallet.verified_at = datetime.utcnow()
        wallet.verification_signature = verification.signature
        
        await self.db.commit()
        await self.db.refresh(wallet)
        
        logger.info(f"Verified wallet {wallet_id} for user {user.id}")
        
        return CryptoWalletResponse.model_validate(wallet)
    
    async def get_user_wallets(
        self,
        user: User,
        network: Optional[CryptoNetwork] = None,
        active_only: bool = True
    ) -> List[CryptoWalletResponse]:
        """Get user's crypto wallets."""
        query = select(CryptoWallet).where(CryptoWallet.user_id == user.id)
        
        if network:
            query = query.where(CryptoWallet.network == network)
        
        if active_only:
            query = query.where(CryptoWallet.is_active == True)
        
        query = query.order_by(CryptoWallet.is_default.desc(), CryptoWallet.created_at.desc())
        
        result = await self.db.execute(query)
        wallets = result.scalars().all()
        
        return [CryptoWalletResponse.model_validate(wallet) for wallet in wallets]
    
    async def update_wallet(
        self,
        wallet_id: str,
        user: User,
        updates: Dict[str, Any]
    ) -> CryptoWalletResponse:
        """Update wallet settings."""
        wallet = await self.db.get(CryptoWallet, wallet_id)
        if not wallet or wallet.user_id != user.id:
            raise ValueError("Wallet not found")
        
        # Update allowed fields
        if 'label' in updates:
            wallet.label = updates['label']
        
        if 'is_active' in updates:
            wallet.is_active = updates['is_active']
        
        if 'is_default' in updates and updates['is_default']:
            # Unset other defaults
            await self.db.execute(
                select(CryptoWallet).where(
                    and_(
                        CryptoWallet.user_id == user.id,
                        CryptoWallet.network == wallet.network,
                        CryptoWallet.id != wallet.id,
                        CryptoWallet.is_default == True
                    )
                ).update({"is_default": False})
            )
            wallet.is_default = True
        
        await self.db.commit()
        await self.db.refresh(wallet)
        
        return CryptoWalletResponse.model_validate(wallet)
    
    async def process_payout(
        self,
        payout: Payout
    ) -> Dict[str, Any]:
        """
        Process a crypto payout.
        
        Args:
            payout: Payout to process
            
        Returns:
            Processing result
        """
        # Get wallet
        wallet_id = payout.payment_details.get('wallet_id')
        if not wallet_id:
            return {'success': False, 'error': 'No wallet specified'}
        
        wallet = await self.db.get(CryptoWallet, wallet_id)
        if not wallet:
            return {'success': False, 'error': 'Wallet not found'}
        
        if not wallet.is_active:
            return {'success': False, 'error': 'Wallet is not active'}
        
        # Get payment gateway
        gateway = await self._get_payment_gateway(wallet.network)
        if not gateway:
            return {'success': False, 'error': 'No payment gateway configured'}
        
        try:
            # Create payment request
            payment_request = CryptoPaymentRequest(
                amount=payout.amount,
                currency="USD",  # Always calculate in USD first
                description=f"Payout {payout.id}",
                recipient_wallet_id=str(wallet.id),
                metadata={
                    'payout_id': str(payout.id),
                    'recipient_id': str(payout.recipient_id)
                }
            )
            
            # Process through gateway
            result = await self._process_gateway_payment(
                gateway,
                wallet,
                payment_request
            )
            
            if result['success']:
                # Record transaction
                transaction = FinancialTransaction(
                    user_id=payout.recipient_id,
                    type=TransactionType.PAYOUT,
                    amount=payout.amount,
                    payout_id=payout.id,
                    external_reference=result.get('transaction_id'),
                    description=f"Crypto payout to {wallet.address}",
                    transaction_date=datetime.utcnow()
                )
                self.db.add(transaction)
                await self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Crypto payout failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def handle_payment_webhook(
        self,
        provider: str,
        headers: Dict[str, str],
        body: bytes
    ) -> Dict[str, Any]:
        """
        Handle payment webhook from crypto provider.
        
        Args:
            provider: Payment provider name
            headers: Request headers
            body: Raw request body
            
        Returns:
            Processing result
        """
        # Get gateway config
        result = await self.db.execute(
            select(PaymentGatewayConfig).where(
                and_(
                    PaymentGatewayConfig.provider == provider,
                    PaymentGatewayConfig.is_active == True
                )
            )
        )
        gateway = result.scalar_one_or_none()
        
        if not gateway:
            logger.warning(f"No active gateway for provider {provider}")
            return {'success': False, 'error': 'Unknown provider'}
        
        # Verify webhook signature
        if not self._verify_webhook_signature(gateway, headers, body):
            logger.warning(f"Invalid webhook signature from {provider}")
            return {'success': False, 'error': 'Invalid signature'}
        
        # Parse webhook data
        try:
            data = json.loads(body)
            
            # Process based on provider
            if provider == "coinbase_commerce":
                return await self._handle_coinbase_webhook(data)
            elif provider == "bitpay":
                return await self._handle_bitpay_webhook(data)
            else:
                logger.warning(f"Unhandled provider: {provider}")
                return {'success': False, 'error': 'Unhandled provider'}
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _get_payment_gateway(
        self,
        network: CryptoNetwork
    ) -> Optional[PaymentGatewayConfig]:
        """Get appropriate payment gateway for network."""
        # Map networks to supported providers
        network_providers = {
            CryptoNetwork.BITCOIN: ["bitpay", "coinbase_commerce"],
            CryptoNetwork.ETHEREUM: ["coinbase_commerce"],
            CryptoNetwork.USDT_ERC20: ["coinbase_commerce"],
            CryptoNetwork.USDC: ["coinbase_commerce"],
            # Add more mappings as needed
        }
        
        providers = network_providers.get(network, [])
        if not providers:
            return None
        
        # Get first active gateway
        result = await self.db.execute(
            select(PaymentGatewayConfig).where(
                and_(
                    PaymentGatewayConfig.provider.in_(providers),
                    PaymentGatewayConfig.is_active == True
                )
            )
        )
        
        return result.scalar_one_or_none()
    
    async def _process_gateway_payment(
        self,
        gateway: PaymentGatewayConfig,
        wallet: CryptoWallet,
        request: CryptoPaymentRequest
    ) -> Dict[str, Any]:
        """Process payment through specific gateway."""
        if gateway.provider == "coinbase_commerce":
            return await self._process_coinbase_payment(gateway, wallet, request)
        elif gateway.provider == "bitpay":
            return await self._process_bitpay_payment(gateway, wallet, request)
        else:
            return {'success': False, 'error': f'Unsupported provider: {gateway.provider}'}
    
    async def _process_coinbase_payment(
        self,
        gateway: PaymentGatewayConfig,
        wallet: CryptoWallet,
        request: CryptoPaymentRequest
    ) -> Dict[str, Any]:
        """Process payment through Coinbase Commerce."""
        # This is a placeholder - actual implementation would use Coinbase Commerce API
        # For MVP, we'll simulate the payment
        
        logger.info(f"Processing Coinbase payment: {request.amount} USD to {wallet.address}")
        
        # In production:
        # 1. Convert USD amount to crypto amount based on current rates
        # 2. Create charge/payment via Coinbase Commerce API
        # 3. Return transaction details
        
        # Simulated response
        return {
            'success': True,
            'transaction_id': f"cb_{datetime.utcnow().timestamp()}",
            'transaction_hash': hashlib.sha256(
                f"{wallet.address}{request.amount}{datetime.utcnow()}".encode()
            ).hexdigest(),
            'amount_crypto': "0.001",  # Simulated crypto amount
            'currency_crypto': self._get_crypto_currency(wallet.network),
            'status': 'pending'
        }
    
    async def _process_bitpay_payment(
        self,
        gateway: PaymentGatewayConfig,
        wallet: CryptoWallet,
        request: CryptoPaymentRequest
    ) -> Dict[str, Any]:
        """Process payment through BitPay."""
        # Placeholder for BitPay implementation
        logger.info(f"Processing BitPay payment: {request.amount} USD to {wallet.address}")
        
        return {
            'success': True,
            'transaction_id': f"bp_{datetime.utcnow().timestamp()}",
            'transaction_hash': hashlib.sha256(
                f"{wallet.address}{request.amount}{datetime.utcnow()}".encode()
            ).hexdigest(),
            'status': 'pending'
        }
    
    def _verify_webhook_signature(
        self,
        gateway: PaymentGatewayConfig,
        headers: Dict[str, str],
        body: bytes
    ) -> bool:
        """Verify webhook signature from payment provider."""
        if not gateway.webhook_secret:
            return True  # No secret configured, skip verification
        
        if gateway.provider == "coinbase_commerce":
            # Coinbase uses HMAC SHA256
            signature = headers.get('X-CC-Webhook-Signature', '')
            expected = hmac.new(
                gateway.webhook_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        
        elif gateway.provider == "bitpay":
            # BitPay uses different signature method
            # Implement BitPay signature verification
            return True
        
        return False
    
    async def _handle_coinbase_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Coinbase Commerce webhook."""
        event_type = data.get('event', {}).get('type')
        
        if event_type == 'charge:confirmed':
            # Payment confirmed
            payout_id = data.get('event', {}).get('data', {}).get('metadata', {}).get('payout_id')
            if payout_id:
                # Update payout status
                from modules.financial.application.payout_service import PayoutService
                payout_service = PayoutService(self.db)
                
                await payout_service.update_payout_status(
                    payout_id,
                    PayoutStatusUpdate(
                        status=PayoutStatus.COMPLETED,
                        transaction_hash=data.get('event', {}).get('data', {}).get('transaction_hash')
                    )
                )
        
        return {'success': True}
    
    async def _handle_bitpay_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle BitPay webhook."""
        # Implement BitPay webhook handling
        return {'success': True}
    
    def _get_crypto_currency(self, network: CryptoNetwork) -> str:
        """Get crypto currency code for network."""
        mapping = {
            CryptoNetwork.BITCOIN: "BTC",
            CryptoNetwork.ETHEREUM: "ETH",
            CryptoNetwork.BINANCE_SMART_CHAIN: "BNB",
            CryptoNetwork.POLYGON: "MATIC",
            CryptoNetwork.TRON: "TRX",
            CryptoNetwork.USDT_TRC20: "USDT",
            CryptoNetwork.USDT_ERC20: "USDT",
            CryptoNetwork.USDC: "USDC"
        }
        return mapping.get(network, "USD")