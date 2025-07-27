"""
API Key management service.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from core.domain.api_key_models import (
    APIKey, APIKeyStatus, APIKeyScope,
    APIKeyAuditLog, APIKeyRotationHistory
)
from core.security.encryption import api_key_encryption, TokenEncryption
from core.exceptions import NotFoundError, ValidationError, PermissionError

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API keys."""
    
    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        user_id: str,
        agency_id: str,
        name: str,
        scopes: List[str],
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            db: Database session
            user_id: User creating the key
            agency_id: Agency the key belongs to
            name: Name for the key
            scopes: List of permission scopes
            description: Optional description
            expires_in_days: Optional expiration in days
            ip_whitelist: Optional IP whitelist
            metadata: Optional metadata
            
        Returns:
            Dictionary with key details and the actual API key
        """
        # Validate scopes
        valid_scopes = [s.value for s in APIKeyScope]
        for scope in scopes:
            if scope not in valid_scopes:
                raise ValidationError(f"Invalid scope: {scope}")
        
        # Generate key pair
        api_key, api_secret = api_key_encryption.generate_key_pair()
        
        # Create key prefix for display
        key_prefix = api_key[:12] + "..."
        
        # Hash the full key for lookups
        key_hash = TokenEncryption.hash_token(f"{api_key}:{api_secret}")
        
        # Encrypt the key data
        encrypted_data = api_key_encryption.encrypt_api_key(
            api_key=api_key,
            api_secret=api_secret,
            metadata=metadata or {}
        )
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create the key record
        api_key_record = APIKey(
            user_id=user_id,
            agency_id=agency_id,
            name=name,
            description=description,
            key_prefix=key_prefix,
            key_hash=key_hash,
            encrypted_data=encrypted_data["encrypted_data"],
            encryption_version=encrypted_data["version"],
            scopes=scopes,
            ip_whitelist=ip_whitelist or [],
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        db.add(api_key_record)
        
        # Create audit log
        audit_log = APIKeyAuditLog(
            api_key_id=api_key_record.id,
            action="created",
            performed_by_id=user_id,
            metadata={
                "name": name,
                "scopes": scopes,
                "expires_in_days": expires_in_days
            }
        )
        db.add(audit_log)
        
        await db.commit()
        await db.refresh(api_key_record)
        
        # Return the key details with the actual key (only shown once)
        return {
            "id": str(api_key_record.id),
            "name": api_key_record.name,
            "key_prefix": api_key_record.key_prefix,
            "api_key": api_key,
            "api_secret": api_secret,
            "scopes": api_key_record.scopes,
            "expires_at": api_key_record.expires_at.isoformat() if api_key_record.expires_at else None,
            "created_at": api_key_record.created_at.isoformat()
        }
    
    @staticmethod
    async def get_api_key(
        db: AsyncSession,
        key_id: str,
        user_id: str,
        agency_id: str
    ) -> APIKey:
        """Get an API key by ID."""
        result = await db.execute(
            select(APIKey)
            .where(
                and_(
                    APIKey.id == key_id,
                    APIKey.agency_id == agency_id,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
            .options(selectinload(APIKey.user))
        )
        
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise NotFoundError("API key not found")
        
        # Check permissions
        if api_key.user_id != user_id and not await APIKeyService._is_admin(db, user_id, agency_id):
            raise PermissionError("Access denied")
        
        return api_key
    
    @staticmethod
    async def list_api_keys(
        db: AsyncSession,
        user_id: str,
        agency_id: str,
        include_revoked: bool = False
    ) -> List[APIKey]:
        """List API keys for a user or agency."""
        query = select(APIKey).where(APIKey.agency_id == agency_id)
        
        # Check if user is admin
        is_admin = await APIKeyService._is_admin(db, user_id, agency_id)
        
        if not is_admin:
            # Non-admins only see their own keys
            query = query.where(APIKey.user_id == user_id)
        
        if not include_revoked:
            query = query.where(
                APIKey.status.in_([APIKeyStatus.ACTIVE, APIKeyStatus.SUSPENDED])
            )
        
        query = query.order_by(APIKey.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def rotate_api_key(
        db: AsyncSession,
        key_id: str,
        user_id: str,
        agency_id: str,
        reason: str,
        grace_period_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Rotate an API key.
        
        Args:
            db: Database session
            key_id: API key ID
            user_id: User performing rotation
            agency_id: Agency ID
            reason: Reason for rotation
            grace_period_hours: Hours before old key expires
            
        Returns:
            New key details
        """
        # Get the existing key
        api_key = await APIKeyService.get_api_key(db, key_id, user_id, agency_id)
        
        # Create rotation history with old data
        rotation_history = APIKeyRotationHistory(
            api_key_id=api_key.id,
            old_key_prefix=api_key.key_prefix,
            rotated_by_id=user_id,
            rotation_reason=reason,
            old_encrypted_data=api_key.encrypted_data,
            old_key_expires_at=datetime.utcnow() + timedelta(hours=grace_period_hours)
        )
        
        # Rotate the key
        old_encrypted = {
            "key_id": api_key.key_prefix,
            "encrypted_data": api_key.encrypted_data,
            "version": api_key.encryption_version
        }
        
        new_encrypted = api_key_encryption.rotate_api_key(old_encrypted)
        
        # Generate new key pair
        new_api_key, new_api_secret = api_key_encryption.generate_key_pair()
        new_key_prefix = new_api_key[:12] + "..."
        new_key_hash = TokenEncryption.hash_token(f"{new_api_key}:{new_api_secret}")
        
        # Update rotation history with new prefix
        rotation_history.new_key_prefix = new_key_prefix
        
        # Encrypt new key data
        encrypted_data = api_key_encryption.encrypt_api_key(
            api_key=new_api_key,
            api_secret=new_api_secret,
            metadata=api_key.metadata or {}
        )
        
        # Update the key record
        api_key.key_prefix = new_key_prefix
        api_key.key_hash = new_key_hash
        api_key.encrypted_data = encrypted_data["encrypted_data"]
        api_key.last_rotated_at = datetime.utcnow()
        api_key.rotation_count += 1
        
        db.add(rotation_history)
        
        # Create audit log
        audit_log = APIKeyAuditLog(
            api_key_id=api_key.id,
            action="rotated",
            performed_by_id=user_id,
            metadata={
                "reason": reason,
                "grace_period_hours": grace_period_hours,
                "rotation_count": api_key.rotation_count
            }
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {
            "id": str(api_key.id),
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "api_key": new_api_key,
            "api_secret": new_api_secret,
            "old_key_expires_at": rotation_history.old_key_expires_at.isoformat(),
            "rotated_at": api_key.last_rotated_at.isoformat()
        }
    
    @staticmethod
    async def revoke_api_key(
        db: AsyncSession,
        key_id: str,
        user_id: str,
        agency_id: str,
        reason: str
    ) -> None:
        """Revoke an API key."""
        api_key = await APIKeyService.get_api_key(db, key_id, user_id, agency_id)
        
        api_key.status = APIKeyStatus.REVOKED
        
        # Create audit log
        audit_log = APIKeyAuditLog(
            api_key_id=api_key.id,
            action="revoked",
            performed_by_id=user_id,
            metadata={"reason": reason}
        )
        db.add(audit_log)
        
        await db.commit()
    
    @staticmethod
    async def validate_api_key(
        db: AsyncSession,
        api_key: str,
        api_secret: str,
        required_scopes: Optional[List[str]] = None,
        ip_address: Optional[str] = None
    ) -> Optional[APIKey]:
        """
        Validate an API key and check permissions.
        
        Args:
            db: Database session
            api_key: Public API key
            api_secret: Secret API key
            required_scopes: Optional required scopes
            ip_address: Optional IP address to check
            
        Returns:
            APIKey record if valid, None otherwise
        """
        # Hash the key pair for lookup
        key_hash = TokenEncryption.hash_token(f"{api_key}:{api_secret}")
        
        # Find the key
        result = await db.execute(
            select(APIKey)
            .where(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
        )
        
        api_key_record = result.scalar_one_or_none()
        if not api_key_record:
            return None
        
        # Check expiration
        if api_key_record.expires_at and datetime.utcnow() > api_key_record.expires_at:
            api_key_record.status = APIKeyStatus.EXPIRED
            await db.commit()
            return None
        
        # Check IP whitelist
        if api_key_record.ip_whitelist and ip_address:
            if ip_address not in api_key_record.ip_whitelist:
                # Log failed attempt
                audit_log = APIKeyAuditLog(
                    api_key_id=api_key_record.id,
                    action="access_denied",
                    ip_address=ip_address,
                    metadata={"reason": "ip_not_whitelisted"}
                )
                db.add(audit_log)
                await db.commit()
                return None
        
        # Check required scopes
        if required_scopes:
            if APIKeyScope.ADMIN.value not in api_key_record.scopes:
                # Admin scope has access to everything
                for scope in required_scopes:
                    if scope not in api_key_record.scopes:
                        return None
        
        # Update usage stats
        api_key_record.usage_count += 1
        api_key_record.last_used_at = datetime.utcnow()
        if ip_address:
            api_key_record.last_ip = ip_address
        
        await db.commit()
        
        return api_key_record
    
    @staticmethod
    async def get_api_key_audit_logs(
        db: AsyncSession,
        key_id: str,
        user_id: str,
        agency_id: str,
        limit: int = 100
    ) -> List[APIKeyAuditLog]:
        """Get audit logs for an API key."""
        # Verify access
        await APIKeyService.get_api_key(db, key_id, user_id, agency_id)
        
        result = await db.execute(
            select(APIKeyAuditLog)
            .where(APIKeyAuditLog.api_key_id == key_id)
            .order_by(APIKeyAuditLog.created_at.desc())
            .limit(limit)
        )
        
        return result.scalars().all()
    
    @staticmethod
    async def cleanup_expired_keys(db: AsyncSession) -> int:
        """Clean up expired API keys."""
        result = await db.execute(
            select(APIKey)
            .where(
                and_(
                    APIKey.expires_at < datetime.utcnow(),
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
        )
        
        expired_keys = result.scalars().all()
        
        for key in expired_keys:
            key.status = APIKeyStatus.EXPIRED
            
            # Create audit log
            audit_log = APIKeyAuditLog(
                api_key_id=key.id,
                action="expired",
                metadata={"expired_at": key.expires_at.isoformat()}
            )
            db.add(audit_log)
        
        await db.commit()
        
        return len(expired_keys)
    
    @staticmethod
    async def _is_admin(db: AsyncSession, user_id: str, agency_id: str) -> bool:
        """Check if user is admin for the agency."""
        from core.domain.models import User, UserRole
        
        result = await db.execute(
            select(User)
            .where(
                and_(
                    User.id == user_id,
                    User.agency_id == agency_id,
                    User.role.in_([
                        UserRole.SUPER_ADMIN,
                        UserRole.AGENCY_OWNER,
                        UserRole.AGENCY_ADMIN
                    ])
                )
            )
        )
        
        return result.scalar_one_or_none() is not None