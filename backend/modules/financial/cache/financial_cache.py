"""
Financial module caching strategies.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from core.cache.cache_service import cache, CacheKey, cached, cache_invalidate
from modules.financial.domain.models import (
    FinancialTransaction,
    TransactionStatus,
    Payout,
    PayoutStatus
)
from modules.financial.domain.schemas import (
    TransactionSummary,
    PayoutSummary,
    CommissionSummary
)

logger = logging.getLogger(__name__)


class FinancialCacheKeys:
    """Standardized cache keys for financial data."""
    
    @staticmethod
    def transaction_summary(
        agency_id: Optional[str] = None,
        model_id: Optional[str] = None,
        period: str = "today"
    ) -> str:
        """Key for transaction summary."""
        return CacheKey.generate(
            "financial:transaction:summary",
            agency_id=agency_id,
            model_id=model_id,
            period=period
        )
    
    @staticmethod
    def balance(entity_type: str, entity_id: str) -> str:
        """Key for entity balance."""
        return CacheKey.generate(
            "financial:balance",
            entity_type,
            entity_id
        )
    
    @staticmethod
    def pending_payouts(model_id: str) -> str:
        """Key for pending payouts."""
        return CacheKey.generate(
            "financial:payouts:pending",
            model_id
        )
    
    @staticmethod
    def commission_rate(model_id: str, transaction_type: str) -> str:
        """Key for commission rate."""
        return CacheKey.generate(
            "financial:commission:rate",
            model_id,
            transaction_type
        )
    
    @staticmethod
    def payment_gateway_status(provider: str) -> str:
        """Key for payment gateway status."""
        return CacheKey.generate(
            "financial:gateway:status",
            provider
        )


class FinancialCache:
    """Cache management for financial data."""
    
    # Cache TTLs
    BALANCE_TTL = timedelta(minutes=1)  # Critical data, short TTL
    SUMMARY_TTL = timedelta(minutes=5)  # Summaries
    RATE_TTL = timedelta(hours=1)  # Commission rates
    STATUS_TTL = timedelta(minutes=2)  # Gateway status
    
    @classmethod
    async def get_balance(
        cls,
        entity_type: str,
        entity_id: str
    ) -> Optional[Decimal]:
        """Get cached balance."""
        key = FinancialCacheKeys.balance(entity_type, entity_id)
        value = await cache.get(key)
        
        if value is not None:
            return Decimal(str(value))
        return None
    
    @classmethod
    async def set_balance(
        cls,
        entity_type: str,
        entity_id: str,
        balance: Decimal
    ):
        """Cache balance with short TTL."""
        key = FinancialCacheKeys.balance(entity_type, entity_id)
        await cache.set(key, str(balance), cls.BALANCE_TTL)
    
    @classmethod
    async def invalidate_balance(
        cls,
        entity_type: str,
        entity_id: str
    ):
        """Invalidate balance cache."""
        key = FinancialCacheKeys.balance(entity_type, entity_id)
        await cache.delete(key)
    
    @classmethod
    async def get_transaction_summary(
        cls,
        agency_id: Optional[str] = None,
        model_id: Optional[str] = None,
        period: str = "today"
    ) -> Optional[TransactionSummary]:
        """Get cached transaction summary."""
        key = FinancialCacheKeys.transaction_summary(agency_id, model_id, period)
        data = await cache.get(key)
        
        if data:
            return TransactionSummary(**data)
        return None
    
    @classmethod
    async def set_transaction_summary(
        cls,
        summary: TransactionSummary,
        agency_id: Optional[str] = None,
        model_id: Optional[str] = None,
        period: str = "today"
    ):
        """Cache transaction summary."""
        key = FinancialCacheKeys.transaction_summary(agency_id, model_id, period)
        await cache.set(key, summary.dict(), cls.SUMMARY_TTL)
    
    @classmethod
    async def cache_commission_rate(
        cls,
        model_id: str,
        transaction_type: str,
        rate: Decimal
    ):
        """Cache commission rate."""
        key = FinancialCacheKeys.commission_rate(model_id, transaction_type)
        await cache.set(key, str(rate), cls.RATE_TTL)
    
    @classmethod
    async def get_commission_rate(
        cls,
        model_id: str,
        transaction_type: str
    ) -> Optional[Decimal]:
        """Get cached commission rate."""
        key = FinancialCacheKeys.commission_rate(model_id, transaction_type)
        value = await cache.get(key)
        
        if value is not None:
            return Decimal(str(value))
        return None
    
    @classmethod
    async def invalidate_transaction_cache(cls, transaction: FinancialTransaction):
        """Invalidate caches affected by transaction."""
        # Invalidate balance caches
        if transaction.model_id:
            await cls.invalidate_balance("model", str(transaction.model_id))
        
        if transaction.agency_id:
            await cls.invalidate_balance("agency", str(transaction.agency_id))
        
        # Invalidate summaries
        patterns = [
            f"*financial:transaction:summary*{transaction.model_id}*",
            f"*financial:transaction:summary*{transaction.agency_id}*"
        ]
        
        for pattern in patterns:
            await cache.delete_pattern(pattern)
    
    @classmethod
    async def cache_gateway_status(
        cls,
        provider: str,
        status: Dict[str, Any]
    ):
        """Cache payment gateway status."""
        key = FinancialCacheKeys.payment_gateway_status(provider)
        await cache.set(key, status, cls.STATUS_TTL)
    
    @classmethod
    async def get_gateway_status(cls, provider: str) -> Optional[Dict[str, Any]]:
        """Get cached gateway status."""
        key = FinancialCacheKeys.payment_gateway_status(provider)
        return await cache.get(key)


# Cached financial functions
@cached(
    prefix="financial:balance:current",
    ttl=FinancialCache.BALANCE_TTL,
    key_func=lambda entity_type, entity_id: f"financial:balance:current:{entity_type}:{entity_id}"
)
async def get_cached_balance(entity_type: str, entity_id: str) -> Decimal:
    """Get current balance with caching."""
    # Actual balance calculation would go here
    return Decimal("0.00")


@cached(
    prefix="financial:pending:amount",
    ttl=timedelta(minutes=5)
)
async def get_cached_pending_amount(model_id: str) -> Decimal:
    """Get pending payout amount with caching."""
    # Actual calculation would go here
    return Decimal("0.00")


@cache_invalidate(
    prefix="financial:transaction:summary",
    key_func=lambda transaction: f"*{transaction.model_id}*" if transaction.model_id else "*"
)
async def create_transaction_with_cache_invalidation(transaction: FinancialTransaction):
    """Create transaction and invalidate related caches."""
    # Transaction creation logic here
    pass


class FinancialCacheOptimizer:
    """Optimize financial cache usage."""
    
    @staticmethod
    async def batch_get_balances(entity_ids: List[str], entity_type: str) -> Dict[str, Decimal]:
        """Get multiple balances efficiently."""
        # Generate keys
        keys = [
            FinancialCacheKeys.balance(entity_type, entity_id)
            for entity_id in entity_ids
        ]
        
        # Batch get from cache
        cached_values = await cache.get_many(keys)
        
        result = {}
        missing_ids = []
        
        # Process cached values
        for entity_id, key in zip(entity_ids, keys):
            if cached_values.get(key) is not None:
                result[entity_id] = Decimal(str(cached_values[key]))
            else:
                missing_ids.append(entity_id)
        
        # Fetch missing values from DB
        if missing_ids:
            # This would be the actual DB query
            # For now, return zeros
            for entity_id in missing_ids:
                balance = Decimal("0.00")
                result[entity_id] = balance
                
                # Cache the fetched value
                await FinancialCache.set_balance(
                    entity_type,
                    entity_id,
                    balance
                )
        
        return result
    
    @staticmethod
    async def preload_commission_rates(model_ids: List[str]):
        """Preload commission rates for multiple models."""
        # This would fetch from DB and cache
        # Used during startup or scheduled tasks
        pass


class PayoutCache:
    """Specialized cache for payout operations."""
    
    PAYOUT_LOCK_TTL = timedelta(minutes=15)  # Prevent duplicate payouts
    
    @classmethod
    async def acquire_payout_lock(
        cls,
        model_id: str,
        amount: Decimal
    ) -> bool:
        """Acquire lock to prevent duplicate payouts."""
        lock_key = CacheKey.generate(
            "financial:payout:lock",
            model_id,
            str(amount),
            datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        # Try to set with NX (only if not exists)
        result = await cache.redis.set(
            lock_key,
            "locked",
            ex=int(cls.PAYOUT_LOCK_TTL.total_seconds()),
            nx=True
        )
        
        return bool(result)
    
    @classmethod
    async def release_payout_lock(
        cls,
        model_id: str,
        amount: Decimal
    ):
        """Release payout lock."""
        lock_key = CacheKey.generate(
            "financial:payout:lock",
            model_id,
            str(amount),
            datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        await cache.delete(lock_key)