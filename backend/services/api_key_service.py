"""API Key management service with encryption and validation."""

import secrets
import string
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload

from services.encryption_service import encryption_service
from core.logger import get_logger
from models.api_key import APIKey, APIKeyProvider, APIKeyStatus
from models.user import User
from core.errors import NotFoundError, ValidationError as AppValidationError, AuthorizationError

logger = get_logger(__name__)


class APIKeyService:
    """Service for managing encrypted API keys."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = encryption_service
    
    @staticmethod
    def generate_key_value(length: int = 32) -> str:
        """Generate a secure random API key."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def create_api_key(
        self,
        user: User,
        provider: APIKeyProvider,
        name: str,
        key_value: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> APIKey:
        """
        Create a new encrypted API key.
        
        Args:
            user: User creating the key
            provider: API provider (onlyfans, stripe, etc.)
            name: Display name for the key
            key_value: The actual API key to encrypt
            metadata: Optional metadata for the key
            
        Returns:
            Created APIKey instance
        """
        # Validate provider
        if provider not in APIKeyProvider:
            raise AppValidationError(f"Invalid provider: {provider}")
        
        # Check if key already exists for this provider
        existing = await self.db.scalar(
            select(APIKey).where(
                and_(
                    APIKey.agency_id == user.agency_id,
                    APIKey.provider == provider,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
        )
        
        if existing:
            raise AppValidationError(f"Active API key already exists for {provider.value}")
        
        # Encrypt the key value
        encrypted_value = self.encryption.encrypt(key_value)
        
        # Create key prefix for display (first 8 chars)
        key_prefix = key_value[:8] if len(key_value) >= 8 else key_value
        
        # Create the API key
        api_key = APIKey(
            agency_id=user.agency_id,
            user_id=user.id,
            provider=provider,
            name=name,
            key_prefix=key_prefix,
            encrypted_value=encrypted_value,
            status=APIKeyStatus.ACTIVE,
            key_metadata=metadata or {},
            created_by=user.id
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.log_business_event(
            "api_key_created",
            "APIKey",
            api_key.id,
            provider=provider.value,
            agency_id=user.agency_id
        )
        
        return api_key
    
    async def get_api_key(
        self,
        key_id: int,
        user: User,
        decrypt: bool = False
    ) -> APIKey:
        """
        Get an API key by ID.
        
        Args:
            key_id: API key ID
            user: User requesting the key
            decrypt: Whether to decrypt the key value
            
        Returns:
            APIKey instance
        """
        stmt = select(APIKey).where(APIKey.id == key_id)
        
        # Apply agency filter for non-super admins
        if user.role != "super_admin":
            stmt = stmt.where(APIKey.agency_id == user.agency_id)
        
        api_key = await self.db.scalar(stmt)
        if not api_key:
            raise NotFoundError("API Key", key_id)
        
        # Decrypt if requested and user has permission
        if decrypt:
            if user.role not in ["super_admin", "agency_owner", "agency_admin"]:
                raise AuthorizationError("Insufficient permissions to decrypt API key")
            
            # Set decrypted value temporarily (don't save to DB)
            api_key.decrypted_value = self.encryption.decrypt(api_key.encrypted_value)
        
        return api_key
    
    async def list_api_keys(
        self,
        user: User,
        provider: Optional[APIKeyProvider] = None,
        status: Optional[APIKeyStatus] = None
    ) -> List[APIKey]:
        """List API keys with optional filters."""
        stmt = select(APIKey)
        
        # Apply agency filter
        if user.role != "super_admin":
            stmt = stmt.where(APIKey.agency_id == user.agency_id)
        
        # Apply filters
        if provider:
            stmt = stmt.where(APIKey.provider == provider)
        
        if status:
            stmt = stmt.where(APIKey.status == status)
        
        # Order by created_at desc
        stmt = stmt.order_by(APIKey.created_at.desc())
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update_api_key(
        self,
        key_id: int,
        user: User,
        name: Optional[str] = None,
        key_value: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> APIKey:
        """Update an API key."""
        api_key = await self.get_api_key(key_id, user)
        
        # Check permissions
        if user.role not in ["super_admin", "agency_owner", "agency_admin"]:
            raise AuthorizationError("Insufficient permissions to update API key")
        
        # Update fields
        if name is not None:
            api_key.name = name
        
        if key_value is not None:
            # Re-encrypt with new value
            api_key.encrypted_value = self.encryption.encrypt(key_value)
            api_key.key_prefix = key_value[:8] if len(key_value) >= 8 else key_value
            api_key.last_rotated_at = datetime.utcnow()
        
        if metadata is not None:
            api_key.key_metadata = metadata
        
        api_key.updated_by = user.id
        
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.log_business_event(
            "api_key_updated",
            "APIKey",
            api_key.id,
            provider=api_key.provider.value
        )
        
        return api_key
    
    async def rotate_api_key(
        self,
        key_id: int,
        user: User,
        new_key_value: str
    ) -> APIKey:
        """Rotate an API key with a new value."""
        return await self.update_api_key(key_id, user, key_value=new_key_value)
    
    async def deactivate_api_key(
        self,
        key_id: int,
        user: User,
        reason: Optional[str] = None
    ) -> APIKey:
        """Deactivate an API key."""
        api_key = await self.get_api_key(key_id, user)
        
        # Check permissions
        if user.role not in ["super_admin", "agency_owner", "agency_admin"]:
            raise AuthorizationError("Insufficient permissions to deactivate API key")
        
        api_key.status = APIKeyStatus.INACTIVE
        api_key.deactivated_at = datetime.utcnow()
        api_key.updated_by = user.id
        
        if reason:
            api_key.key_metadata["deactivation_reason"] = reason
        
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.log_business_event(
            "api_key_deactivated",
            "APIKey",
            api_key.id,
            provider=api_key.provider.value,
            reason=reason
        )
        
        return api_key
    
    async def validate_api_key(
        self,
        key_id: int,
        user: User,
        test_endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate an API key by testing it against the provider.
        
        Args:
            key_id: API key ID
            user: User requesting validation
            test_endpoint: Optional endpoint to test
            
        Returns:
            Validation result dict
        """
        api_key = await self.get_api_key(key_id, user, decrypt=True)
        
        # Update last validated timestamp
        api_key.last_validated_at = datetime.utcnow()
        await self.db.commit()
        
        # Provider-specific validation
        if api_key.provider == APIKeyProvider.ONLYFANS:
            return await self._validate_onlyfans_key(api_key.decrypted_value)
        elif api_key.provider == APIKeyProvider.STRIPE:
            return await self._validate_stripe_key(api_key.decrypted_value)
        elif api_key.provider == APIKeyProvider.INFLOW:
            return await self._validate_inflow_key(api_key.decrypted_value)
        else:
            return {
                "valid": True,
                "message": f"Validation not implemented for {api_key.provider.value}",
                "provider": api_key.provider.value
            }
    
    async def _validate_onlyfans_key(self, key: str) -> Dict[str, Any]:
        """Validate OnlyFans API key."""
        # TODO: Implement actual OnlyFans API validation
        return {
            "valid": True,
            "message": "OnlyFans API key validation not yet implemented",
            "provider": "onlyfans"
        }
    
    async def _validate_stripe_key(self, key: str) -> Dict[str, Any]:
        """Validate Stripe API key."""
        # TODO: Implement actual Stripe API validation
        return {
            "valid": True,
            "message": "Stripe API key validation not yet implemented",
            "provider": "stripe"
        }
    
    async def _validate_inflow_key(self, key: str) -> Dict[str, Any]:
        """Validate Inflow API key."""
        # TODO: Implement actual Inflow API validation
        return {
            "valid": True,
            "message": "Inflow API key validation not yet implemented",
            "provider": "inflow"
        }
    
    async def record_usage(
        self,
        key_id: int,
        endpoint: str,
        success: bool,
        response_time_ms: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record API key usage for tracking."""
        # Update last used timestamp
        await self.db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(last_used_at=datetime.utcnow())
        )
        await self.db.commit()
        
        # TODO: Implement detailed usage tracking in api_usage table
        logger.debug(
            f"API key {key_id} used",
            extra={
                "endpoint": endpoint,
                "success": success,
                "response_time_ms": response_time_ms,
                "metadata": metadata
            }
        )