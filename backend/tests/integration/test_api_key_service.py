"""
Integration tests for API key service.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from core.application.api_key_service import APIKeyService
from core.domain.api_key_models import APIKeyStatus, APIKeyScope
from core.domain.models import User, Agency
from core.exceptions import NotFoundError, ValidationError, PermissionError


class TestAPIKeyService:
    
    @pytest.mark.asyncio
    async def test_create_api_key(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test creating an API key."""
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Test API Key",
            description="Test key for integration testing",
            scopes=[APIKeyScope.READ_ANALYTICS.value, APIKeyScope.READ_FINANCIAL.value],
            expires_in_days=30,
            ip_whitelist=["192.168.1.1"],
            metadata={"test": True}
        )
        
        assert result["name"] == "Test API Key"
        assert result["api_key"].startswith("ak_")
        assert result["api_secret"].startswith("sk_")
        assert len(result["scopes"]) == 2
        assert result["expires_at"] is not None
        
        # Verify key was saved to database
        saved_key = await APIKeyService.get_api_key(
            db=db_session,
            key_id=result["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id)
        )
        
        assert saved_key.name == "Test API Key"
        assert saved_key.description == "Test key for integration testing"
        assert saved_key.ip_whitelist == ["192.168.1.1"]
    
    @pytest.mark.asyncio
    async def test_create_api_key_invalid_scope(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test creating API key with invalid scope."""
        with pytest.raises(ValidationError, match="Invalid scope"):
            await APIKeyService.create_api_key(
                db=db_session,
                user_id=str(test_user.id),
                agency_id=str(test_agency.id),
                name="Invalid Key",
                scopes=["invalid:scope"]
            )
    
    @pytest.mark.asyncio
    async def test_list_api_keys(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test listing API keys."""
        # Create multiple keys
        for i in range(3):
            await APIKeyService.create_api_key(
                db=db_session,
                user_id=str(test_user.id),
                agency_id=str(test_agency.id),
                name=f"Key {i}",
                scopes=[APIKeyScope.READ_ANALYTICS.value]
            )
        
        # List keys
        keys = await APIKeyService.list_api_keys(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id)
        )
        
        assert len(keys) == 3
        assert all(key.status == APIKeyStatus.ACTIVE for key in keys)
    
    @pytest.mark.asyncio
    async def test_rotate_api_key(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test rotating an API key."""
        # Create a key
        original = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Rotation Test",
            scopes=[APIKeyScope.ADMIN.value]
        )
        
        original_secret = original["api_secret"]
        
        # Rotate the key
        rotated = await APIKeyService.rotate_api_key(
            db=db_session,
            key_id=original["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            reason="Security rotation test",
            grace_period_hours=24
        )
        
        assert rotated["id"] == original["id"]
        assert rotated["api_key"] != original["api_key"]  # New public key
        assert rotated["api_secret"] != original_secret  # New secret
        assert rotated["old_key_expires_at"] is not None
        
        # Verify rotation was recorded
        key = await APIKeyService.get_api_key(
            db=db_session,
            key_id=original["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id)
        )
        
        assert key.rotation_count == 1
        assert key.last_rotated_at is not None
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test revoking an API key."""
        # Create a key
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Revoke Test",
            scopes=[APIKeyScope.READ_MODELS.value]
        )
        
        # Revoke it
        await APIKeyService.revoke_api_key(
            db=db_session,
            key_id=result["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            reason="Testing revocation"
        )
        
        # Try to get it - should fail since it's revoked
        with pytest.raises(NotFoundError):
            await APIKeyService.get_api_key(
                db=db_session,
                key_id=result["id"],
                user_id=str(test_user.id),
                agency_id=str(test_agency.id)
            )
    
    @pytest.mark.asyncio
    async def test_validate_api_key(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test validating an API key."""
        # Create a key
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Validation Test",
            scopes=[APIKeyScope.READ_ANALYTICS.value, APIKeyScope.READ_FINANCIAL.value]
        )
        
        # Validate with correct credentials
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"]
        )
        
        assert validated is not None
        assert str(validated.id) == result["id"]
        assert validated.usage_count == 1
        
        # Validate with required scopes
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"],
            required_scopes=[APIKeyScope.READ_ANALYTICS.value]
        )
        assert validated is not None
        
        # Validate with missing scope
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"],
            required_scopes=[APIKeyScope.WRITE_MODELS.value]
        )
        assert validated is None  # Missing required scope
        
        # Validate with wrong credentials
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret="wrong_secret"
        )
        assert validated is None
    
    @pytest.mark.asyncio
    async def test_api_key_expiration(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test API key expiration."""
        # Create a key that expires immediately
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Expiring Key",
            scopes=[APIKeyScope.READ_ANALYTICS.value],
            expires_in_days=0  # Will be set to minimum 1 day
        )
        
        # Manually set expiration to past
        from core.domain.api_key_models import APIKey
        key = await db_session.get(APIKey, result["id"])
        key.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()
        
        # Try to validate - should fail
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"]
        )
        
        assert validated is None
        
        # Key should be marked as expired
        await db_session.refresh(key)
        assert key.status == APIKeyStatus.EXPIRED
    
    @pytest.mark.asyncio
    async def test_api_key_ip_whitelist(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test API key IP whitelist."""
        # Create a key with IP whitelist
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="IP Restricted Key",
            scopes=[APIKeyScope.READ_ANALYTICS.value],
            ip_whitelist=["192.168.1.1", "10.0.0.1"]
        )
        
        # Validate from allowed IP
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"],
            ip_address="192.168.1.1"
        )
        assert validated is not None
        
        # Validate from non-allowed IP
        validated = await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"],
            ip_address="192.168.1.2"
        )
        assert validated is None
    
    @pytest.mark.asyncio
    async def test_api_key_audit_logs(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test API key audit logging."""
        # Create a key
        result = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Audit Test",
            scopes=[APIKeyScope.READ_ANALYTICS.value]
        )
        
        # Perform some actions
        await APIKeyService.validate_api_key(
            db=db_session,
            api_key=result["api_key"],
            api_secret=result["api_secret"]
        )
        
        await APIKeyService.revoke_api_key(
            db=db_session,
            key_id=result["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            reason="Audit test"
        )
        
        # Get audit logs
        logs = await APIKeyService.get_api_key_audit_logs(
            db=db_session,
            key_id=result["id"],
            user_id=str(test_user.id),
            agency_id=str(test_agency.id)
        )
        
        assert len(logs) >= 2
        actions = [log.action for log in logs]
        assert "created" in actions
        assert "revoked" in actions
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_keys(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_agency: Agency
    ):
        """Test cleaning up expired keys."""
        # Create keys with different expiration
        active_key = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Active Key",
            scopes=[APIKeyScope.READ_ANALYTICS.value],
            expires_in_days=30
        )
        
        expired_key = await APIKeyService.create_api_key(
            db=db_session,
            user_id=str(test_user.id),
            agency_id=str(test_agency.id),
            name="Expired Key",
            scopes=[APIKeyScope.READ_ANALYTICS.value],
            expires_in_days=1
        )
        
        # Manually expire the second key
        from core.domain.api_key_models import APIKey
        key = await db_session.get(APIKey, expired_key["id"])
        key.expires_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()
        
        # Run cleanup
        count = await APIKeyService.cleanup_expired_keys(db_session)
        
        assert count == 1
        
        # Verify expired key is marked
        await db_session.refresh(key)
        assert key.status == APIKeyStatus.EXPIRED
        
        # Active key should still be active
        active = await db_session.get(APIKey, active_key["id"])
        assert active.status == APIKeyStatus.ACTIVE