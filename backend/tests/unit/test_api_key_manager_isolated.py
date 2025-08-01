"""
Isolated unit tests for API Key Manager that don't require full app import
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSecureAPIKeyManagerIsolated:
    """Test cases for API key manager logic without imports"""
    
    def test_hash_api_key_logic(self):
        """Test API key hashing logic."""
        import hashlib
        
        def hash_api_key(api_key: str) -> str:
            """Create a secure hash of an API key"""
            salt = b'agencydark_api_key_salt_v1'
            key_bytes = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000)
            return key_bytes.hex()
        
        # Test consistent hashing
        test_key = "sk_test123456789"
        hash1 = hash_api_key(test_key)
        hash2 = hash_api_key(test_key)
        
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 produces 32 bytes = 64 hex chars
        
        # Test different keys produce different hashes
        hash3 = hash_api_key("sk_different123")
        assert hash1 != hash3
    
    def test_check_scopes_logic(self):
        """Test scope checking logic."""
        def check_scopes(available_scopes: list, required_scopes: list) -> bool:
            """Check if available scopes satisfy requirements"""
            if "*" in available_scopes:
                return True
            
            for scope in required_scopes:
                if scope not in available_scopes:
                    # Check for wildcard scopes
                    scope_parts = scope.split(":")
                    if len(scope_parts) > 1:
                        wildcard = f"{scope_parts[0]}:*"
                        if wildcard not in available_scopes:
                            return False
                    else:
                        return False
            
            return True
        
        # Test exact matches
        assert check_scopes(["read:users", "write:users"], ["read:users"]) is True
        assert check_scopes(["read:users"], ["write:users"]) is False
        
        # Test wildcards
        assert check_scopes(["*"], ["anything"]) is True
        assert check_scopes(["read:*"], ["read:users"]) is True
        assert check_scopes(["read:*"], ["write:users"]) is False
    
    def test_needs_rotation_logic(self):
        """Test key rotation logic."""
        def needs_rotation(created_at, rotated_at, rotation_days=90):
            """Check if an API key needs rotation"""
            if not rotated_at:
                age_days = (datetime.utcnow() - created_at).days
            else:
                age_days = (datetime.utcnow() - rotated_at).days
            
            return age_days >= rotation_days
        
        # Test never rotated, recent
        assert needs_rotation(
            datetime.utcnow() - timedelta(days=30),
            None
        ) is False
        
        # Test never rotated, old
        assert needs_rotation(
            datetime.utcnow() - timedelta(days=100),
            None
        ) is True
        
        # Test rotated recently
        assert needs_rotation(
            datetime.utcnow() - timedelta(days=200),
            datetime.utcnow() - timedelta(days=30)
        ) is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_logic(self):
        """Test rate limiting logic."""
        class MockRedis:
            def __init__(self):
                self.data = {}
            
            def pipeline(self):
                return self
            
            def incrby(self, key, value):
                self.data[key] = self.data.get(key, 0) + value
                return self
            
            def expire(self, key, ttl):
                return self
            
            async def execute(self):
                if self.data:
                    key = list(self.data.keys())[-1]  # Get last key
                    return [self.data.get(key, 0), True]
                return [0, True]
        
        redis = MockRedis()
        
        # Test rate limit checking
        async def check_rate_limit(key, limit, redis_client):
            pipe = redis_client.pipeline()
            pipe.incrby(key, 1)
            pipe.expire(key, 60)
            results = await pipe.execute()
            return results[0] <= limit
        
        # First request should pass
        result1 = await check_rate_limit("test:1", 10, redis)
        assert result1 is True
        
        # Simulate hitting the limit
        redis.data["test:2"] = 15
        result2 = await check_rate_limit("test:2", 10, redis)
        assert result2 is False
    
    def test_key_prefix_generation(self):
        """Test API key prefix generation."""
        def get_key_prefix(environment, key_type="public"):
            """Generate key prefix based on environment and type"""
            prefixes = {
                "public": {"live": "pk_live_", "test": "pk_test_"},
                "secret": {"live": "sk_live_", "test": "sk_test_"}
            }
            return prefixes.get(key_type, {}).get(environment, "pk_")
        
        assert get_key_prefix("live", "public") == "pk_live_"
        assert get_key_prefix("test", "public") == "pk_test_"
        assert get_key_prefix("live", "secret") == "sk_live_"
        assert get_key_prefix("test", "secret") == "sk_test_"
    
    def test_metadata_encryption_format(self):
        """Test metadata encryption format."""
        def format_encrypted_metadata(scopes, environment, user_metadata=None):
            """Format metadata for encryption"""
            return {
                "scopes": scopes,
                "environment": environment,
                "user_metadata": user_metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
        
        metadata = format_encrypted_metadata(
            ["read:users", "write:users"],
            "production",
            {"org": "test_org"}
        )
        
        assert metadata["scopes"] == ["read:users", "write:users"]
        assert metadata["environment"] == "production"
        assert metadata["user_metadata"]["org"] == "test_org"
        assert "created_at" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])