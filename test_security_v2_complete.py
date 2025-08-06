#!/usr/bin/env python3
"""
Test the complete security_v2 module.
"""
import sys
sys.path.insert(0, 'backend')

from core.security_v2 import (
    # Authentication
    hash_password,
    verify_password,
    create_token_pair,
    verify_token,
    
    # Authorization
    Role,
    Permission,
    has_permission,
    get_role_permissions
)

def test_authentication():
    """Test authentication components."""
    print("Testing Authentication...")
    print("-" * 50)
    
    # Test password hashing
    password = "SecurePassword123!"
    hashed = hash_password(password)
    print(f"✓ Password hashed: {hashed[:30]}...")
    
    # Verify password
    assert verify_password(password, hashed), "Password verification failed"
    print("✓ Password verified successfully")
    
    # Create JWT tokens
    access_token, refresh_token = create_token_pair(
        user_id=1,
        email="admin@agency.com",
        role=Role.AGENCY_OWNER
    )
    print(f"✓ Access token created: {access_token[:30]}...")
    print(f"✓ Refresh token created: {refresh_token[:30]}...")
    
    # Verify token
    payload = verify_token(access_token, "access")
    assert payload is not None, "Token verification failed"
    assert payload["email"] == "admin@agency.com", "Email mismatch"
    assert payload["role"] == Role.AGENCY_OWNER, "Role mismatch"
    print(f"✓ Token verified: user={payload['sub']}, role={payload['role']}")
    
    print("\n✅ Authentication tests passed!")

def test_authorization():
    """Test authorization components."""
    print("\nTesting Authorization...")
    print("-" * 50)
    
    # Test role permissions
    owner_perms = get_role_permissions(Role.AGENCY_OWNER)
    print(f"✓ Agency owner has {len(owner_perms)} permissions")
    
    admin_perms = get_role_permissions(Role.AGENCY_ADMIN)
    print(f"✓ Agency admin has {len(admin_perms)} permissions")
    
    model_perms = get_role_permissions(Role.MODEL)
    print(f"✓ Model has {len(model_perms)} permissions")
    
    # Test permission checking
    # Agency owner can manage users
    assert has_permission(
        user_role=Role.AGENCY_OWNER,
        permission=Permission.USER_CREATE
    ), "Owner should be able to create users"
    print("✓ Agency owner can create users")
    
    # Model cannot delete users
    assert not has_permission(
        user_role=Role.MODEL,
        permission=Permission.USER_DELETE
    ), "Model should not be able to delete users"
    print("✓ Model cannot delete users")
    
    # Test agency scoping
    assert has_permission(
        user_role=Role.AGENCY_ADMIN,
        permission=Permission.MODEL_UPDATE,
        agency_id=1,
        user_agency_id=1
    ), "Admin should access same agency"
    print("✓ Agency admin can access same agency resources")
    
    assert not has_permission(
        user_role=Role.AGENCY_ADMIN,
        permission=Permission.MODEL_UPDATE,
        agency_id=2,
        user_agency_id=1
    ), "Admin should not access different agency"
    print("✓ Agency admin blocked from different agency")
    
    # Test super admin override
    assert has_permission(
        user_role=Role.SUPER_ADMIN,
        permission=Permission.SYSTEM_CONFIG
    ), "Super admin should have all permissions"
    print("✓ Super admin has system config permission")
    
    print("\n✅ Authorization tests passed!")

def test_integration():
    """Test integration between authentication and authorization."""
    print("\nTesting Integration...")
    print("-" * 50)
    
    # Create token with role
    access_token, _ = create_token_pair(
        user_id=2,
        email="admin@elitemodels.com",
        role=Role.AGENCY_ADMIN,
        additional_claims={"agency_id": 1}
    )
    print("✓ Created token with role and agency")
    
    # Verify token and check permissions
    payload = verify_token(access_token, "access")
    user_role = payload.get("role")
    agency_id = payload.get("agency_id")
    
    # Check if user can approve models
    can_approve = has_permission(
        user_role=user_role,
        permission=Permission.MODEL_APPROVE,
        user_agency_id=agency_id
    )
    assert can_approve, "Agency admin should be able to approve models"
    print(f"✓ User {payload['email']} can approve models")
    
    # Check if user cannot delete agency
    cannot_delete = not has_permission(
        user_role=user_role,
        permission=Permission.AGENCY_DELETE
    )
    assert cannot_delete, "Agency admin should not be able to delete agency"
    print(f"✓ User {payload['email']} cannot delete agency")
    
    print("\n✅ Integration tests passed!")

def main():
    """Run all tests."""
    print("🔐 Testing Complete Security v2 Module\n")
    
    try:
        test_authentication()
        test_authorization()
        test_integration()
        
        print("\n" + "=" * 50)
        print("✨ ALL SECURITY V2 TESTS PASSED! ✨")
        print("=" * 50)
        
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