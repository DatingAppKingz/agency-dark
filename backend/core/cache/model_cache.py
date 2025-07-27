"""
Caching for model profiles and user data.
"""
import logging
from typing import Dict, Any, Optional, List, Set
from datetime import timedelta
from uuid import UUID

from core.cache.cache_service import cache, CacheKey, cached, cache_invalidate
from core.domain.models import ModelProfile, User, Fan, Agency
from core.domain.schemas import ModelProfileResponse, UserResponse

logger = logging.getLogger(__name__)


class ModelCacheKeys:
    """Standardized cache keys for model data."""
    
    @staticmethod
    def model_profile(model_id: str) -> str:
        """Key for model profile."""
        return CacheKey.generate("model:profile", model_id)
    
    @staticmethod
    def model_by_username(username: str) -> str:
        """Key for model lookup by username."""
        return CacheKey.generate("model:username", username.lower())
    
    @staticmethod
    def agency_models(agency_id: str) -> str:
        """Key for agency's model list."""
        return CacheKey.generate("agency:models", agency_id)
    
    @staticmethod
    def user_profile(user_id: str) -> str:
        """Key for user profile."""
        return CacheKey.generate("user:profile", user_id)
    
    @staticmethod
    def user_permissions(user_id: str) -> str:
        """Key for user permissions."""
        return CacheKey.generate("user:permissions", user_id)
    
    @staticmethod
    def fan_profile(fan_id: str) -> str:
        """Key for fan profile."""
        return CacheKey.generate("fan:profile", fan_id)
    
    @staticmethod
    def model_fans(model_id: str, active_only: bool = True) -> str:
        """Key for model's fan list."""
        return CacheKey.generate(
            "model:fans",
            model_id,
            "active" if active_only else "all"
        )


