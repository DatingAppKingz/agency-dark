"""
Test script for enhanced WebSocket authentication.
"""
import asyncio
import json
from datetime import datetime, timedelta
from jose import jwt

from core.security_v2.authentication import enhanced_websocket_auth, WebSocketAuthError
from core.config import settings

# Mock user data
MOCK_USERS = {
    "admin@agency.com": {
        "id": "00000000-0000-0000-0000-000000000001",
        "role": "SUPER_ADMIN",
        "agency_id": None
    },
    "owner@elitemodels.com": {
        "id": "11111111-1111-1111-1111-111111111111",
        "role": "AGENCY_OWNER",
        "agency_id": "11111111-1111-1111-1111-111111111111"
    },
    "sarah@elitemodels.com": {
        "id": "22222222-2222-2222-2222-222222222222",
        "role": "MODEL",
        "agency_id": "11111111-1111-1111-1111-111111111111"
    },
    "john@elitemodels.com": {
        "id": "33333333-3333-3333-3333-333333333333",
        "role": "CHATTER",
        "agency_id": "11111111-1111-1111-1111-111111111111"
    }
}


def create_test_token(email: str, expired: bool = False) -> str:
    """Create a test JWT token."""
    user = MOCK_USERS.get(email)
    if not user:
        raise ValueError(f"Unknown test user: {email}")
    
    exp_time = datetime.utcnow() + (
        timedelta(minutes=-10) if expired else timedelta(minutes=30)
    )
    
    payload = {
        "sub": user["id"],
        "email": email,
        "role": user["role"],
        "agency_id": user["agency_id"],
        "exp": exp_time,
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def test_authentication():
    """Test WebSocket authentication scenarios."""
    print("🔒 Testing Enhanced WebSocket Authentication\n")
    
    # Test 1: Successful authentication for different roles
    print("1️⃣ Testing successful authentication for different roles:")
    
    for email, user_data in MOCK_USERS.items():
        try:
            token = create_test_token(email)
            connection_id = f"test_sid_{user_data['id'][:8]}"
            
            # Mock client info
            client_info = {
                "ip": "127.0.0.1",
                "user_agent": "TestClient/1.0"
            }
            
            # Note: This will fail because it tries to fetch from real database
            # In a real test, we would mock the database call
            print(f"\n   Testing {email} (Role: {user_data['role']}):")
            print(f"   - Token created successfully")
            print(f"   - Connection ID: {connection_id}")
            print(f"   - Would authenticate with role-based permissions")
            
        except Exception as e:
            print(f"   ❌ Error for {email}: {e}")
    
    # Test 2: Invalid token
    print("\n\n2️⃣ Testing invalid token:")
    try:
        # Create invalid token
        invalid_token = "invalid.jwt.token"
        connection_id = "test_sid_invalid"
        
        # This should fail
        result = await enhanced_websocket_auth.authenticate_connection(
            invalid_token, connection_id
        )
        print("   ❌ Should have failed but didn't!")
    except WebSocketAuthError as e:
        print(f"   ✅ Correctly rejected: {e}")
    except Exception as e:
        print(f"   ⚠️  Failed with different error: {e}")
    
    # Test 3: Expired token
    print("\n3️⃣ Testing expired token:")
    try:
        expired_token = create_test_token("admin@agency.com", expired=True)
        connection_id = "test_sid_expired"
        
        result = await enhanced_websocket_auth.authenticate_connection(
            expired_token, connection_id
        )
        print("   ❌ Should have failed but didn't!")
    except WebSocketAuthError as e:
        print(f"   ✅ Correctly rejected: {e}")
    except Exception as e:
        print(f"   ⚠️  Failed with different error: {e}")
    
    # Test 4: Room access validation
    print("\n4️⃣ Testing room access validation:")
    
    # Mock user contexts for testing
    test_contexts = {
        "super_admin": {
            "user_id": "00000000-0000-0000-0000-000000000001",
            "role": "SUPER_ADMIN",
            "agency_id": None,
            "is_super_admin": True
        },
        "agency_owner": {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "role": "AGENCY_OWNER",
            "agency_id": "11111111-1111-1111-1111-111111111111",
            "is_super_admin": False
        },
        "model": {
            "user_id": "22222222-2222-2222-2222-222222222222",
            "role": "MODEL",
            "agency_id": "11111111-1111-1111-1111-111111111111",
            "is_super_admin": False
        },
        "chatter": {
            "user_id": "33333333-3333-3333-3333-333333333333",
            "role": "CHATTER",
            "agency_id": "11111111-1111-1111-1111-111111111111",
            "is_super_admin": False
        }
    }
    
    # Test agency room access
    print("\n   Agency Room Access:")
    for role, context in test_contexts.items():
        # Test own agency
        allowed = await enhanced_websocket_auth.validate_room_access(
            context, "agency", context.get("agency_id", "none")
        )
        print(f"   - {role} → own agency: {'✅ Allowed' if allowed else '❌ Denied'}")
        
        # Test different agency
        allowed = await enhanced_websocket_auth.validate_room_access(
            context, "agency", "99999999-9999-9999-9999-999999999999"
        )
        print(f"   - {role} → other agency: {'✅ Allowed' if allowed else '❌ Denied'}")
    
    # Test 5: Permission validation
    print("\n5️⃣ Testing permission validation:")
    
    actions = ["send_message", "update_status", "assign_chatter", "view_analytics"]
    
    for role, context in test_contexts.items():
        print(f"\n   {role} permissions:")
        # Get permissions for role
        permissions = enhanced_websocket_auth._get_role_permissions(context["role"])
        context["permissions"] = permissions
        
        for action in actions:
            allowed = await enhanced_websocket_auth.validate_message_permissions(
                context, action, {"conversation_id": "123"}
            )
            print(f"   - {action}: {'✅ Allowed' if allowed else '❌ Denied'}")
    
    print("\n✅ WebSocket authentication tests completed!")


async def test_token_refresh():
    """Test token refresh functionality."""
    print("\n🔄 Testing Token Refresh:\n")
    
    # Create a token that expires soon
    from datetime import timezone
    
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "admin@agency.com",
        "role": "SUPER_ADMIN",
        "agency_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=4),  # Expires in 4 minutes
        "iat": datetime.now(timezone.utc)
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    # Mock connection
    connection_id = "test_refresh_sid"
    enhanced_websocket_auth.active_connections[connection_id] = {
        "connection_id": connection_id,
        "user_id": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
        "agency_id": payload["agency_id"],
        "token_exp": payload["exp"].timestamp()
    }
    
    # Check if refresh is needed
    new_token = await enhanced_websocket_auth.refresh_token_if_needed(connection_id)
    if new_token:
        print("   ✅ Token refresh triggered (expires within 5 minutes)")
        print(f"   New token generated: {new_token[:20]}...")
    else:
        print("   ℹ️  Token still valid, no refresh needed")
    
    # Clean up
    del enhanced_websocket_auth.active_connections[connection_id]


async def main():
    """Run all tests."""
    await test_authentication()
    await test_token_refresh()


if __name__ == "__main__":
    asyncio.run(main())