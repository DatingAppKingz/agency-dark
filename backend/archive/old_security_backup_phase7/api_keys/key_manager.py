"""
API Key management service for creating, validating, and managing platform API keys.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.platform_api_key import PlatformAPIKey, PlatformAPIKeyUsageLog, PlatformAPIKeyScope
from models.user import User, UserRole
from core.security.api_keys.key_generator import APIKeyGenerator, APIKeyValidator, APIKeyScopeValidator
from core.redis import redis_manager
from core.logger import get_logger

logger = get_logger(__name__)


class APIKeyManager:
    """Manage platform API keys lifecycle."""
    
    def __init__(self):
        self.generator = APIKeyGenerator()
        self.validator = APIKeyValidator()
        self.scope_validator = APIKeyScopeValidator()
        self.cache_ttl = 300  # 5 minutes
    
    async def create_api_key(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        scopes: List[str],
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        rate_limits: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[PlatformAPIKey, str]:
        """
        Create a new API key.
        
        Args:
            db: Database session
            user: User creating the key
            name: Name for the key
            scopes: List of permission scopes
            description: Optional description
            expires_in_days: Days until expiration (None for no expiration)
            allowed_ips: Optional IP restrictions
            allowed_origins: Optional origin restrictions
            rate_limits: Optional custom rate limits
            metadata: Optional metadata
            
        Returns:
            Tuple of (api_key_model, plain_text_key)
        """
        # Validate user permissions
        if not self._can_create_api_key(user, scopes):
            raise PermissionError("User cannot create API key with requested scopes")
        
        # Validate scopes
        valid, error = self.validator.validate_scope_combination(scopes)
        if not valid:
            raise ValueError(f"Invalid scope combination: {error}")
        
        # Validate IP restrictions
        if allowed_ips:
            valid, error = self.validator.validate_ip_restrictions(allowed_ips)
            if not valid:
                raise ValueError(f"Invalid IP restrictions: {error}")
        
        # Generate key
        key_type = "test" if any(s.startswith("test:") for s in scopes) else "live"
        full_key, key_prefix, key_hash = self.generator.generate_key(key_type)
        
        # Calculate expiration
        expires_at = self.validator.calculate_expiration(expires_in_days)
        
        # Set rate limits
        if rate_limits:
            valid, error = self.validator.validate_rate_limits(
                rate_limits.get("per_minute", 60),
                rate_limits.get("per_hour", 1000),
                rate_limits.get("per_day", 10000)
            )
            if not valid:
                raise ValueError(f"Invalid rate limits: {error}")
        
        # Create API key model
        api_key = PlatformAPIKey(
            user_id=user.id,
            agency_id=user.agency_id,
            name=name,
            description=description,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            allowed_ips=allowed_ips,
            allowed_origins=allowed_origins,
            rate_limit_per_minute=rate_limits.get("per_minute", 60) if rate_limits else 60,
            rate_limit_per_hour=rate_limits.get("per_hour", 1000) if rate_limits else 1000,
            rate_limit_per_day=rate_limits.get("per_day", 10000) if rate_limits else 10000,
            expires_at=expires_at,
            metadata=metadata or {},
            created_by_id=user.id
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(
            f"Created API key '{name}' for user {user.email} "
            f"with scopes: {', '.join(scopes)}"
        )
        
        # Cache the key for quick lookups
        await self._cache_api_key(api_key)
        
        return api_key, full_key
    
    async def validate_api_key(
        self,
        db: AsyncSession,
        api_key_string: str,
        required_scope: Optional[str] = None,
        ip_address: Optional[str] = None,
        origin: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[PlatformAPIKey]:
        """
        Validate an API key and check permissions.
        
        Args:
            db: Database session
            api_key_string: The API key to validate
            required_scope: Optional required scope
            ip_address: Client IP address
            origin: Request origin
            user_agent: Client user agent
            
        Returns:
            API key model if valid, None otherwise
        """
        # Validate format
        if not self.generator.validate_format(api_key_string):
            logger.warning(f"Invalid API key format: {api_key_string[:8]}...")
            return None
        
        # Extract prefix and hash
        key_prefix = self.generator.extract_prefix(api_key_string)
        key_hash = self.generator.hash_key(api_key_string)
        
        # Check cache first
        cached_key = await self._get_cached_api_key(key_hash)
        if cached_key:
            api_key = cached_key
        else:
            # Query database
            result = await db.execute(
                select(PlatformAPIKey).where(
                    and_(
                        PlatformAPIKey.key_prefix == key_prefix,
                        PlatformAPIKey.key_hash == key_hash
                    )
                )
            )
            api_key = result.scalar_one_or_none()
            
            if api_key:
                await self._cache_api_key(api_key)
        
        if not api_key:
            logger.warning(f"API key not found: {key_prefix}...")
            return None
        
        # Check if key is valid
        if not api_key.is_valid:
            logger.warning(f"API key invalid: {key_prefix}... (expired: {api_key.is_expired})")
            return None
        
        # Check IP restrictions
        if ip_address and not api_key.is_ip_allowed(ip_address):
            logger.warning(f"API key {key_prefix}... blocked for IP: {ip_address}")
            return None
        
        # Check origin restrictions
        if origin and not api_key.is_origin_allowed(origin):
            logger.warning(f"API key {key_prefix}... blocked for origin: {origin}")
            return None
        
        # Check user agent restrictions
        if user_agent and not api_key.is_user_agent_allowed(user_agent):
            logger.warning(f"API key {key_prefix}... blocked for user agent: {user_agent}")
            return None
        
        # Check required scope
        if required_scope and not self.scope_validator.check_scope_permission(
            required_scope, api_key.scopes
        ):
            logger.warning(
                f"API key {key_prefix}... lacks required scope: {required_scope}"
            )
            return None
        
        # Update last used
        api_key.last_used_at = datetime.utcnow()
        api_key.last_used_ip = ip_address
        
        return api_key
    
    async def check_rate_limit(
        self,
        api_key: PlatformAPIKey,
        db: AsyncSession
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if API key has exceeded rate limits.
        
        Args:
            api_key: The API key to check
            db: Database session
            
        Returns:
            Tuple of (is_allowed, remaining_limits)
        """
        now = datetime.utcnow()
        
        # Check minute limit
        minute_ago = now - timedelta(minutes=1)
        minute_count = await self._get_usage_count(db, api_key.id, minute_ago)
        
        # Check hour limit
        hour_ago = now - timedelta(hours=1)
        hour_count = await self._get_usage_count(db, api_key.id, hour_ago)
        
        # Check day limit
        day_ago = now - timedelta(days=1)
        day_count = await self._get_usage_count(db, api_key.id, day_ago)
        
        # Calculate remaining
        remaining = {
            "minute": max(0, api_key.rate_limit_per_minute - minute_count),
            "hour": max(0, api_key.rate_limit_per_hour - hour_count),
            "day": max(0, api_key.rate_limit_per_day - day_count)
        }
        
        # Check if any limit exceeded
        is_allowed = all(r > 0 for r in remaining.values())
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for API key {api_key.key_prefix}... "
                f"(minute: {minute_count}/{api_key.rate_limit_per_minute}, "
                f"hour: {hour_count}/{api_key.rate_limit_per_hour}, "
                f"day: {day_count}/{api_key.rate_limit_per_day})"
            )
        
        return is_allowed, remaining
    
    async def log_usage(
        self,
        db: AsyncSession,
        api_key: PlatformAPIKey,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        scope_used: Optional[str] = None,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        origin: Optional[str] = None
    ):
        """Log API key usage."""
        usage_log = PlatformAPIKeyUsageLog(
            api_key_id=api_key.id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size=request_size,
            response_size=response_size,
            scope_used=scope_used,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            origin=origin
        )
        
        db.add(usage_log)
        
        # Update API key usage stats
        api_key.increment_usage()
        if status_code >= 400:
            api_key.increment_errors()
        
        await db.commit()
    
    async def revoke_api_key(
        self,
        db: AsyncSession,
        api_key_id: str,
        revoked_by: User,
        reason: str
    ) -> bool:
        """
        Revoke an API key.
        
        Args:
            db: Database session
            api_key_id: ID of the key to revoke
            revoked_by: User revoking the key
            reason: Reason for revocation
            
        Returns:
            True if revoked successfully
        """
        result = await db.execute(
            select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return False
        
        # Check permissions
        if not self._can_revoke_api_key(revoked_by, api_key):
            raise PermissionError("User cannot revoke this API key")
        
        # Revoke the key
        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_by_id = revoked_by.id
        api_key.revoke_reason = reason
        
        await db.commit()
        
        # Remove from cache
        await self._invalidate_cache(api_key)
        
        logger.info(
            f"API key {api_key.key_prefix}... revoked by {revoked_by.email}: {reason}"
        )
        
        return True
    
    async def rotate_api_key(
        self,
        db: AsyncSession,
        api_key_id: str,
        user: User,
        grace_period_hours: int = 24
    ) -> Tuple[PlatformAPIKey, str]:
        """
        Rotate an API key with optional grace period.
        
        Args:
            db: Database session
            api_key_id: ID of the key to rotate
            user: User requesting rotation
            grace_period_hours: Hours before old key expires
            
        Returns:
            Tuple of (new_api_key, plain_text_key)
        """
        # Get existing key
        result = await db.execute(
            select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
        )
        old_key = result.scalar_one_or_none()
        
        if not old_key:
            raise ValueError("API key not found")
        
        # Check permissions
        if not self._can_rotate_api_key(user, old_key):
            raise PermissionError("User cannot rotate this API key")
        
        # Create new key with same settings
        new_key, plain_text = await self.create_api_key(
            db=db,
            user=user,
            name=f"{old_key.name} (Rotated)",
            scopes=old_key.scopes,
            description=f"Rotated from {old_key.key_prefix}...",
            expires_in_days=None,  # Copy from old key
            allowed_ips=old_key.allowed_ips,
            allowed_origins=old_key.allowed_origins,
            rate_limits={
                "per_minute": old_key.rate_limit_per_minute,
                "per_hour": old_key.rate_limit_per_hour,
                "per_day": old_key.rate_limit_per_day
            },
            metadata={**old_key.metadata, "rotated_from": str(old_key.id)}
        )
        
        # Set rotation relationship
        new_key.rotated_from_id = old_key.id
        
        # Schedule old key expiration
        if grace_period_hours > 0:
            old_key.rotation_scheduled_at = datetime.utcnow() + timedelta(hours=grace_period_hours)
            old_key.metadata["rotation_grace_end"] = old_key.rotation_scheduled_at.isoformat()
        else:
            # Immediate revocation
            old_key.is_active = False
            old_key.revoked_at = datetime.utcnow()
            old_key.revoked_by_id = user.id
            old_key.revoke_reason = "Rotated"
        
        await db.commit()
        
        logger.info(
            f"Rotated API key {old_key.key_prefix}... to {new_key.key_prefix}... "
            f"with {grace_period_hours}h grace period"
        )
        
        return new_key, plain_text
    
    async def list_api_keys(
        self,
        db: AsyncSession,
        user: User,
        include_revoked: bool = False,
        agency_id: Optional[str] = None
    ) -> List[PlatformAPIKey]:
        """List API keys accessible to user."""
        query = select(PlatformAPIKey)
        
        # Filter by user permissions
        if user.role == UserRole.SUPER_ADMIN:
            # Super admin sees all
            if agency_id:
                query = query.where(PlatformAPIKey.agency_id == agency_id)
        elif user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            # Agency admin sees agency keys
            query = query.where(PlatformAPIKey.agency_id == user.agency_id)
        else:
            # Others see only their own keys
            query = query.where(PlatformAPIKey.user_id == user.id)
        
        # Filter revoked
        if not include_revoked:
            query = query.where(PlatformAPIKey.revoked_at.is_(None))
        
        # Order by creation
        query = query.order_by(PlatformAPIKey.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    # Private helper methods
    
    def _can_create_api_key(self, user: User, scopes: List[str]) -> bool:
        """Check if user can create API key with given scopes."""
        # Super admin can create any key
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check for admin scopes
        admin_scopes = [s for s in scopes if s.startswith("admin:")]
        if admin_scopes:
            # Only super admin can create admin keys
            return False
        
        # Agency owners/admins can create agency-scoped keys
        if user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return True
        
        # Models can create limited keys
        if user.role == UserRole.MODEL:
            # Only read scopes allowed
            write_scopes = [s for s in scopes if s.startswith("write:")]
            return len(write_scopes) == 0
        
        # Others cannot create keys
        return False
    
    def _can_revoke_api_key(self, user: User, api_key: PlatformAPIKey) -> bool:
        """Check if user can revoke an API key."""
        # Super admin can revoke any key
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # User can revoke their own keys
        if api_key.user_id == user.id:
            return True
        
        # Agency admin can revoke agency keys
        if user.role in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            return api_key.agency_id == user.agency_id
        
        return False
    
    def _can_rotate_api_key(self, user: User, api_key: PlatformAPIKey) -> bool:
        """Check if user can rotate an API key."""
        # Same as revoke permissions
        return self._can_revoke_api_key(user, api_key)
    
    async def _get_usage_count(
        self,
        db: AsyncSession,
        api_key_id: str,
        since: datetime
    ) -> int:
        """Get usage count since a given time."""
        result = await db.execute(
            select(func.count(PlatformAPIKeyUsageLog.id)).where(
                and_(
                    PlatformAPIKeyUsageLog.api_key_id == api_key_id,
                    PlatformAPIKeyUsageLog.timestamp >= since
                )
            )
        )
        return result.scalar() or 0
    
    async def _cache_api_key(self, api_key: PlatformAPIKey):
        """Cache API key for fast lookups."""
        if not redis_manager:
            return
        
        import json
        
        cache_data = {
            "id": str(api_key.id),
            "user_id": str(api_key.user_id),
            "agency_id": str(api_key.agency_id) if api_key.agency_id else None,
            "scopes": api_key.scopes,
            "is_active": api_key.is_active,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "allowed_ips": api_key.allowed_ips,
            "allowed_origins": api_key.allowed_origins,
            "rate_limits": {
                "per_minute": api_key.rate_limit_per_minute,
                "per_hour": api_key.rate_limit_per_hour,
                "per_day": api_key.rate_limit_per_day
            }
        }
        
        cache_key = f"api_key:{api_key.key_hash}"
        await redis_manager.set(
            cache_key,
            json.dumps(cache_data),
            expire=self.cache_ttl
        )
    
    async def _get_cached_api_key(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached API key data."""
        if not redis_manager:
            return None
        
        cache_key = f"api_key:{key_hash}"
        data = await redis_manager.get(cache_key)
        
        if data:
            import json
            return json.loads(data)
        
        return None
    
    async def _invalidate_cache(self, api_key: PlatformAPIKey):
        """Remove API key from cache."""
        if not redis_manager:
            return
        
        cache_key = f"api_key:{api_key.key_hash}"
        await redis_manager.delete(cache_key)


# Global API key manager instance
api_key_manager = APIKeyManager()