class ModelCache:
    """Cache management for model and user data."""
    
    # Cache TTLs
    PROFILE_TTL = timedelta(minutes=30)  # User/model profiles
    LIST_TTL = timedelta(minutes=15)  # Lists (fans, models)
    PERMISSION_TTL = timedelta(hours=1)  # Permissions
    USERNAME_TTL = timedelta(hours=6)  # Username lookups
    
    @classmethod
    async def get_model_profile(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Get cached model profile."""
        key = ModelCacheKeys.model_profile(model_id)
        return await cache.get(key)
    
    @classmethod
    async def set_model_profile(cls, model_id: str, profile: Dict[str, Any]):
        """Cache model profile."""
        key = ModelCacheKeys.model_profile(model_id)
        await cache.set(key, profile, cls.PROFILE_TTL)
        
        # Also cache username lookup if available
        if profile.get('onlyfans_username'):
            username_key = ModelCacheKeys.model_by_username(profile['onlyfans_username'])
            await cache.set(username_key, model_id, cls.USERNAME_TTL)
    
    @classmethod
    async def invalidate_model_profile(cls, model_id: str):
        """Invalidate model profile cache."""
        # Get profile first to clear username cache
        profile = await cls.get_model_profile(model_id)
        
        # Delete profile cache
        key = ModelCacheKeys.model_profile(model_id)
        await cache.delete(key)
        
        # Delete username lookup
        if profile and profile.get('onlyfans_username'):
            username_key = ModelCacheKeys.model_by_username(profile['onlyfans_username'])
            await cache.delete(username_key)
        
        # Invalidate agency model list
        if profile and profile.get('agency_id'):
            agency_key = ModelCacheKeys.agency_models(profile['agency_id'])
            await cache.delete(agency_key)
    
    @classmethod
    async def get_user_profile(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user profile."""
        key = ModelCacheKeys.user_profile(user_id)
        return await cache.get(key)
    
    @classmethod
    async def set_user_profile(cls, user_id: str, profile: Dict[str, Any]):
        """Cache user profile."""
        key = ModelCacheKeys.user_profile(user_id)
        await cache.set(key, profile, cls.PROFILE_TTL)
    
    @classmethod
    async def get_user_permissions(cls, user_id: str) -> Optional[Set[str]]:
        """Get cached user permissions."""
        key = ModelCacheKeys.user_permissions(user_id)
        perms = await cache.get(key)
        
        if perms:
            return set(perms)
        return None
    
    @classmethod
    async def set_user_permissions(cls, user_id: str, permissions: Set[str]):
        """Cache user permissions."""
        key = ModelCacheKeys.user_permissions(user_id)
        await cache.set(key, list(permissions), cls.PERMISSION_TTL)
    
    @classmethod
    async def invalidate_user_cache(cls, user_id: str):
        """Invalidate all user-related cache."""
        keys = [
            ModelCacheKeys.user_profile(user_id),
            ModelCacheKeys.user_permissions(user_id)
        ]
        await cache.delete(keys)
    
    @classmethod
    async def batch_get_models(cls, model_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple model profiles efficiently."""
        # Generate keys
        keys = [ModelCacheKeys.model_profile(model_id) for model_id in model_ids]
        
        # Batch get from cache
        cached_values = await cache.get_many(keys)
        
        result = {}
        missing_ids = []
        
        # Process cached values
        for model_id, key in zip(model_ids, keys):
            if cached_values.get(key) is not None:
                result[model_id] = cached_values[key]
            else:
                missing_ids.append(model_id)
        
        # Return what we have (caller should fetch missing from DB)
        return result
    
    @classmethod
    async def cache_agency_models(
        cls,
        agency_id: str,
        model_ids: List[str]
    ):
        """Cache agency's model list."""
        key = ModelCacheKeys.agency_models(agency_id)
        await cache.set(key, model_ids, cls.LIST_TTL)
    
    @classmethod
    async def get_agency_models(cls, agency_id: str) -> Optional[List[str]]:
        """Get cached agency model list."""
        key = ModelCacheKeys.agency_models(agency_id)
        return await cache.get(key)


# Cached functions with decorators
@cached(
    prefix="model:profile:full",
    ttl=ModelCache.PROFILE_TTL,
    model_class=ModelProfileResponse
)
async def get_cached_model_profile(model_id: str) -> ModelProfileResponse:
    """Get model profile with caching."""
    # Actual DB query would go here
    pass


@cached(
    prefix="user:profile:full",
    ttl=ModelCache.PROFILE_TTL,
    model_class=UserResponse
)
async def get_cached_user_profile(user_id: str) -> UserResponse:
    """Get user profile with caching."""
    # Actual DB query would go here
    pass


@cache_invalidate(
    prefix="model:profile",
    key_func=lambda model: f"*{model.id}*"
)
async def update_model_profile(model: ModelProfile):
    """Update model and invalidate cache."""
    # Update logic here
    pass


class FanCache:
    """Specialized cache for fan data."""
    
    FAN_TTL = timedelta(minutes=15)
    ACTIVE_FANS_TTL = timedelta(minutes=5)
    
    @classmethod
    async def cache_fan_batch(cls, fans: List[Dict[str, Any]]):
        """Cache multiple fans at once."""
        mapping = {}
        
        for fan in fans:
            key = ModelCacheKeys.fan_profile(fan['id'])
            mapping[key] = fan
        
        await cache.set_many(mapping, cls.FAN_TTL)
    
    @classmethod
    async def get_model_active_fans_count(cls, model_id: str) -> Optional[int]:
        """Get cached active fan count."""
        key = CacheKey.generate("model:fans:count:active", model_id)
        count = await cache.get(key)
        
        if count is not None:
            return int(count)
        return None
    
    @classmethod
    async def set_model_active_fans_count(cls, model_id: str, count: int):
        """Cache active fan count."""
        key = CacheKey.generate("model:fans:count:active", model_id)
        await cache.set(key, count, cls.ACTIVE_FANS_TTL)


class CachePreloader:
    """Preload frequently accessed data into cache."""
    
    @staticmethod
    async def preload_agency_data(agency_id: str):
        """Preload agency's models and key data."""
        # This would be called on agency login or periodically
        logger.info(f"Preloading cache for agency {agency_id}")
        
        # Would fetch from DB and cache:
        # - Agency profile
        # - All models in agency
        # - Active fan counts
        # - Recent transactions summary
    
    @staticmethod
    async def preload_model_data(model_id: str):
        """Preload model's frequently accessed data."""
        logger.info(f"Preloading cache for model {model_id}")
        
        # Would fetch from DB and cache:
        # - Model profile
        # - Active fans
        # - Recent earnings
        # - Platform credentials status