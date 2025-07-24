"""
API key management and rotation system.
"""
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Boolean, Index, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid
import secrets
import hashlib
from cryptography.fernet import Fernet
import base64
import json

from core.database import Base
from core.redis import redis_client
from core.config import settings
from core.audit import audit_logger, AuditEventType
import logging

logger = logging.getLogger(__name__)


class APIKey(Base):
    """API key model for external integrations."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Key details
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    key_hash = Column(String(128), nullable=False, unique=True)  # SHA-512 hash
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    
    # Owner
    agency_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    
    # Permissions
    scopes = Column(JSON, default=list)  # List of allowed scopes
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    ip_whitelist = Column(JSON, default=list)  # Allowed IP addresses
    
    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    last_used_ip = Column(String(45))
    usage_count = Column(Integer, default=0)
    
    # Rotation
    expires_at = Column(DateTime(timezone=True))
    rotated_from = Column(UUID(as_uuid=True))  # Previous key ID
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_api_key_agency', 'agency_id'),
        Index('idx_api_key_prefix', 'key_prefix'),
        Index('idx_api_key_active', 'is_active'),
    )


class APIKeyScope(str):
    """Available API key scopes."""
    READ_ANALYTICS = "analytics:read"
    WRITE_ANALYTICS = "analytics:write"
    READ_FANS = "fans:read"
    WRITE_FANS = "fans:write"
    READ_MODELS = "models:read"
    WRITE_MODELS = "models:write"
    WEBHOOK = "webhook:receive"
    SYNC = "sync:perform"
    FINANCIAL = "financial:access"


class APIKeyManager:
    """Service for managing API keys."""
    
    def __init__(self):
        # Generate encryption key from secret
        key = base64.urlsafe_b64encode(settings.SECRET_KEY[:32].encode().ljust(32, b'0'))
        self.cipher = Fernet(key)
    
    async def create_api_key(
        self,
        name: str,
        agency_id: UUID,
        created_by: UUID,
        scopes: List[str],
        description: Optional[str] = None,
        expires_in_days: int = 365,
        rate_limit: int = 1000,
        ip_whitelist: Optional[List[str]] = None,
        db: AsyncSession = None
    ) -> Dict[str, any]:
        """Create a new API key."""
        # Generate secure API key
        raw_key = self._generate_api_key()
        key_hash = self._hash_key(raw_key)
        key_prefix = raw_key[:8]
        
        # Create database entry
        api_key = APIKey(
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            agency_id=agency_id,
            created_by=created_by,
            scopes=scopes,
            rate_limit=rate_limit,
            ip_whitelist=ip_whitelist or [],
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        # Cache key details
        await self._cache_key(raw_key, api_key)
        
        # Log creation
        await audit_logger.log_event(
            AuditEventType.API_KEY_USED,
            user_id=created_by,
            target_type="api_key",
            target_id=str(api_key.id),
            description=f"API key '{name}' created",
            agency_id=agency_id,
            db=db
        )
        
        return {
            "id": api_key.id,
            "key": raw_key,  # Only returned once
            "name": name,
            "prefix": key_prefix,
            "scopes": scopes,
            "expires_at": api_key.expires_at
        }
    
    async def validate_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None,
        ip_address: Optional[str] = None,
        db: AsyncSession = None
    ) -> Optional[APIKey]:
        """Validate an API key and check permissions."""
        # Check cache first
        cached = await redis_client.get(f"api_key:{api_key}")
        if cached == "invalid":
            return None
        
        # Hash the key
        key_hash = self._hash_key(api_key)
        
        # Look up in database
        result = await db.execute(
            select(APIKey).filter(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True
                )
            )
        )
        key_record = result.scalar_one_or_none()
        
        if not key_record:
            await redis_client.setex(f"api_key:{api_key}", 300, "invalid")
            return None
        
        # Check expiration
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            await self._deactivate_key(key_record, db)
            return None
        
        # Check IP whitelist
        if key_record.ip_whitelist and ip_address:
            if ip_address not in key_record.ip_whitelist:
                logger.warning(f"API key {key_record.key_prefix} used from unauthorized IP: {ip_address}")
                return None
        
        # Check scope
        if required_scope and required_scope not in key_record.scopes:
            return None
        
        # Update usage
        key_record.last_used_at = datetime.utcnow()
        key_record.last_used_ip = ip_address
        key_record.usage_count += 1
        
        await db.commit()
        
        # Cache valid key
        await self._cache_key(api_key, key_record)
        
        return key_record
    
    async def rotate_api_key(
        self,
        key_id: UUID,
        rotated_by: UUID,
        db: AsyncSession
    ) -> Dict[str, any]:
        """Rotate an API key."""
        # Get existing key
        result = await db.execute(
            select(APIKey).filter(APIKey.id == key_id)
        )
        old_key = result.scalar_one_or_none()
        
        if not old_key:
            raise ValueError("API key not found")
        
        # Deactivate old key
        old_key.is_active = False
        
        # Create new key with same settings
        new_key_data = await self.create_api_key(
            name=f"{old_key.name} (Rotated)",
            agency_id=old_key.agency_id,
            created_by=rotated_by,
            scopes=old_key.scopes,
            description=f"Rotated from {old_key.key_prefix}",
            rate_limit=old_key.rate_limit,
            ip_whitelist=old_key.ip_whitelist,
            db=db
        )
        
        # Link to old key
        new_key_id = new_key_data["id"]
        result = await db.execute(
            select(APIKey).filter(APIKey.id == new_key_id)
        )
        new_key = result.scalar_one_or_none()
        new_key.rotated_from = old_key.id
        
        await db.commit()
        
        # Log rotation
        await audit_logger.log_event(
            AuditEventType.API_KEY_USED,
            user_id=rotated_by,
            target_type="api_key",
            target_id=str(new_key.id),
            description=f"API key rotated from {old_key.key_prefix} to {new_key.key_prefix}",
            agency_id=old_key.agency_id,
            db=db
        )
        
        return new_key_data
    
    async def list_api_keys(
        self,
        agency_id: UUID,
        include_inactive: bool = False,
        db: AsyncSession = None
    ) -> List[APIKey]:
        """List API keys for an agency."""
        query = select(APIKey).filter(APIKey.agency_id == agency_id)
        
        if not include_inactive:
            query = query.filter(APIKey.is_active == True)
        
        query = query.order_by(APIKey.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def revoke_api_key(
        self,
        key_id: UUID,
        revoked_by: UUID,
        db: AsyncSession
    ):
        """Revoke an API key."""
        result = await db.execute(
            select(APIKey).filter(APIKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError("API key not found")
        
        await self._deactivate_key(api_key, db)
        
        # Log revocation
        await audit_logger.log_event(
            AuditEventType.API_KEY_USED,
            user_id=revoked_by,
            target_type="api_key",
            target_id=str(api_key.id),
            description=f"API key '{api_key.name}' revoked",
            agency_id=api_key.agency_id,
            db=db
        )
    
    async def check_rate_limit(
        self,
        api_key: APIKey,
        ip_address: str
    ) -> bool:
        """Check if API key has exceeded rate limit."""
        key = f"rate_limit:api_key:{api_key.id}:{ip_address}"
        
        current = await redis_client.incr(key)
        
        if current == 1:
            # First request in window
            await redis_client.expire(key, 3600)  # 1 hour window
        
        return current <= api_key.rate_limit
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key."""
        # Format: agdk_{random_string}
        random_part = secrets.token_urlsafe(32)
        return f"agdk_{random_part}"
    
    def _hash_key(self, api_key: str) -> str:
        """Hash an API key."""
        return hashlib.sha512(api_key.encode()).hexdigest()
    
    async def _cache_key(self, raw_key: str, key_record: APIKey):
        """Cache API key details."""
        cache_data = {
            "id": str(key_record.id),
            "agency_id": str(key_record.agency_id),
            "scopes": key_record.scopes,
            "rate_limit": key_record.rate_limit,
            "ip_whitelist": key_record.ip_whitelist
        }
        
        # Cache for 1 hour
        await redis_client.setex(
            f"api_key:{raw_key}",
            3600,
            json.dumps(cache_data)
        )
    
    async def _deactivate_key(self, api_key: APIKey, db: AsyncSession):
        """Deactivate an API key."""
        api_key.is_active = False
        
        # Clear from cache
        # Note: We can't clear by raw key, so we mark as invalid
        await redis_client.setex(f"api_key:invalid:{api_key.id}", 86400, "1")
        
        await db.commit()


# Global API key manager instance
api_key_manager = APIKeyManager()