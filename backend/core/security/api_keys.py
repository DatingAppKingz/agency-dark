"""
API key management and rotation system.
"""

import secrets
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from cryptography.fernet import Fernet

from app.core.database import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.models import APIKey, User

logger = get_logger(__name__)


class APIKeyManager:
    """Manage API keys with rotation and security features."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.encryption_key = settings.SECRET_KEY.encode()[:32]
        self.fernet = Fernet(Fernet.generate_key())
        
        # Configuration
        self.key_length = 32
        self.key_prefix = "ak_"
        self.rotation_period_days = 90
        self.max_keys_per_user = 5
        self.cache_ttl = 3600  # 1 hour
    
    @classmethod
    async def create(cls, redis_url: str = None) -> "APIKeyManager":
        """Create API key manager with Redis connection."""
        redis_url = redis_url or settings.REDIS_URL
        redis_client = await redis.from_url(redis_url)
        return cls(redis_client)
    
    async def generate_api_key(
        self,
        user_id: int,
        name: str,
        permissions: List[str],
        expires_in_days: Optional[int] = None,
        db: AsyncSession = None
    ) -> Tuple[str, Dict[str, any]]:
        """Generate a new API key for a user."""
        # Generate secure random key
        raw_key = secrets.token_urlsafe(self.key_length)
        api_key = f"{self.key_prefix}{raw_key}"
        
        # Hash the key for storage
        key_hash = self._hash_key(api_key)
        
        # Set expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key_record = APIKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=api_key[:8],  # Store prefix for identification
            permissions=permissions,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            last_used_at=None,
            is_active=True
        )
        
        # Check key limit
        if db:
            existing_keys = await db.execute(
                select(func.count(APIKey.id))
                .where(APIKey.user_id == user_id)
                .where(APIKey.is_active == True)
            )
            key_count = existing_keys.scalar()
            
            if key_count >= self.max_keys_per_user:
                raise ValueError(f"User has reached maximum of {self.max_keys_per_user} API keys")
            
            # Save to database
            db.add(api_key_record)
            await db.commit()
            await db.refresh(api_key_record)
        
        # Cache the key permissions
        if self.redis:
            await self._cache_key_data(api_key, {
                "user_id": user_id,
                "permissions": permissions,
                "expires_at": expires_at.isoformat() if expires_at else None
            })
        
        # Log key creation
        logger.info(
            f"API key created for user {user_id}",
            extra={
                "user_id": user_id,
                "key_prefix": api_key[:8],
                "permissions": permissions
            }
        )
        
        # Return the unhashed key (only shown once)
        return api_key, {
            "id": api_key_record.id,
            "name": name,
            "prefix": api_key[:8],
            "permissions": permissions,
            "expires_at": expires_at,
            "created_at": api_key_record.created_at
        }
    
    async def validate_api_key(
        self,
        api_key: str,
        required_permissions: Optional[List[str]] = None,
        db: AsyncSession = None
    ) -> Optional[Dict[str, any]]:
        """Validate an API key and check permissions."""
        # Check cache first
        cached_data = await self._get_cached_key_data(api_key)
        if cached_data:
            # Validate permissions
            if required_permissions and not all(
                perm in cached_data["permissions"] for perm in required_permissions
            ):
                return None
            
            # Check expiration
            if cached_data.get("expires_at"):
                expires_at = datetime.fromisoformat(cached_data["expires_at"])
                if expires_at < datetime.utcnow():
                    await self._invalidate_cache(api_key)
                    return None
            
            return cached_data
        
        # Validate against database
        if not db:
            return None
        
        key_hash = self._hash_key(api_key)
        
        result = await db.execute(
            select(APIKey)
            .where(APIKey.key_hash == key_hash)
            .where(APIKey.is_active == True)
        )
        api_key_record = result.scalar_one_or_none()
        
        if not api_key_record:
            return None
        
        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            api_key_record.is_active = False
            await db.commit()
            return None
        
        # Check permissions
        if required_permissions and not all(
            perm in api_key_record.permissions for perm in required_permissions
        ):
            return None
        
        # Update last used timestamp
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.usage_count += 1
        await db.commit()
        
        # Cache the validated data
        key_data = {
            "user_id": api_key_record.user_id,
            "permissions": api_key_record.permissions,
            "expires_at": api_key_record.expires_at.isoformat() if api_key_record.expires_at else None
        }
        
        if self.redis:
            await self._cache_key_data(api_key, key_data)
        
        return key_data
    
    async def rotate_api_key(
        self,
        old_key_id: int,
        user_id: int,
        db: AsyncSession
    ) -> Tuple[str, Dict[str, any]]:
        """Rotate an API key, creating a new one and invalidating the old."""
        # Get old key data
        result = await db.execute(
            select(APIKey)
            .where(APIKey.id == old_key_id)
            .where(APIKey.user_id == user_id)
            .where(APIKey.is_active == True)
        )
        old_key = result.scalar_one_or_none()
        
        if not old_key:
            raise ValueError("API key not found or inactive")
        
        # Generate new key with same permissions
        new_key, new_key_data = await self.generate_api_key(
            user_id=user_id,
            name=f"{old_key.name} (rotated)",
            permissions=old_key.permissions,
            expires_in_days=self.rotation_period_days,
            db=db
        )
        
        # Mark old key for revocation (with grace period)
        old_key.revoked_at = datetime.utcnow() + timedelta(hours=24)  # 24 hour grace period
        old_key.replaced_by_id = new_key_data["id"]
        await db.commit()
        
        # Log rotation
        logger.info(
            f"API key rotated for user {user_id}",
            extra={
                "user_id": user_id,
                "old_key_id": old_key_id,
                "new_key_id": new_key_data["id"]
            }
        )
        
        return new_key, new_key_data
    
    async def revoke_api_key(
        self,
        key_id: int,
        user_id: int,
        reason: str,
        db: AsyncSession
    ) -> bool:
        """Revoke an API key."""
        result = await db.execute(
            select(APIKey)
            .where(APIKey.id == key_id)
            .where(APIKey.user_id == user_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return False
        
        # Revoke the key
        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.revocation_reason = reason
        await db.commit()
        
        # Clear cache
        if self.redis and api_key.key_prefix:
            # We can't clear exact key without unhashed value
            # In production, consider storing encrypted key reference
            pass
        
        # Log revocation
        logger.info(
            f"API key revoked for user {user_id}",
            extra={
                "user_id": user_id,
                "key_id": key_id,
                "reason": reason
            }
        )
        
        return True
    
    async def list_user_keys(
        self,
        user_id: int,
        include_revoked: bool = False,
        db: AsyncSession = None
    ) -> List[Dict[str, any]]:
        """List all API keys for a user."""
        if not db:
            return []
        
        query = select(APIKey).where(APIKey.user_id == user_id)
        
        if not include_revoked:
            query = query.where(APIKey.is_active == True)
        
        result = await db.execute(query.order_by(APIKey.created_at.desc()))
        keys = result.scalars().all()
        
        return [
            {
                "id": key.id,
                "name": key.name,
                "prefix": key.key_prefix,
                "permissions": key.permissions,
                "created_at": key.created_at,
                "expires_at": key.expires_at,
                "last_used_at": key.last_used_at,
                "is_active": key.is_active,
                "revoked_at": key.revoked_at,
                "usage_count": key.usage_count
            }
            for key in keys
        ]
    
    async def check_keys_for_rotation(self, db: AsyncSession) -> List[Dict[str, any]]:
        """Check for API keys that need rotation."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.rotation_period_days - 7)  # 7 day warning
        
        result = await db.execute(
            select(APIKey)
            .where(APIKey.is_active == True)
            .where(APIKey.created_at <= cutoff_date)
            .where(APIKey.rotated_at == None)
        )
        
        keys_needing_rotation = result.scalars().all()
        
        return [
            {
                "id": key.id,
                "user_id": key.user_id,
                "name": key.name,
                "created_at": key.created_at,
                "days_old": (datetime.utcnow() - key.created_at).days
            }
            for key in keys_needing_rotation
        ]
    
    def _hash_key(self, api_key: str) -> str:
        """Hash API key for secure storage."""
        return hashlib.sha256(
            api_key.encode() + self.encryption_key
        ).hexdigest()
    
    async def _cache_key_data(self, api_key: str, data: Dict[str, any]):
        """Cache API key data in Redis."""
        if not self.redis:
            return
        
        cache_key = f"api_key:{self._hash_key(api_key)}"
        
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(data)
        )
    
    async def _get_cached_key_data(self, api_key: str) -> Optional[Dict[str, any]]:
        """Get cached API key data."""
        if not self.redis:
            return None
        
        cache_key = f"api_key:{self._hash_key(api_key)}"
        
        data = await self.redis.get(cache_key)
        if data:
            return json.loads(data)
        
        return None
    
    async def _invalidate_cache(self, api_key: str):
        """Invalidate cached API key data."""
        if not self.redis:
            return
        
        cache_key = f"api_key:{self._hash_key(api_key)}"
        await self.redis.delete(cache_key)


