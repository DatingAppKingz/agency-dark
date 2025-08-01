"""
Enhanced API Key Security System

Provides advanced API key security features:
- Secure key generation with cryptographic randomness
- Key rotation and versioning
- Scope-based permissions
- Usage tracking and analytics
- Automatic key expiration
- IP whitelisting per key
- Request signing validation
- Key compromise detection
"""
import secrets
import hashlib
import hmac
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import base64
import re

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_

from core.database import get_db
from core.logger import get_logger
from core.redis import redis_client
from models.api_key import APIKey

logger = get_logger(__name__)


class APIKeyScope(str, Enum):
    """API key permission scopes."""
    # Read permissions
    READ_USERS = "read:users"
    READ_AGENCIES = "read:agencies"
    READ_CONTENT = "read:content"
    READ_ANALYTICS = "read:analytics"
    READ_FINANCIAL = "read:financial"
    
    # Write permissions
    WRITE_USERS = "write:users"
    WRITE_AGENCIES = "write:agencies"
    WRITE_CONTENT = "write:content"
    WRITE_ANALYTICS = "write:analytics"
    WRITE_FINANCIAL = "write:financial"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_AGENCIES = "admin:agencies"
    ADMIN_SYSTEM = "admin:system"
    
    # Special permissions
    WEBHOOKS = "webhooks"
    INTEGRATIONS = "integrations"
    BULK_OPERATIONS = "bulk:operations"


@dataclass
class APIKeyInfo:
    """API key information."""
    key_id: str
    user_id: int
    name: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    ip_whitelist: Optional[List[str]]
    version: int
    is_active: bool
    usage_count: int


