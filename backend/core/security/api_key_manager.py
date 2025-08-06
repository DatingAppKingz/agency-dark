"""
Enhanced API Key Management with Encryption and Security Features
"""
import secrets
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base
from core.security.encryption import api_key_encryption, encryption_service
from core.logging import get_logger
from core.redis import redis_client
from models.api_key import APIKey
from models.user import User
from models.api_key_audit import APIKeyAudit

logger = get_logger(__name__)


class SecureAPIKeyManager:
    """Manages API keys with enhanced security features"""
    
    def __init__(self):
        self.key_prefix = {
            "public": "pk_",
            "secret": "sk_",
            "test": "test_",
            "live": "live_"
        }
        self.max_keys_per_user = 10
        self.key_rotation_days = 90
    
    async def create_api_key(
        self,
        db: AsyncSession,
        user_id: int,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, APIKey]:
        """
        Create a new API key with encryption
        
        Returns:
            Tuple of (public_key, secret_key, api_key_model)
        """
        # Check key limit
        existing_count = await db.scalar(
            select(func.count(APIKey.id))
            .where(and_(APIKey.user_id == user_id, APIKey.is_active == True))
        )
        
        if existing_count >= self.max_keys_per_user:
            raise ValueError(f"Maximum of {self.max_keys_per_user} active keys allowed per user")
        
        # Generate key pair
        environment = "live" if not name.lower().startswith("test") else "test"
        public_key = f"{self.key_prefix[environment]}{secrets.token_urlsafe(24)}"
        secret_key = f"{self.key_prefix['secret']}{secrets.token_urlsafe(32)}"
        
        # Hash the secret for storage
        key_hash = self._hash_api_key(secret_key)
        
        # Encrypt additional data
        encrypted_data = api_key_encryption.encrypt_api_key(
            public_key,
            secret_key,
            metadata={
                "scopes": scopes,
                "environment": environment,
                "user_metadata": metadata or {},
                "created_by_ip": metadata.get("ip_address") if metadata else None
            }
        )
        
        # Create the API key record
        api_key = APIKey(
            user_id=user_id,
            name=name,
            key_prefix=public_key[:8],  # Store prefix for identification
            key_hash=key_hash,
            encrypted_data=encrypted_data["encrypted_data"],
            scopes=scopes,
            expires_at=expires_at or datetime.utcnow() + timedelta(days=365),
            last_used_at=None,
            is_active=True,
            environment=environment,
            metadata=metadata or {}
        )
        
        db.add(api_key)
        
        # Create audit log
        await self._create_audit_log(
            db, api_key.id, user_id, "created", 
            {"action": "api_key_created", "key_prefix": public_key[:8]}
        )
        
        await db.commit()
        await db.refresh(api_key)
        
        # Cache the key hash for fast lookup
        await self._cache_key_hash(public_key, api_key.id, key_hash)
        
        logger.info(f"Created API key {public_key[:8]}*** for user {user_id}")
        
        return public_key, secret_key, api_key
    
    async def verify_api_key(
        self,
        db: AsyncSession,
        api_key: str,
        required_scopes: Optional[List[str]] = None
    ) -> Optional[APIKey]:
        """Verify an API key and check permissions"""
        # Check cache first
        cached_data = await self._get_cached_key_data(api_key)
        
        if cached_data:
            key_id = cached_data["key_id"]
            key_hash = cached_data["key_hash"]
        else:
            # Extract prefix for database lookup
            key_prefix = api_key[:8]
            
            # Find potential matches by prefix
            api_key_record = await db.scalar(
                select(APIKey)
                .where(and_(
                    APIKey.key_prefix == key_prefix,
                    APIKey.is_active == True,
                    APIKey.expires_at > datetime.utcnow()
                ))
            )
            
            if not api_key_record:
                logger.warning(f"API key not found: {key_prefix}***")
                return None
            
            key_id = api_key_record.id
            key_hash = api_key_record.key_hash
        
        # Verify the key hash
        if not self._verify_key_hash(api_key, key_hash):
            logger.warning(f"Invalid API key hash: {api_key[:8]}***")
            await self._create_audit_log(
                db, key_id, None, "failed_verification",
                {"reason": "invalid_hash"}
            )
            return None
        
        # Load full record if from cache
        if cached_data:
            api_key_record = await db.get(APIKey, key_id)
            
        if not api_key_record:
            return None
        
        # Check expiration
        if api_key_record.expires_at <= datetime.utcnow():
            logger.warning(f"Expired API key: {api_key[:8]}***")
            await self._create_audit_log(
                db, key_id, api_key_record.user_id, "expired",
                {"expired_at": api_key_record.expires_at.isoformat()}
            )
            return None
        
        # Check scopes
        if required_scopes:
            if not self._check_scopes(api_key_record.scopes, required_scopes):
                logger.warning(f"Insufficient scopes for API key: {api_key[:8]}***")
                await self._create_audit_log(
                    db, key_id, api_key_record.user_id, "insufficient_scopes",
                    {"required": required_scopes, "available": api_key_record.scopes}
                )
                return None
        
        # Update last used timestamp
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.usage_count += 1
        
        # Check if rotation is needed
        if self._needs_rotation(api_key_record):
            await self._mark_for_rotation(api_key_record.id)
        
        await db.commit()
        
        # Cache the verification result
        await self._cache_key_hash(api_key, key_id, key_hash)
        
        return api_key_record
    
    async def rotate_api_key(
        self,
        db: AsyncSession,
        api_key_id: int,
        user_id: int
    ) -> Tuple[str, str]:
        """Rotate an API key to a new secret"""
        api_key_record = await db.get(APIKey, api_key_id)
        
        if not api_key_record or api_key_record.user_id != user_id:
            raise ValueError("API key not found or unauthorized")
        
        # Decrypt current data
        encrypted_data = {
            "encrypted_data": api_key_record.encrypted_data,
            "version": "1.0"
        }
        current_data = api_key_encryption.decrypt_api_key(encrypted_data)
        
        # Generate new keys
        new_public_key = f"{api_key_record.key_prefix}{secrets.token_urlsafe(24)}"
        new_secret_key = f"{self.key_prefix['secret']}{secrets.token_urlsafe(32)}"
        
        # Update encryption
        new_encrypted_data = api_key_encryption.encrypt_api_key(
            new_public_key,
            new_secret_key,
            metadata=current_data.get("metadata", {})
        )
        
        # Update record
        api_key_record.key_prefix = new_public_key[:8]
        api_key_record.key_hash = self._hash_api_key(new_secret_key)
        api_key_record.encrypted_data = new_encrypted_data["encrypted_data"]
        api_key_record.rotated_at = datetime.utcnow()
        api_key_record.rotation_count += 1
        
        # Clear old cache
        await self._clear_key_cache(current_data["api_key"])
        
        # Create audit log
        await self._create_audit_log(
            db, api_key_id, user_id, "rotated",
            {"rotation_count": api_key_record.rotation_count}
        )
        
        await db.commit()
        
        logger.info(f"Rotated API key {api_key_id} for user {user_id}")
        
        return new_public_key, new_secret_key
    
    async def revoke_api_key(
        self,
        db: AsyncSession,
        api_key_id: int,
        user_id: int,
        reason: str = "user_requested"
    ) -> bool:
        """Revoke an API key"""
        api_key_record = await db.get(APIKey, api_key_id)
        
        if not api_key_record or api_key_record.user_id != user_id:
            return False
        
        api_key_record.is_active = False
        api_key_record.revoked_at = datetime.utcnow()
        api_key_record.revocation_reason = reason
        
        # Clear cache
        await self._clear_key_cache_by_id(api_key_id)
        
        # Create audit log
        await self._create_audit_log(
            db, api_key_id, user_id, "revoked",
            {"reason": reason}
        )
        
        await db.commit()
        
        logger.info(f"Revoked API key {api_key_id} for user {user_id}: {reason}")
        
        return True
    
    async def list_user_keys(
        self,
        db: AsyncSession,
        user_id: int,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """List all API keys for a user"""
        query = select(APIKey).where(APIKey.user_id == user_id)
        
        if not include_inactive:
            query = query.where(APIKey.is_active == True)
        
        query = query.order_by(APIKey.created_at.desc())
        
        result = await db.execute(query)
        api_keys = result.scalars().all()
        
        # Prepare safe response
        keys_data = []
        for key in api_keys:
            # Decrypt to get metadata
            try:
                encrypted_data = {
                    "encrypted_data": key.encrypted_data,
                    "version": "1.0"
                }
                decrypted = api_key_encryption.decrypt_api_key(encrypted_data)
                metadata = decrypted.get("metadata", {})
            except:
                metadata = {}
            
            keys_data.append({
                "id": key.id,
                "name": key.name,
                "key_prefix": key.key_prefix + "***",
                "scopes": key.scopes,
                "environment": key.environment,
                "created_at": key.created_at,
                "expires_at": key.expires_at,
                "last_used_at": key.last_used_at,
                "usage_count": key.usage_count,
                "is_active": key.is_active,
                "needs_rotation": self._needs_rotation(key),
                "metadata": metadata.get("user_metadata", {})
            })
        
        return keys_data
    
    async def get_key_audit_log(
        self,
        db: AsyncSession,
        api_key_id: int,
        user_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get audit log for an API key"""
        # Verify ownership
        api_key = await db.get(APIKey, api_key_id)
        if not api_key or api_key.user_id != user_id:
            return []
        
        query = (
            select(APIKeyAudit)
            .where(APIKeyAudit.api_key_id == api_key_id)
            .order_by(APIKeyAudit.created_at.desc())
            .limit(limit)
        )
        
        result = await db.execute(query)
        audits = result.scalars().all()
        
        return [
            {
                "action": audit.action,
                "details": audit.details,
                "ip_address": audit.ip_address,
                "user_agent": audit.user_agent,
                "created_at": audit.created_at
            }
            for audit in audits
        ]
    
    def _hash_api_key(self, api_key: str) -> str:
        """Create a secure hash of an API key"""
        # Use PBKDF2 with SHA256
        salt = b'agencydark_api_key_salt_v1'  # In production, use per-key salt
        key_bytes = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
        return key_bytes.hex()
    
    def _verify_key_hash(self, api_key: str, stored_hash: str) -> bool:
        """Verify an API key against its hash"""
        computed_hash = self._hash_api_key(api_key)
        return secrets.compare_digest(computed_hash, stored_hash)
    
    def _check_scopes(self, available_scopes: List[str], required_scopes: List[str]) -> bool:
        """Check if available scopes satisfy requirements"""
        if "*" in available_scopes:
            return True
        
        for scope in required_scopes:
            if scope not in available_scopes:
                # Check for wildcard scopes (e.g., "read:*" covers "read:users")
                scope_parts = scope.split(":")
                if len(scope_parts) > 1:
                    wildcard = f"{scope_parts[0]}:*"
                    if wildcard not in available_scopes:
                        return False
                else:
                    return False
        
        return True
    
    def _needs_rotation(self, api_key: APIKey) -> bool:
        """Check if an API key needs rotation"""
        if not api_key.rotated_at:
            # Never rotated, check creation date
            age_days = (datetime.utcnow() - api_key.created_at).days
        else:
            # Check last rotation
            age_days = (datetime.utcnow() - api_key.rotated_at).days
        
        return age_days >= self.key_rotation_days
    
    async def _cache_key_hash(self, api_key: str, key_id: int, key_hash: str):
        """Cache API key hash for fast lookup"""
        cache_key = f"api_key:{api_key[:16]}"  # Use prefix for security
        cache_data = {
            "key_id": key_id,
            "key_hash": key_hash
        }
        
        # Cache for 1 hour
        await redis_client.setex(
            cache_key,
            3600,
            json.dumps(cache_data)
        )
    
    async def _get_cached_key_data(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get cached API key data"""
        cache_key = f"api_key:{api_key[:16]}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        return None
    
    async def _clear_key_cache(self, api_key: str):
        """Clear API key from cache"""
        cache_key = f"api_key:{api_key[:16]}"
        await redis_client.delete(cache_key)
    
    async def _clear_key_cache_by_id(self, key_id: int):
        """Clear API key cache by ID"""
        # This would require reverse lookup - in production, maintain a mapping
        pattern = "api_key:*"
        # For now, we'll clear on next verification
        pass
    
    async def _mark_for_rotation(self, key_id: int):
        """Mark an API key for rotation notification"""
        await redis_client.sadd("api_keys:needs_rotation", str(key_id))
    
    async def _create_audit_log(
        self,
        db: AsyncSession,
        api_key_id: int,
        user_id: Optional[int],
        action: str,
        details: Dict[str, Any]
    ):
        """Create an audit log entry"""
        audit = APIKeyAudit(
            api_key_id=api_key_id,
            user_id=user_id,
            action=action,
            details=details,
            ip_address=details.get("ip_address"),
            user_agent=details.get("user_agent")
        )
        db.add(audit)


# Global instance
secure_api_key_manager = SecureAPIKeyManager()


import json