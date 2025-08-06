#!/usr/bin/env python3
"""
Test the migration layer for security_v2.
"""
import sys
sys.path.insert(0, 'backend')

from core.security_v2.migration.auth_adapter import auth_adapter
from core.security_v2.migration.permission_mapper import permission_mapper
from core.security_v2.migration import create_compatible_token
from core.security_v2.migration.compatibility import (
    create_access_token,
    verify_token,
    get_password_hash,
    verify_password,
    check_permission,
    get_user_permissions,
    is_admin,
    is_owner
)

def test_auth_adapter():
    """Test authentication adapter."""
    print("Testing Auth Adapter...")
    print("-" * 50)
    
    # Test role mapping
    role_tests = [
        ("admin", "agency_admin"),
        ("super-admin", "super_admin"),
        ("owner", "agency_owner"),
        ("unknown", "viewer")
    ]
    
    for old_role, expected in role_tests:
        mapped = auth_adapter._map_role(old_role)
        print(f"✓ Role '{old_role}' -> '{mapped}' (expected: {expected})")
        assert mapped == expected, f"Role mapping failed for {old_role}"
    
    # Test password verification with plain text fallback
    plain_password = "admin123"
    hashed_password = get_password_hash(plain_password)
    
    # Test with hashed password
    assert auth_adapter.verify_password_compatible(plain_password, hashed_password)
    print(f"✓ Verified hashed password")
    
    # Test with wrong password
    assert not auth_adapter.verify_password_compatible("wrong", hashed_password)
    print(f"✓ Rejected wrong password")
    
    # Test authentication
    user_data = {
        'id': 1,
        'email': 'test@example.com',
        'role': 'admin',
        'agency_id': 1,
        'hashed_password': hashed_password,
        'first_name': 'Test',
        'last_name': 'User'
    }
    
    result = auth_adapter.authenticate_user('test@example.com', plain_password, user_data)
    assert result is not None
    assert 'access_token' in result
    assert result['user']['role'] == 'agency_admin'
    print(f"✓ User authenticated successfully")
    
    print("\n✅ Auth adapter tests passed!")

def test_permission_mapper():
    """Test permission mapper."""
    print("\nTesting Permission Mapper...")
    print("-" * 50)
    
    # Test permission mapping
    perm_tests = [
        ("users:create", "user:create"),
        ("models:read", "model:read"),
        ("admin", "system:admin"),
        ("unknown", None)
    ]
    
    for old_perm, expected in perm_tests:
        mapped = permission_mapper.map_permission(old_perm)
        if expected:
            print(f"✓ Permission '{old_perm}' -> '{mapped.value if mapped else None}'")
            assert mapped and mapped.value == expected, f"Permission mapping failed for {old_perm}"
        else:
            print(f"✓ Unknown permission '{old_perm}' -> None")
            assert mapped is None
    
    # Test role permission retrieval
    admin_perms = permission_mapper.get_role_permissions_legacy("admin")
    print(f"✓ Admin has {len(admin_perms)} permissions")
    assert len(admin_perms) > 0
    
    # Test permission checking
    can_create = permission_mapper.check_legacy_permission(
        "agency_admin",
        "users:create"
    )
    assert can_create
    print(f"✓ Agency admin can create users")
    
    cannot_delete = not permission_mapper.check_legacy_permission(
        "model",
        "users:delete"
    )
    assert cannot_delete
    print(f"✓ Model cannot delete users")
    
    print("\n✅ Permission mapper tests passed!")

def test_compatibility_layer():
    """Test compatibility functions."""
    print("\nTesting Compatibility Layer...")
    print("-" * 50)
    
    # Test token creation
    token_data = {
        "sub": "1",
        "email": "test@example.com",
        "role": "admin"
    }
    token = create_access_token(token_data)
    assert token is not None
    print(f"✓ Created access token: {token[:30]}...")
    
    # Test token verification
    payload = verify_token(token)
    assert payload is not None
    assert payload['email'] == "test@example.com"
    print(f"✓ Verified token successfully")
    
    # Test password functions
    password = "TestPassword123!"
    hashed = get_password_hash(password)
    assert hashed.startswith('$2b$')
    print(f"✓ Password hashed: {hashed[:20]}...")
    
    assert verify_password(password, hashed)
    print(f"✓ Password verified")
    
    # Test permission checking
    assert check_permission("agency_admin", "model:update")
    print(f"✓ Permission check passed")
    
    # Test role checks
    assert is_admin("agency_admin")
    print(f"✓ Admin check passed")
    
    assert is_owner("agency_owner")
    print(f"✓ Owner check passed")
    
    assert not is_owner("model")
    print(f"✓ Non-owner check passed")
    
    # Test get permissions
    perms = get_user_permissions("agency_admin")
    assert len(perms) > 0
    print(f"✓ Retrieved {len(perms)} permissions for admin")
    
    print("\n✅ Compatibility layer tests passed!")

def main():
    """Run all migration layer tests."""
    print("🔄 Testing Security Migration Layer\n")
    
    try:
        test_auth_adapter()
        test_permission_mapper()
        test_compatibility_layer()
        
        print("\n" + "=" * 50)
        print("✨ ALL MIGRATION TESTS PASSED! ✨")
        print("=" * 50)
        print("\nThe migration layer is ready to bridge old and new security systems!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()