class APIKeySecurity:
    """Enhanced API key security system."""
    
    def __init__(self):
        self.key_prefix = "agdk"  # Agency Dark prefix
        self.key_length = 32  # 256 bits of entropy
        self.hash_algorithm = "sha256"
        self.signature_algorithm = "sha256"
        self.key_cache_ttl = 300  # 5 minutes
        
        # Security settings
        self.max_key_age_days = 365
        self.rotation_warning_days = 30
        self.max_failed_attempts = 5
        self.lockout_duration = 3600  # 1 hour
        
        # Usage tracking
        self.track_usage = True
        self.usage_window = 3600  # 1 hour
        
        # Bearer token scheme
        self.bearer_scheme = HTTPBearer()
    
    def generate_api_key(self) -> Tuple[str, str, str]:
        """
        Generate a secure API key.
        
        Returns:
            Tuple of (public_key, secret_key, key_hash)
        """
        # Generate cryptographically secure random bytes
        key_bytes = secrets.token_bytes(self.key_length)
        
        # Create key components
        key_id = secrets.token_urlsafe(8)  # Short ID for reference
        secret = base64.urlsafe_b64encode(key_bytes).decode('utf-8').rstrip('=')
        
        # Create public key (shown to user)
        public_key = f"{self.key_prefix}_{key_id}_{secret}"
        
        # Create hash for storage (never store plain key)
        key_hash = self._hash_key(public_key)
        
        # Create secret key for signing (optional, for HMAC)
        secret_key = secrets.token_urlsafe(32)
        
        return public_key, secret_key, key_hash
    
    def _hash_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def create_api_key(
        self,
        db: AsyncSession,
        user_id: int,
        name: str,
        scopes: List[str],
        expires_in_days: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None
    ) -> Tuple[str, str, APIKey]:
        """
        Create a new API key with enhanced security.
        
        Args:
            db: Database session
            user_id: User ID
            name: Key name/description
            scopes: List of permission scopes
            expires_in_days: Days until expiration
            ip_whitelist: List of allowed IPs
            
        Returns:
            Tuple of (public_key, secret_key, api_key_model)
        """
        # Validate scopes
        valid_scopes = {s.value for s in APIKeyScope}
        invalid_scopes = set(scopes) - valid_scopes
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {invalid_scopes}")
        
        # Generate key
        public_key, secret_key, key_hash = self.generate_api_key()
        
        # Extract key ID from public key
        key_id = public_key.split('_')[1]
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        elif self.max_key_age_days:
            expires_at = datetime.utcnow() + timedelta(days=self.max_key_age_days)
        
        # Create database record
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            secret_hash=self._hash_key(secret_key),
            user_id=user_id,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            ip_whitelist=ip_whitelist,
            version=1,
            is_active=True,
            metadata={
                "created_by": "api_key_security",
                "algorithm": self.hash_algorithm
            }
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        # Log key creation
        logger.info(
            f"Created API key '{name}' for user {user_id} "
            f"with scopes: {', '.join(scopes)}"
        )
        
        return public_key, secret_key, api_key
    
    async def validate_api_key(
        self,
        credentials: HTTPAuthorizationCredentials,
        db: AsyncSession,
        required_scopes: Optional[List[str]] = None,
        request: Optional[Request] = None
    ) -> APIKeyInfo:
        """
        Validate API key with enhanced security checks.
        
        Args:
            credentials: Bearer token credentials
            db: Database session
            required_scopes: Required permission scopes
            request: FastAPI request object
            
        Returns:
            APIKeyInfo object
            
        Raises:
            HTTPException: If validation fails
        """
        api_key = credentials.credentials
        
        # Check key format
        if not self._validate_key_format(api_key):
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        # Extract key ID
        try:
            parts = api_key.split('_')
            key_id = parts[1]
        except (IndexError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        # Check cache first
        cached_info = await self._get_cached_key_info(key_id)
        if cached_info:
            api_key_info = cached_info
        else:
            # Hash the key
            key_hash = self._hash_key(api_key)
            
            # Look up in database
            result = await db.execute(
                select(APIKey).where(
                    and_(
                        APIKey.key_id == key_id,
                        APIKey.key_hash == key_hash,
                        APIKey.is_active == True
                    )
                )
            )
            api_key_model = result.scalar_one_or_none()
            
            if not api_key_model:
                # Check if key exists but is wrong (potential attack)
                exists = await db.execute(
                    select(APIKey).where(APIKey.key_id == key_id)
                )
                if exists.scalar_one_or_none():
                    await self._record_failed_attempt(key_id)
                
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            # Create info object
            api_key_info = APIKeyInfo(
                key_id=api_key_model.key_id,
                user_id=api_key_model.user_id,
                name=api_key_model.name,
                scopes=api_key_model.scopes,
                created_at=api_key_model.created_at,
                expires_at=api_key_model.expires_at,
                last_used_at=api_key_model.last_used_at,
                ip_whitelist=api_key_model.ip_whitelist,
                version=api_key_model.version,
                is_active=api_key_model.is_active,
                usage_count=api_key_model.usage_count
            )
            
            # Cache the info
            await self._cache_key_info(api_key_info)
        
        # Security checks
        await self._perform_security_checks(api_key_info, request)
        
        # Check required scopes
        if required_scopes:
            missing_scopes = set(required_scopes) - set(api_key_info.scopes)
            if missing_scopes:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required scopes: {', '.join(missing_scopes)}"
                )
        
        # Track usage
        if self.track_usage:
            await self._track_usage(api_key_info.key_id, db)
        
        return api_key_info
    
    def _validate_key_format(self, api_key: str) -> bool:
        """Validate API key format."""
        pattern = rf"^{self.key_prefix}_[a-zA-Z0-9_-]+_[a-zA-Z0-9_-]+$"
        return bool(re.match(pattern, api_key))
    
    async def _perform_security_checks(
        self,
        api_key_info: APIKeyInfo,
        request: Optional[Request]
    ):
        """Perform security checks on API key."""
        # Check if key is locked due to failed attempts
        if await self._is_key_locked(api_key_info.key_id):
            raise HTTPException(
                status_code=401,
                detail="API key is temporarily locked"
            )
        
        # Check expiration
        if api_key_info.expires_at and datetime.utcnow() > api_key_info.expires_at:
            raise HTTPException(status_code=401, detail="API key has expired")
        
        # Check IP whitelist
        if api_key_info.ip_whitelist and request:
            client_ip = self._get_client_ip(request)
            if client_ip not in api_key_info.ip_whitelist:
                logger.warning(
                    f"API key {api_key_info.key_id} used from "
                    f"non-whitelisted IP: {client_ip}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access from this IP is not allowed"
                )
        
        # Check for key rotation warning
        key_age = datetime.utcnow() - api_key_info.created_at
        if key_age.days > (self.max_key_age_days - self.rotation_warning_days):
            logger.warning(
                f"API key {api_key_info.key_id} should be rotated soon "
                f"(age: {key_age.days} days)"
            )
    
    async def rotate_api_key(
        self,
        db: AsyncSession,
        old_key_id: str,
        user_id: int
    ) -> Tuple[str, str, APIKey]:
        """
        Rotate an API key (create new, deprecate old).
        
        Args:
            db: Database session
            old_key_id: ID of key to rotate
            user_id: User ID (for verification)
            
        Returns:
            New key tuple
        """
        # Get old key
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_id == old_key_id,
                    APIKey.user_id == user_id,
                    APIKey.is_active == True
                )
            )
        )
        old_key = result.scalar_one_or_none()
        
        if not old_key:
            raise ValueError("API key not found or inactive")
        
        # Create new key with same settings
        new_public_key, new_secret_key, new_api_key = await self.create_api_key(
            db=db,
            user_id=user_id,
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes,
            ip_whitelist=old_key.ip_whitelist
        )
        
        # Update new key version
        new_api_key.version = old_key.version + 1
        new_api_key.metadata["rotated_from"] = old_key_id
        
        # Deprecate old key (keep for audit trail)
        old_key.is_active = False
        old_key.metadata["rotated_to"] = new_api_key.key_id
        old_key.metadata["rotated_at"] = datetime.utcnow().isoformat()
        
        await db.commit()
        
        logger.info(
            f"Rotated API key {old_key_id} to {new_api_key.key_id} "
            f"for user {user_id}"
        )
        
        return new_public_key, new_secret_key, new_api_key
    
    async def revoke_api_key(
        self,
        db: AsyncSession,
        key_id: str,
        user_id: int,
        reason: Optional[str] = None
    ):
        """Revoke an API key."""
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_id == key_id,
                    APIKey.user_id == user_id
                )
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError("API key not found")
        
        api_key.is_active = False
        api_key.metadata["revoked_at"] = datetime.utcnow().isoformat()
        if reason:
            api_key.metadata["revoke_reason"] = reason
        
        await db.commit()
        
        # Clear cache
        await self._clear_cached_key_info(key_id)
        
        logger.info(f"Revoked API key {key_id} for user {user_id}")
    
    def create_request_signature(
        self,
        secret_key: str,
        method: str,
        path: str,
        timestamp: int,
        body: Optional[str] = None
    ) -> str:
        """
        Create HMAC signature for request.
        
        Used for additional security when needed.
        """
        # Create message to sign
        message_parts = [
            method.upper(),
            path,
            str(timestamp)
        ]
        
        if body:
            body_hash = hashlib.sha256(body.encode()).hexdigest()
            message_parts.append(body_hash)
        
        message = '\n'.join(message_parts)
        
        # Create HMAC signature
        signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            getattr(hashlib, self.signature_algorithm)
        ).hexdigest()
        
        return signature
    
    def verify_request_signature(
        self,
        secret_key: str,
        signature: str,
        method: str,
        path: str,
        timestamp: int,
        body: Optional[str] = None,
        max_age_seconds: int = 300
    ) -> bool:
        """Verify request signature."""
        # Check timestamp
        current_time = int(time.time())
        if abs(current_time - timestamp) > max_age_seconds:
            return False
        
        # Calculate expected signature
        expected_signature = self.create_request_signature(
            secret_key, method, path, timestamp, body
        )
        
        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)
    
    async def get_usage_analytics(
        self,
        db: AsyncSession,
        key_id: Optional[str] = None,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get API key usage analytics."""
        # Build query
        query = select(APIKey)
        
        if key_id:
            query = query.where(APIKey.key_id == key_id)
        elif user_id:
            query = query.where(APIKey.user_id == user_id)
        else:
            raise ValueError("Either key_id or user_id must be provided")
        
        result = await db.execute(query)
        api_keys = result.scalars().all()
        
        analytics = {
            "total_keys": len(api_keys),
            "active_keys": sum(1 for k in api_keys if k.is_active),
            "expired_keys": sum(
                1 for k in api_keys
                if k.expires_at and k.expires_at < datetime.utcnow()
            ),
            "total_usage": sum(k.usage_count for k in api_keys),
            "keys_by_scope": {},
            "recent_usage": []
        }
        
        # Group by scopes
        scope_counts = {}
        for key in api_keys:
            for scope in key.scopes:
                scope_counts[scope] = scope_counts.get(scope, 0) + 1
        analytics["keys_by_scope"] = scope_counts
        
        # Get recent usage from Redis
        if key_id:
            usage_key = f"api_key_usage:{key_id}:*"
            cursor = 0
            usage_data = []
            
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=usage_key, count=100
                )
                for k in keys:
                    timestamp = k.split(':')[-1]
                    count = await redis_client.get(k)
                    usage_data.append({
                        "timestamp": int(timestamp),
                        "count": int(count or 0)
                    })
                if cursor == 0:
                    break
            
            analytics["recent_usage"] = sorted(
                usage_data,
                key=lambda x: x["timestamp"],
                reverse=True
            )[:100]
        
        return analytics
    
    # Helper methods
    
    async def _get_cached_key_info(self, key_id: str) -> Optional[APIKeyInfo]:
        """Get cached API key info."""
        cache_key = f"api_key_info:{key_id}"
        data = await redis_client.get(cache_key)
        
        if data:
            import json
            info_dict = json.loads(data)
            return APIKeyInfo(**info_dict)
        
        return None
    
    async def _cache_key_info(self, api_key_info: APIKeyInfo):
        """Cache API key info."""
        cache_key = f"api_key_info:{api_key_info.key_id}"
        
        # Convert to dict for JSON serialization
        info_dict = {
            "key_id": api_key_info.key_id,
            "user_id": api_key_info.user_id,
            "name": api_key_info.name,
            "scopes": api_key_info.scopes,
            "created_at": api_key_info.created_at.isoformat(),
            "expires_at": api_key_info.expires_at.isoformat() if api_key_info.expires_at else None,
            "last_used_at": api_key_info.last_used_at.isoformat() if api_key_info.last_used_at else None,
            "ip_whitelist": api_key_info.ip_whitelist,
            "version": api_key_info.version,
            "is_active": api_key_info.is_active,
            "usage_count": api_key_info.usage_count
        }
        
        import json
        await redis_client.setex(
            cache_key,
            self.key_cache_ttl,
            json.dumps(info_dict)
        )
    
    async def _clear_cached_key_info(self, key_id: str):
        """Clear cached API key info."""
        cache_key = f"api_key_info:{key_id}"
        await redis_client.delete(cache_key)
    
    async def _track_usage(self, key_id: str, db: AsyncSession):
        """Track API key usage."""
        # Update database
        await db.execute(
            update(APIKey)
            .where(APIKey.key_id == key_id)
            .values(
                usage_count=APIKey.usage_count + 1,
                last_used_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        # Track in Redis for analytics
        timestamp = int(time.time())
        hour_bucket = timestamp // 3600 * 3600
        usage_key = f"api_key_usage:{key_id}:{hour_bucket}"
        
        await redis_client.incr(usage_key)
        await redis_client.expire(usage_key, 86400 * 30)  # Keep 30 days
    
    async def _record_failed_attempt(self, key_id: str):
        """Record failed authentication attempt."""
        attempt_key = f"api_key_failed:{key_id}"
        
        # Increment counter
        attempts = await redis_client.incr(attempt_key)
        
        # Set expiry on first attempt
        if attempts == 1:
            await redis_client.expire(attempt_key, self.lockout_duration)
        
        # Lock if too many attempts
        if attempts >= self.max_failed_attempts:
            lock_key = f"api_key_locked:{key_id}"
            await redis_client.setex(lock_key, self.lockout_duration, "1")
            
            logger.warning(
                f"API key {key_id} locked after {attempts} failed attempts"
            )
    
    async def _is_key_locked(self, key_id: str) -> bool:
        """Check if API key is locked."""
        lock_key = f"api_key_locked:{key_id}"
        return bool(await redis_client.get(lock_key))
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"


# Global instance
api_key_security = APIKeySecurity()


# Dependency for FastAPI
async def validate_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(api_key_security.bearer_scheme),
    db: AsyncSession = Depends(get_db),
    request: Request = None
) -> APIKeyInfo:
    """FastAPI dependency for API key validation."""
    return await api_key_security.validate_api_key(
        credentials, db, request=request
    )


def require_scopes(*scopes: str):
    """Dependency to require specific scopes."""
    async def _require_scopes(
        api_key_info: APIKeyInfo = Depends(validate_api_key)
    ) -> APIKeyInfo:
        missing_scopes = set(scopes) - set(api_key_info.scopes)
        if missing_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scopes: {', '.join(missing_scopes)}"
            )
        return api_key_info
    
    return _require_scopes