# Rotation scheduler
async def rotate_api_keys(db: AsyncSession):
    """Background task to rotate API keys."""
    manager = await APIKeyManager.create()
    
    # Get keys needing rotation
    keys_to_rotate = await manager.check_keys_for_rotation(db)
    
    for key_info in keys_to_rotate:
        try:
            # Notify user about upcoming rotation
            # In production, send email/notification
            logger.info(
                f"API key {key_info['id']} for user {key_info['user_id']} needs rotation",
                extra=key_info
            )
            
            # Auto-rotate if past deadline
            if key_info["days_old"] >= manager.rotation_period_days:
                await manager.rotate_api_key(
                    old_key_id=key_info["id"],
                    user_id=key_info["user_id"],
                    db=db
                )
                
        except Exception as e:
            logger.error(f"Error rotating API key {key_info['id']}: {e}")


# API key authentication dependency
async def verify_api_key(
    api_key: str,
    required_permissions: Optional[List[str]] = None
) -> Optional[Dict[str, any]]:
    """FastAPI dependency for API key authentication."""
    from fastapi import HTTPException, status
    
    async with get_db() as db:
        manager = await APIKeyManager.create()
        
        key_data = await manager.validate_api_key(
            api_key=api_key,
            required_permissions=required_permissions,
            db=db
        )
        
        if not key_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key"
            )
        
        return key_data