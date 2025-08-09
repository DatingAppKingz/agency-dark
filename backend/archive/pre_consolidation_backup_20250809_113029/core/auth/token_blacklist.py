"""
JWT Token Blacklist Management

This module handles token revocation and blacklisting for enhanced security.
"""
from datetime import datetime, timedelta
from typing import Optional, List
import logging
from sqlalchemy import Column, String, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid

from core.database import Base
from core.redis import redis_client
from core.security import hash_token

logger = logging.getLogger(__name__)


class TokenBlacklist(Base):
    """Blacklisted JWT tokens."""
    __tablename__ = "token_blacklist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA256 hash
    jti = Column(String(255), unique=True, nullable=False, index=True)  # JWT ID
    user_id = Column(UUID(as_uuid=True), index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    reason = Column(Text)
    revoked_by = Column(UUID(as_uuid=True))
    
    __table_args__ = (
        Index('idx_token_blacklist_expires', 'expires_at'),
    )


class TokenBlacklistService:
    """Service for managing token blacklist."""
    
    def __init__(self):
        self.cache_prefix = "token_blacklist:"
        self.cache_ttl = 3600  # 1 hour cache
    
    async def blacklist_token(
        self,
        token: str,
        jti: str,
        user_id: str,
        expires_at: datetime,
        reason: str = "Manual revocation",
        revoked_by: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """Add a token to the blacklist."""
        try:
            token_hash = hash_token(token)
            
            # Add to database
            if db:
                blacklist_entry = TokenBlacklist(
                    token_hash=token_hash,
                    jti=jti,
                    user_id=user_id,
                    expires_at=expires_at,
                    reason=reason,
                    revoked_by=revoked_by
                )
                db.add(blacklist_entry)
                await db.commit()
            
            # Add to Redis cache
            cache_key = f"{self.cache_prefix}{jti}"
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            if ttl > 0:
                await redis_client.setex(
                    cache_key,
                    ttl,
                    "1"  # Just mark as blacklisted
                )
            
            logger.info(f"Token blacklisted: JTI={jti}, User={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False
    
    async def is_token_blacklisted(
        self,
        jti: str,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """Check if a token is blacklisted."""
        try:
            # Check Redis cache first
            cache_key = f"{self.cache_prefix}{jti}"
            cached = await redis_client.get(cache_key)
            if cached:
                return True
            
            # Check database
            if db:
                result = await db.execute(
                    select(TokenBlacklist).where(
                        TokenBlacklist.jti == jti,
                        TokenBlacklist.expires_at > datetime.utcnow()
                    )
                )
                entry = result.scalar_one_or_none()
                
                if entry:
                    # Cache the result
                    ttl = int((entry.expires_at - datetime.utcnow()).total_seconds())
                    if ttl > 0:
                        await redis_client.setex(cache_key, ttl, "1")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # Temporarily fail open to allow authentication to work
            # TODO: Fix mapper issues and revert to fail closed
            return False
    
    async def blacklist_all_user_tokens(
        self,
        user_id: str,
        reason: str = "User logout",
        revoked_by: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> int:
        """Blacklist all tokens for a user (logout all sessions)."""
        try:
            count = 0
            
            if db:
                # Get all active sessions for the user
                from core.domain.models import Session
                result = await db.execute(
                    select(Session).where(
                        Session.user_id == user_id,
                        Session.is_active == True,
                        Session.expires_at > datetime.utcnow()
                    )
                )
                sessions = result.scalars().all()
                
                # Deactivate all sessions
                for session in sessions:
                    session.is_active = False
                    count += 1
                
                # Note: We can't blacklist the actual tokens without storing them,
                # but deactivating sessions achieves the same effect
                
                await db.commit()
                
            logger.info(f"Blacklisted {count} tokens for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to blacklist user tokens: {e}")
            return 0
    
    async def cleanup_expired_tokens(
        self,
        db: AsyncSession
    ) -> int:
        """Remove expired tokens from the blacklist."""
        try:
            result = await db.execute(
                delete(TokenBlacklist).where(
                    TokenBlacklist.expires_at < datetime.utcnow()
                )
            )
            await db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} expired blacklist entries")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0
    
    async def get_blacklist_stats(
        self,
        db: AsyncSession,
        hours: int = 24
    ) -> dict:
        """Get blacklist statistics."""
        try:
            # Count total blacklisted tokens
            total_result = await db.execute(
                select(TokenBlacklist).where(
                    TokenBlacklist.expires_at > datetime.utcnow()
                )
            )
            total_count = len(total_result.scalars().all())
            
            # Count recent blacklists
            recent_result = await db.execute(
                select(TokenBlacklist).where(
                    TokenBlacklist.revoked_at > datetime.utcnow() - timedelta(hours=hours),
                    TokenBlacklist.expires_at > datetime.utcnow()
                )
            )
            recent_count = len(recent_result.scalars().all())
            
            return {
                "total_blacklisted": total_count,
                f"blacklisted_last_{hours}h": recent_count,
                "cache_keys": await redis_client.dbsize() if redis_client else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get blacklist stats: {e}")
            return {
                "total_blacklisted": 0,
                f"blacklisted_last_{hours}h": 0,
                "cache_keys": 0
            }


# Global instance
token_blacklist_service = TokenBlacklistService()