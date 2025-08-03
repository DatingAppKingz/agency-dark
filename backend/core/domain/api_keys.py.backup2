"""
API Key Models and Service
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID as UUIDType
import uuid
import secrets
import hashlib

from core.database import Base


class APIKey(Base):
    """API Key for external integrations"""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Key details
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False)  # Store hashed version
    key_prefix = Column(String, nullable=False)  # First 8 chars for identification
    
    # Permissions and restrictions
    permissions = Column(JSON, default={})
    allowed_ips = Column(JSON, default=[])
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    
    # Status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime)
    usage_count = Column(Integer, default=0)
    
    # Expiration
    expires_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = relationship("Agency", back_populates="api_keys")
    user = relationship("User", back_populates="api_keys")
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new API key"""
        return f"sk_{''.join(secrets.token_urlsafe(32))}"
    
    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    @staticmethod
    def get_prefix(key: str) -> str:
        """Get key prefix for identification"""
        return key[:8]


class APIKeyService:
    """Service for managing API keys"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_api_key(
        self,
        agency_id: UUID,
        user_id: UUID,
        name: str,
        permissions: Dict[str, Any] = None,
        allowed_ips: List[str] = None,
        rate_limit: int = 1000,
        expires_in_days: Optional[int] = None
    ) -> Tuple[APIKey, str]:
        """
        Create a new API key.
        
        Returns:
            Tuple of (APIKey object, raw key string)
        """
        # Generate key
        raw_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(raw_key)
        key_prefix = APIKey.get_prefix(raw_key)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create record
        api_key = APIKey(
            agency_id=agency_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions=permissions or {},
            allowed_ips=allowed_ips or [],
            rate_limit=rate_limit,
            expires_at=expires_at
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        # Return both the object and raw key (raw key is shown only once)
        return api_key, raw_key
    
    async def validate_api_key(
        self,
        key: str,
        ip_address: Optional[str] = None
    ) -> Optional[APIKey]:
        """
        Validate an API key and return the key object if valid.
        """
        from sqlalchemy import select, and_
        
        # Hash the provided key
        key_hash = APIKey.hash_key(key)
        key_prefix = APIKey.get_prefix(key)
        
        # Look up by prefix first (for efficiency)
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_prefix == key_prefix,
                    APIKey.is_active == True
                )
            )
        )
        api_keys = result.scalars().all()
        
        # Check each key with matching prefix
        for api_key in api_keys:
            if api_key.key_hash == key_hash:
                # Found matching key, now validate it
                
                # Check expiration
                if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                    api_key.is_active = False
                    await self.db.commit()
                    return None
                
                # Check IP restrictions
                if api_key.allowed_ips and ip_address:
                    if ip_address not in api_key.allowed_ips:
                        return None
                
                # Update usage
                api_key.last_used_at = datetime.utcnow()
                api_key.usage_count += 1
                await self.db.commit()
                
                return api_key
        
        return None
    
    async def revoke_api_key(self, key_id: UUID) -> bool:
        """Revoke an API key"""
        api_key = await self.db.get(APIKey, key_id)
        if api_key:
            api_key.is_active = False
            api_key.updated_at = datetime.utcnow()
            await self.db.commit()
            return True
        return False
    
    async def list_api_keys(
        self,
        agency_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        active_only: bool = True
    ) -> List[APIKey]:
        """List API keys with filters"""
        from sqlalchemy import select, and_
        
        conditions = []
        if agency_id:
            conditions.append(APIKey.agency_id == agency_id)
        if user_id:
            conditions.append(APIKey.user_id == user_id)
        if active_only:
            conditions.append(APIKey.is_active == True)
        
        result = await self.db.execute(
            select(APIKey).where(and_(*conditions)).order_by(APIKey.created_at.desc())
        )
        
        return result.scalars().all()
    
    async def check_rate_limit(
        self,
        api_key: APIKey,
        redis_client
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if API key has exceeded rate limit.
        
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        # Use Redis for rate limiting
        key = f"rate_limit:{api_key.id}"
        current_hour = datetime.utcnow().strftime("%Y%m%d%H")
        rate_key = f"{key}:{current_hour}"
        
        # Get current count
        current = await redis_client.get(rate_key)
        count = int(current) if current else 0
        
        # Check limit
        if count >= api_key.rate_limit:
            return False, {
                "limit": api_key.rate_limit,
                "remaining": 0,
                "reset": 3600  # Reset in 1 hour
            }
        
        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 3600)  # Expire after 1 hour
        await pipe.execute()
        
        return True, {
            "limit": api_key.rate_limit,
            "remaining": api_key.rate_limit - count - 1,
            "reset": 3600
        }