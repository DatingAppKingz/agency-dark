"""Comprehensive tests for API Key model and management."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import secrets
import hashlib

from models.api_key import APIKey, APIKeyScope, APIKeyStatus
from models.user import User
from models.agency import Agency
from tests.factories import create_test_user, create_test_agency


class TestAPIKeyModel:
    """Test cases for API Key model."""
    
    @pytest.mark.asyncio
    async def test_create_api_key_with_valid_data(self, db_session: AsyncSession):
        """Test creating an API key with all valid data."""
        user = await create_test_user()
        
        # Generate API key
        raw_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(raw_key)
        
        api_key = APIKey(
            user_id=user.id,
            name="Production API Key",
            key_hash=key_hash,
            prefix=raw_key[:8],
            scopes=[APIKeyScope.READ, APIKeyScope.WRITE],
            expires_at=datetime.utcnow() + timedelta(days=365),
            status=APIKeyStatus.ACTIVE
        )
        
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        
        assert api_key.id is not None
        assert api_key.user_id == user.id
        assert api_key.name == "Production API Key"
        assert api_key.prefix == raw_key[:8]
        assert APIKeyScope.READ in api_key.scopes
        assert APIKeyScope.WRITE in api_key.scopes
        assert api_key.status == APIKeyStatus.ACTIVE
        assert api_key.created_at is not None
    
    @pytest.mark.asyncio
    async def test_api_key_generation_and_hashing(self, db_session: AsyncSession):
        """Test API key generation and secure hashing."""
        # Generate multiple keys
        keys = [APIKey.generate_key() for _ in range(10)]
        
        # All keys should be unique
        assert len(set(keys)) == 10
        
        # Keys should have correct format
        for key in keys:
            assert len(key) == 32
            assert key.isalnum()
            
        # Test hashing
        raw_key = keys[0]
        hash1 = APIKey.hash_key(raw_key)
        hash2 = APIKey.hash_key(raw_key)
        
        # Same key should produce same hash
        assert hash1 == hash2
        
        # Different keys should produce different hashes
        assert APIKey.hash_key(keys[0]) != APIKey.hash_key(keys[1])
        
        # Hash should not reveal original key
        assert raw_key not in hash1
        assert len(hash1) == 64  # SHA256 hex digest
    
    @pytest.mark.asyncio
    async def test_api_key_verification(self, db_session: AsyncSession):
        """Test API key verification process."""
        user = await create_test_user()
        
        # Create API key
        raw_key = APIKey.generate_key()
        api_key = APIKey(
            user_id=user.id,
            name="Test Key",
            key_hash=APIKey.hash_key(raw_key),
            prefix=raw_key[:8],
            scopes=[APIKeyScope.READ],
            status=APIKeyStatus.ACTIVE
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Verify correct key
        assert api_key.verify_key(raw_key) is True
        
        # Verify incorrect key
        assert api_key.verify_key("wrong_key_12345678901234567890") is False
        assert api_key.verify_key("") is False
        assert api_key.verify_key(raw_key[:-1]) is False
    
    @pytest.mark.asyncio
    async def test_api_key_scopes(self, db_session: AsyncSession):
        """Test API key scope validation."""
        user = await create_test_user()
        
        # Create key with specific scopes
        api_key = APIKey(
            user_id=user.id,
            name="Limited Key",
            key_hash="hash",
            prefix="test",
            scopes=[APIKeyScope.READ, APIKeyScope.ANALYTICS]
        )
        
        # Check individual scopes
        assert api_key.has_scope(APIKeyScope.READ) is True
        assert api_key.has_scope(APIKeyScope.ANALYTICS) is True
        assert api_key.has_scope(APIKeyScope.WRITE) is False
        assert api_key.has_scope(APIKeyScope.DELETE) is False
        
        # Check multiple scopes (AND)
        assert api_key.has_all_scopes([APIKeyScope.READ, APIKeyScope.ANALYTICS]) is True
        assert api_key.has_all_scopes([APIKeyScope.READ, APIKeyScope.WRITE]) is False
        
        # Check multiple scopes (OR)
        assert api_key.has_any_scope([APIKeyScope.READ, APIKeyScope.WRITE]) is True
        assert api_key.has_any_scope([APIKeyScope.WRITE, APIKeyScope.DELETE]) is False
    
    @pytest.mark.asyncio
    async def test_api_key_expiration(self, db_session: AsyncSession):
        """Test API key expiration handling."""
        user = await create_test_user()
        
        # Create expired key
        expired_key = APIKey(
            user_id=user.id,
            name="Expired Key",
            key_hash="hash",
            prefix="exp",
            expires_at=datetime.utcnow() - timedelta(days=1),
            status=APIKeyStatus.ACTIVE
        )
        
        assert expired_key.is_expired() is True
        assert expired_key.is_valid() is False
        
        # Create key expiring in future
        future_key = APIKey(
            user_id=user.id,
            name="Future Key",
            key_hash="hash",
            prefix="fut",
            expires_at=datetime.utcnow() + timedelta(days=30),
            status=APIKeyStatus.ACTIVE
        )
        
        assert future_key.is_expired() is False
        assert future_key.is_valid() is True
        
        # Create key with no expiration
        permanent_key = APIKey(
            user_id=user.id,
            name="Permanent Key",
            key_hash="hash",
            prefix="perm",
            expires_at=None,
            status=APIKeyStatus.ACTIVE
        )
        
        assert permanent_key.is_expired() is False
        assert permanent_key.is_valid() is True
    
    @pytest.mark.asyncio
    async def test_api_key_status_management(self, db_session: AsyncSession):
        """Test API key status transitions."""
        user = await create_test_user()
        raw_key = APIKey.generate_key()
        
        api_key = APIKey(
            user_id=user.id,
            name="Status Test Key",
            key_hash=APIKey.hash_key(raw_key),
            prefix=raw_key[:8],
            status=APIKeyStatus.ACTIVE
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Active key is valid
        assert api_key.is_valid() is True
        assert api_key.status == APIKeyStatus.ACTIVE
        
        # Revoke key
        api_key.revoke(reason="Security policy update")
        assert api_key.status == APIKeyStatus.REVOKED
        assert api_key.revoked_at is not None
        assert api_key.revocation_reason == "Security policy update"
        assert api_key.is_valid() is False
        
        # Cannot reactivate revoked key
        with pytest.raises(ValueError, match="Cannot reactivate revoked key"):
            api_key.activate()
        
        # Create new key and rotate it
        new_key = APIKey(
            user_id=user.id,
            name="Rotation Test",
            key_hash="hash",
            prefix="rot",
            status=APIKeyStatus.ACTIVE
        )
        
        new_key.mark_as_rotated(new_key_id="new_key_123")
        assert new_key.status == APIKeyStatus.ROTATED
        assert new_key.rotated_at is not None
        assert new_key.rotated_to_key_id == "new_key_123"
        assert new_key.is_valid() is False
    
    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(self, db_session: AsyncSession):
        """Test API key usage tracking and rate limiting."""
        user = await create_test_user()
        
        api_key = APIKey(
            user_id=user.id,
            name="Usage Test",
            key_hash="hash",
            prefix="use",
            status=APIKeyStatus.ACTIVE,
            rate_limit_per_hour=100
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Record usage
        for i in range(10):
            api_key.record_usage(
                endpoint="/api/users",
                method="GET",
                response_time_ms=50 + i,
                status_code=200
            )
        
        await db_session.commit()
        
        # Check usage stats
        assert api_key.last_used_at is not None
        assert api_key.usage_count == 10
        
        # Get usage statistics
        stats = api_key.get_usage_stats(hours=1)
        assert stats["total_requests"] == 10
        assert stats["average_response_time"] == 54.5  # (50+51+...+59)/10
        assert stats["endpoints"]["/api/users"] == 10
        
        # Check rate limiting
        current_usage = api_key.get_current_hour_usage()
        assert current_usage == 10
        assert api_key.is_rate_limited() is False
        
        # Simulate hitting rate limit
        for i in range(91):
            api_key.record_usage(endpoint="/api/test", method="GET")
        
        assert api_key.get_current_hour_usage() == 101
        assert api_key.is_rate_limited() is True
    
    @pytest.mark.asyncio
    async def test_api_key_ip_restrictions(self, db_session: AsyncSession):
        """Test API key IP address restrictions."""
        user = await create_test_user()
        
        # Key with IP whitelist
        api_key = APIKey(
            user_id=user.id,
            name="IP Restricted",
            key_hash="hash",
            prefix="ip",
            status=APIKeyStatus.ACTIVE,
            allowed_ips=["192.168.1.1", "10.0.0.0/24"]
        )
        
        # Test exact IP match
        assert api_key.is_ip_allowed("192.168.1.1") is True
        assert api_key.is_ip_allowed("192.168.1.2") is False
        
        # Test CIDR range
        assert api_key.is_ip_allowed("10.0.0.1") is True
        assert api_key.is_ip_allowed("10.0.0.255") is True
        assert api_key.is_ip_allowed("10.0.1.1") is False
        
        # Empty whitelist allows all
        api_key.allowed_ips = []
        assert api_key.is_ip_allowed("any.ip.address") is True
    
    @pytest.mark.asyncio
    async def test_api_key_metadata(self, db_session: AsyncSession):
        """Test API key metadata storage."""
        user = await create_test_user()
        
        metadata = {
            "environment": "production",
            "service": "webhook-processor",
            "version": "1.2.3",
            "permissions": ["read:users", "write:logs"]
        }
        
        api_key = APIKey(
            user_id=user.id,
            name="Metadata Test",
            key_hash="hash",
            prefix="meta",
            metadata=metadata
        )
        
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        
        # Verify metadata stored correctly
        assert api_key.metadata["environment"] == "production"
        assert api_key.metadata["service"] == "webhook-processor"
        assert "read:users" in api_key.metadata["permissions"]
        
        # Update metadata
        api_key.update_metadata({"environment": "staging", "new_field": "value"})
        await db_session.commit()
        
        assert api_key.metadata["environment"] == "staging"
        assert api_key.metadata["new_field"] == "value"
        assert api_key.metadata["service"] == "webhook-processor"  # Preserved
    
    @pytest.mark.asyncio
    async def test_api_key_rotation(self, db_session: AsyncSession):
        """Test API key rotation workflow."""
        user = await create_test_user()
        
        # Create original key
        old_raw_key = APIKey.generate_key()
        old_key = APIKey(
            user_id=user.id,
            name="Production API",
            key_hash=APIKey.hash_key(old_raw_key),
            prefix=old_raw_key[:8],
            scopes=[APIKeyScope.READ, APIKeyScope.WRITE],
            metadata={"version": "1.0"}
        )
        db_session.add(old_key)
        await db_session.commit()
        
        # Rotate key
        new_raw_key = APIKey.generate_key()
        new_key = APIKey.rotate_from(
            old_key=old_key,
            new_raw_key=new_raw_key,
            rotation_reason="Regular rotation policy"
        )
        
        db_session.add(new_key)
        await db_session.commit()
        
        # Verify rotation
        assert new_key.user_id == old_key.user_id
        assert new_key.name == old_key.name + " (Rotated)"
        assert new_key.scopes == old_key.scopes
        assert new_key.metadata["version"] == "1.0"
        assert new_key.metadata["rotated_from"] == str(old_key.id)
        assert new_key.status == APIKeyStatus.ACTIVE
        
        assert old_key.status == APIKeyStatus.ROTATED
        assert old_key.rotated_to_key_id == str(new_key.id)
        assert old_key.is_valid() is False
    
    @pytest.mark.asyncio
    async def test_api_key_audit_trail(self, db_session: AsyncSession):
        """Test API key audit trail functionality."""
        user = await create_test_user()
        
        api_key = APIKey(
            user_id=user.id,
            name="Audit Test",
            key_hash="hash",
            prefix="aud",
            status=APIKeyStatus.ACTIVE
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Log various events
        api_key.log_event("created", {"created_by": "admin"})
        api_key.log_event("scope_changed", {"old": [], "new": ["read"]})
        api_key.log_event("used", {"endpoint": "/api/users", "ip": "1.2.3.4"})
        api_key.log_event("rate_limited", {"requests": 101})
        api_key.log_event("revoked", {"reason": "Compromised"})
        
        # Get audit trail
        events = api_key.get_audit_trail()
        assert len(events) == 5
        assert events[0]["event"] == "revoked"
        assert events[-1]["event"] == "created"
        
        # Filter by event type
        usage_events = api_key.get_audit_trail(event_type="used")
        assert len(usage_events) == 1
        assert usage_events[0]["metadata"]["endpoint"] == "/api/users"
    
    @pytest.mark.asyncio
    async def test_api_key_uniqueness_constraints(self, db_session: AsyncSession):
        """Test API key uniqueness constraints."""
        user = await create_test_user()
        
        # Create first key
        key1 = APIKey(
            user_id=user.id,
            name="Unique Test 1",
            key_hash="unique_hash_123",
            prefix="uniq1234"
        )
        db_session.add(key1)
        await db_session.commit()
        
        # Try to create key with same hash (should fail)
        key2 = APIKey(
            user_id=user.id,
            name="Unique Test 2",
            key_hash="unique_hash_123",  # Same hash
            prefix="diff5678"
        )
        db_session.add(key2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
        
        await db_session.rollback()
        
        # Different hash should work
        key3 = APIKey(
            user_id=user.id,
            name="Unique Test 3",
            key_hash="different_hash_456",
            prefix="diff5678"
        )
        db_session.add(key3)
        await db_session.commit()  # Should succeed


class TestAPIKeyService:
    """Test cases for API key service operations."""
    
    @pytest.mark.asyncio
    async def test_create_api_key_with_validation(self, db_session: AsyncSession):
        """Test creating API key with full validation."""
        user = await create_test_user()
        
        # Test invalid scope combinations
        with pytest.raises(ValueError, match="DELETE scope requires WRITE scope"):
            APIKey.create_for_user(
                user_id=user.id,
                name="Invalid Scopes",
                scopes=[APIKeyScope.READ, APIKeyScope.DELETE]
            )
        
        # Test name validation
        with pytest.raises(ValueError, match="API key name required"):
            APIKey.create_for_user(
                user_id=user.id,
                name="",
                scopes=[APIKeyScope.READ]
            )
        
        # Create valid key
        raw_key, api_key = APIKey.create_for_user(
            user_id=user.id,
            name="Valid Key",
            scopes=[APIKeyScope.READ, APIKeyScope.WRITE],
            expires_in_days=90,
            metadata={"purpose": "testing"}
        )
        
        assert len(raw_key) == 32
        assert api_key.name == "Valid Key"
        assert api_key.verify_key(raw_key) is True
        assert api_key.expires_at is not None
    
    @pytest.mark.asyncio
    async def test_find_and_validate_key(self, db_session: AsyncSession):
        """Test finding and validating API keys."""
        user = await create_test_user()
        raw_key, api_key = APIKey.create_for_user(
            user_id=user.id,
            name="Search Test",
            scopes=[APIKeyScope.READ]
        )
        db_session.add(api_key)
        await db_session.commit()
        
        # Find by prefix
        found_keys = await APIKey.find_by_prefix(
            db_session,
            prefix=raw_key[:8]
        )
        assert len(found_keys) == 1
        assert found_keys[0].id == api_key.id
        
        # Validate full key
        validated_key = await APIKey.validate_key(
            db_session,
            raw_key=raw_key,
            required_scopes=[APIKeyScope.READ],
            ip_address="any.ip"
        )
        assert validated_key is not None
        assert validated_key.id == api_key.id
        
        # Validation should fail with wrong key
        invalid_key = await APIKey.validate_key(
            db_session,
            raw_key="wrong_key_12345678901234567890",
            required_scopes=[APIKeyScope.READ]
        )
        assert invalid_key is None
        
        # Validation should fail with missing scope
        invalid_scope = await APIKey.validate_key(
            db_session,
            raw_key=raw_key,
            required_scopes=[APIKeyScope.WRITE]
        )
        assert invalid_scope is None
    
    @pytest.mark.asyncio  
    async def test_bulk_key_operations(self, db_session: AsyncSession):
        """Test bulk API key operations."""
        user = await create_test_user()
        
        # Create multiple keys
        keys = []
        for i in range(5):
            _, api_key = APIKey.create_for_user(
                user_id=user.id,
                name=f"Bulk Test {i}",
                scopes=[APIKeyScope.READ]
            )
            keys.append(api_key)
            db_session.add(api_key)
        
        await db_session.commit()
        
        # Bulk revoke by user
        revoked_count = await APIKey.revoke_all_for_user(
            db_session,
            user_id=user.id,
            reason="User deactivated"
        )
        assert revoked_count == 5
        
        # Verify all revoked
        for key in keys:
            await db_session.refresh(key)
            assert key.status == APIKeyStatus.REVOKED
            assert key.revocation_reason == "User deactivated"
        
        # Cleanup expired keys
        # First create some expired keys
        for i in range(3):
            expired_key = APIKey(
                user_id=user.id,
                name=f"Expired {i}",
                key_hash=f"expired_hash_{i}",
                prefix=f"exp{i}",
                expires_at=datetime.utcnow() - timedelta(days=1),
                status=APIKeyStatus.ACTIVE
            )
            db_session.add(expired_key)
        
        await db_session.commit()
        
        # Cleanup
        cleaned = await APIKey.cleanup_expired_keys(db_session)
        assert cleaned == 3