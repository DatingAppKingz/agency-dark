"""
Test script for Platform API Key management.
"""
import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ["DATABASE_URL"] = "postgresql://mariuszbudzisz@localhost/agencydark_dev"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["DISABLE_ML"] = "true"

import logging
logging.basicConfig(level=logging.INFO)

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from models.user import User, UserRole
from models.platform_api_key import PlatformAPIKey, PlatformAPIKeyScope
from core.security.api_keys.key_manager import api_key_manager
from core.security.api_keys.key_generator import APIKeyGenerator, APIKeyValidator, APIKeyScopeValidator


async def get_test_user(db: AsyncSession) -> User:
    """Get or create a test user."""
    # Try to get admin user
    result = await db.execute(
        select(User).where(User.email == "admin@agency.com")
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create test user
        user = User(
            email="admin@agency.com",
            username="admin",
            first_name="Admin",
            last_name="User",
            role=UserRole.AGENCY_ADMIN,
            agency_id="11111111-1111-1111-1111-111111111111",
            hashed_password="dummy_hash",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user


async def test_key_generation():
    """Test API key generation."""
    print("\n=== Testing Key Generation ===")
    
    generator = APIKeyGenerator()
    
    # Test different key types
    for key_type in ["live", "test", "webhook", "restricted"]:
        full_key, prefix, key_hash = generator.generate_key(key_type)
        print(f"\n{key_type.upper()} Key:")
        print(f"  Full Key: {full_key}")
        print(f"  Prefix: {prefix}")
        print(f"  Hash: {key_hash[:16]}...")
        
        # Validate format
        is_valid = generator.validate_format(full_key)
        print(f"  Valid Format: {is_valid}")
        
        # Test hash consistency
        rehash = generator.hash_key(full_key)
        print(f"  Hash Consistent: {rehash == key_hash}")


async def test_scope_validation():
    """Test scope validation."""
    print("\n=== Testing Scope Validation ===")
    
    validator = APIKeyScopeValidator()
    
    # Test valid scope combinations
    test_cases = [
        (["read:users", "read:models"], True),
        (["write:users", "read:users"], True),  # Write implies read
        (["admin:system"], True),
        (["admin:system", "read:users"], False),  # System admin shouldn't mix
        (["read:users", "read:users"], False),  # Duplicate
    ]
    
    for scopes, should_be_valid in test_cases:
        is_valid, error = APIKeyValidator.validate_scope_combination(scopes)
        print(f"\nScopes: {scopes}")
        print(f"  Expected Valid: {should_be_valid}")
        print(f"  Actually Valid: {is_valid}")
        if error:
            print(f"  Error: {error}")
        
        # Test scope expansion
        expanded = validator.expand_scopes(scopes)
        print(f"  Expanded Scopes: {sorted(expanded)}")


async def test_api_key_creation(db: AsyncSession):
    """Test creating an API key."""
    print("\n=== Testing API Key Creation ===")
    
    # Get test user
    user = await get_test_user(db)
    print(f"\nUsing user: {user.email} (Role: {user.role})")
    
    # Create API key with various scopes
    try:
        api_key, plain_text_key = await api_key_manager.create_api_key(
            db=db,
            user=user,
            name="Test API Key",
            scopes=["read:users", "read:models", "write:conversations"],
            description="Test key for platform access",
            expires_in_days=30,
            allowed_ips=["127.0.0.1", "192.168.1.0/24"],
            rate_limits={
                "per_minute": 100,
                "per_hour": 1000,
                "per_day": 10000
            },
            metadata={"purpose": "testing", "created_by": "test_script"}
        )
        
        print(f"\nAPI Key Created:")
        print(f"  ID: {api_key.id}")
        print(f"  Name: {api_key.name}")
        print(f"  Prefix: {api_key.key_prefix}")
        print(f"  Plain Text Key: {plain_text_key}")
        print(f"  Scopes: {api_key.scopes}")
        print(f"  Expires At: {api_key.expires_at}")
        print(f"  Rate Limits: {api_key.rate_limit_per_minute}/min, {api_key.rate_limit_per_hour}/hr, {api_key.rate_limit_per_day}/day")
        
        return api_key, plain_text_key
        
    except Exception as e:
        print(f"  Error creating key: {e}")
        raise


async def test_api_key_validation(db: AsyncSession, api_key_string: str):
    """Test API key validation."""
    print("\n=== Testing API Key Validation ===")
    
    # Test valid key
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string=api_key_string,
        required_scope="read:users",
        ip_address="127.0.0.1"
    )
    
    if validated_key:
        print(f"\nKey Validated Successfully:")
        print(f"  Name: {validated_key.name}")
        print(f"  Last Used: {validated_key.last_used_at}")
        print(f"  Usage Count: {validated_key.usage_count}")
    else:
        print("\nKey validation failed!")
        
    # Test with invalid scope
    print("\n\nTesting with invalid scope:")
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string=api_key_string,
        required_scope="admin:system",  # Key doesn't have this
        ip_address="127.0.0.1"
    )
    print(f"  Should fail (no admin scope): {validated_key is None}")
    
    # Test with invalid IP
    print("\n\nTesting with invalid IP:")
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string=api_key_string,
        required_scope="read:users",
        ip_address="10.0.0.1"  # Not in allowed IPs
    )
    print(f"  Should fail (invalid IP): {validated_key is None}")
    
    # Test with invalid key
    print("\n\nTesting with invalid key:")
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string="pk_live_invalidkey123",
        ip_address="127.0.0.1"
    )
    print(f"  Should fail (invalid key): {validated_key is None}")


