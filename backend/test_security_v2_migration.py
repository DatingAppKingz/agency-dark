#!/usr/bin/env python3
"""
Test script to verify security_v2 migration is working.
"""
import sys
import asyncio

def test_imports():
    """Test that all key imports work."""
    print("Testing imports...")
    
    try:
        # Test core dependencies
        from core.dependencies import (
            get_current_user,
            CurrentUser,
            CurrentUserOptional,
            require_permission,
            require_role
        )
        print("✓ core.dependencies imports OK")
        
        # Test security_v2 imports
        from core.security_v2 import (
            hash_password,
            verify_password,
            create_token_pair,
            decode_token,
            session_manager
        )
        print("✓ core.security_v2 imports OK")
        
        # Test middleware imports
        from core.security_v2.middleware import (
            AuthenticationMiddleware,
            SecurityMiddleware,
            RateLimitMiddleware
        )
        print("✓ core.security_v2.middleware imports OK")
        
        # Test auth endpoint
        from api.v1.endpoints.auth import router
        print("✓ api.v1.endpoints.auth imports OK")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


async def test_basic_auth_functions():
    """Test basic authentication functions."""
    print("\nTesting basic auth functions...")
    
    try:
        from core.security_v2 import hash_password, verify_password, create_token_pair, decode_token
        
        # Test password hashing
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed), "Password verification failed"
        print("✓ Password hashing and verification OK")
        
        # Test token creation
        access_token, refresh_token = create_token_pair(
            user_id="test-user-id",
            email="test@example.com",
            role="admin"
        )
        assert access_token, "Access token creation failed"
        assert refresh_token, "Refresh token creation failed"
        print("✓ Token creation OK")
        
        # Test token decoding
        payload = decode_token(access_token)
        assert payload, "Token decoding failed"
        assert payload.get("email") == "test@example.com", "Token payload incorrect"
        print("✓ Token decoding OK")
        
        return True
        
    except Exception as e:
        print(f"✗ Function test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("Security_v2 Migration Test")
    print("=" * 50)
    
    # Test imports
    import_success = test_imports()
    
    # Test functions
    function_success = asyncio.run(test_basic_auth_functions())
    
    print("\n" + "=" * 50)
    if import_success and function_success:
        print("✅ All tests passed! Migration successful.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())