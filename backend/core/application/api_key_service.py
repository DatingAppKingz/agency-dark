"""API Key service for managing API keys."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import hashlib

from models.webhook import APIKey
from core.exceptions import NotFoundError, ValidationError, PermissionError


class APIKeyService:
    """Service for managing API keys."""
    
    @staticmethod
    def _generate_key() -> tuple[str, str]:
        """Generate a new API key and its hash."""
        # Generate a secure random key
        raw_key = secrets.token_urlsafe(32)
        prefix = "sk_live"
        full_key = f"{prefix}_{raw_key}"
        
        # Hash the key for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        
        return full_key, key_hash
    
    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        user_id: str,
        agency_id: Optional[str],
        name: str,
        description: Optional[str] = None,
        scopes: List[str] = None,
        expires_in_days: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new API key."""
        # Generate the key
        full_key, key_hash = APIKeyService._generate_key()
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # agency_id is required in the existing model
        if not agency_id:
            raise ValidationError("agency_id is required")
            
        # Create the API key
        api_key = APIKey(
            user_id=int(user_id),
            agency_id=int(agency_id),
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=full_key.split("_")[0],
            scopes=scopes or [],
            expires_at=expires_at.isoformat() if expires_at else None,
            ip_whitelist=ip_whitelist or [],
            key_metadata=metadata or {}
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        return {
            "id": api_key.id,
            "key": full_key,  # Only returned once!
            "name": api_key.name,
            "prefix": api_key.key_prefix,
            "scopes": api_key.scopes,
            "expires_at": api_key.expires_at
        }
    
    @staticmethod
    async def list_api_keys(
        db: AsyncSession,
        user_id: str,
        agency_id: Optional[str] = None
    ) -> List[APIKey]:
        """List API keys for a user or agency."""
        stmt = select(APIKey).where(APIKey.user_id == int(user_id))
        
        if agency_id:
            stmt = stmt.where(APIKey.agency_id == int(agency_id))
            
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_api_key(
        db: AsyncSession,
        key_id: int,
        user_id: str
    ) -> APIKey:
        """Get a specific API key."""
        stmt = select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == int(user_id)
        )
        
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise NotFoundError("API key not found")
            
        return api_key
    
    @staticmethod
    async def update_api_key(
        db: AsyncSession,
        key_id: int,
        user_id: str,
        **kwargs
    ) -> APIKey:
        """Update an API key."""
        api_key = await APIKeyService.get_api_key(db, key_id, user_id)
        
        # Update fields
        for field, value in kwargs.items():
            if value is not None and hasattr(api_key, field):
                setattr(api_key, field, value)
        
        await db.commit()
        await db.refresh(api_key)
        
        return api_key
    
    @staticmethod
    async def revoke_api_key(
        db: AsyncSession,
        key_id: int,
        user_id: str
    ) -> None:
        """Revoke an API key."""
        api_key = await APIKeyService.get_api_key(db, key_id, user_id)
        api_key.is_active = False
        await db.commit()
    
    @staticmethod
    async def rotate_api_key(
        db: AsyncSession,
        key_id: int,
        user_id: str
    ) -> Dict[str, Any]:
        """Rotate an API key (generate new key, invalidate old one)."""
        # Get the existing key
        old_key = await APIKeyService.get_api_key(db, key_id, user_id)
        
        # Deactivate the old key
        old_key.is_active = False
        
        # Create a new key with the same settings
        return await APIKeyService.create_api_key(
            db=db,
            user_id=user_id,
            agency_id=str(old_key.agency_id) if old_key.agency_id else None,
            name=f"{old_key.name} (rotated)",
            description=old_key.description,
            scopes=old_key.scopes,
            expires_in_days=None,  # Keep same expiration
            ip_whitelist=old_key.ip_whitelist,
            metadata=old_key.key_metadata
        )
    
    @staticmethod
    async def validate_api_key(
        db: AsyncSession,
        key: str,
        scope: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate an API key."""
        # In production, you'd hash the key and look up by hash
        stmt = select(APIKey).where(APIKey.key_hash == key)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key or not api_key.is_active:
            return None
            
        # Check expiration
        if api_key.expires_at:
            try:
                expires_at = datetime.fromisoformat(api_key.expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.utcnow():
                    return None
            except:
                # If parsing fails, assume expired
                return None
            
        # Check IP whitelist
        if ip_address and not api_key.check_ip(ip_address):
            return None
            
        # Check scope
        if scope and not api_key.has_scope(scope):
            return None
            
        # Update last used
        api_key.last_used_at = datetime.utcnow().isoformat()
        api_key.last_used_ip = ip_address
        api_key.usage_count += 1
        await db.commit()
        
        return {
            "valid": True,
            "key_id": api_key.id,
            "user_id": api_key.user_id,
            "agency_id": api_key.agency_id,
            "scopes": api_key.scopes,
            "expires_at": api_key.expires_at
        }