async def test_rate_limiting(db: AsyncSession, api_key: PlatformAPIKey):
    """Test rate limiting."""
    print("\n=== Testing Rate Limiting ===")
    
    # Check initial rate limits
    is_allowed, remaining = await api_key_manager.check_rate_limit(api_key, db)
    print(f"\nInitial Rate Limits:")
    print(f"  Allowed: {is_allowed}")
    print(f"  Remaining: {remaining}")
    
    # Log some usage
    for i in range(5):
        await api_key_manager.log_usage(
            db=db,
            api_key=api_key,
            endpoint="/api/v1/users",
            method="GET",
            status_code=200,
            response_time_ms=100 + i * 10,
            ip_address="127.0.0.1"
        )
    
    # Check rate limits again
    is_allowed, remaining = await api_key_manager.check_rate_limit(api_key, db)
    print(f"\nAfter 5 requests:")
    print(f"  Allowed: {is_allowed}")
    print(f"  Remaining: {remaining}")
    
    # Check usage stats
    await db.refresh(api_key)
    print(f"\nUsage Stats:")
    print(f"  Total Usage: {api_key.usage_count}")
    print(f"  Monthly Usage: {api_key.monthly_usage}")


async def test_api_key_rotation(db: AsyncSession, api_key_id: str, user: User):
    """Test API key rotation."""
    print("\n=== Testing API Key Rotation ===")
    
    # Rotate the key
    new_key, new_plain_text = await api_key_manager.rotate_api_key(
        db=db,
        api_key_id=api_key_id,
        user=user,
        grace_period_hours=24
    )
    
    print(f"\nKey Rotated:")
    print(f"  New Key ID: {new_key.id}")
    print(f"  New Key Prefix: {new_key.key_prefix}")
    print(f"  New Plain Text: {new_plain_text}")
    print(f"  Rotated From: {new_key.rotated_from_id}")
    
    # Check old key
    result = await db.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
    )
    old_key = result.scalar_one_or_none()
    
    if old_key:
        print(f"\nOld Key Status:")
        print(f"  Still Active: {old_key.is_active}")
        print(f"  Rotation Scheduled: {old_key.rotation_scheduled_at}")


async def test_api_key_revocation(db: AsyncSession, api_key_id: str, user: User):
    """Test API key revocation."""
    print("\n=== Testing API Key Revocation ===")
    
    # Revoke the key
    success = await api_key_manager.revoke_api_key(
        db=db,
        api_key_id=api_key_id,
        revoked_by=user,
        reason="Testing revocation"
    )
    
    print(f"\nRevocation Success: {success}")
    
    # Check revoked key
    result = await db.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == api_key_id)
    )
    revoked_key = result.scalar_one_or_none()
    
    if revoked_key:
        print(f"\nRevoked Key Status:")
        print(f"  Is Active: {revoked_key.is_active}")
        print(f"  Revoked At: {revoked_key.revoked_at}")
        print(f"  Revoke Reason: {revoked_key.revoke_reason}")


async def main():
    """Run all tests."""
    print("Platform API Key Management Test Suite")
    print("=" * 50)
    
    # Create database engine
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False
    )
    
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as db:
        try:
            # Test key generation (no DB needed)
            await test_key_generation()
            
            # Test scope validation (no DB needed)
            await test_scope_validation()
            
            # Test API key creation
            api_key, plain_text_key = await test_api_key_creation(db)
            
            # Test API key validation
            await test_api_key_validation(db, plain_text_key)
            
            # Test rate limiting
            await test_rate_limiting(db, api_key)
            
            # Get user for next tests
            user = await get_test_user(db)
            
            # Test rotation
            await test_api_key_rotation(db, str(api_key.id), user)
            
            # Test revocation
            await test_api_key_revocation(db, str(api_key.id), user)
            
            print("\n\n✅ All tests completed successfully!")
            
        except Exception as e:
            print(f"\n\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())