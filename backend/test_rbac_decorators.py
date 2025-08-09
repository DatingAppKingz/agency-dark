"""Test RBAC decorators functionality."""
import asyncio
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import dependencies first to avoid circular imports
from core.security_v2.dependencies import get_current_user
from core.security_v2.decorators import require_roles, require_self_or_admin, require_model_assignment
from core.database import get_db
from models.user import User, UserRole
from auth_fix import router as auth_router

# Create test app
app = FastAPI()
app.include_router(auth_router, prefix="/api/v1/auth")

# Test endpoints
@app.get("/test/admin-only")
@require_roles([UserRole.SUPER_ADMIN.value, UserRole.AGENCY_OWNER.value])
async def admin_only_endpoint(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello admin {current_user.email}"}

@app.get("/test/self-or-admin/{user_id}")
@require_self_or_admin(user_id_param="user_id")
async def self_or_admin_endpoint(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {"message": f"Access granted for user {user_id}"}

@app.get("/test/model-access/{model_id}")
@require_model_assignment(model_id_param="model_id")
async def model_access_endpoint(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {"message": f"Access granted to model {model_id}"}

# Create test client
client = TestClient(app)

async def test_decorators():
    """Test RBAC decorators with different user roles."""
    
    test_cases = [
        {
            "user": "admin@agency.com",
            "password": "admin123",
            "role": "SUPER_ADMIN",
            "tests": [
                ("GET", "/test/admin-only", None, 200),
                ("GET", "/test/self-or-admin/b3333333-3333-3333-3333-333333333333", None, 200),  # Can access any user
                ("GET", "/test/model-access/b3333333-3333-3333-3333-333333333333", None, 200),  # Can access any model
            ]
        },
        {
            "user": "owner@elitemodels.com", 
            "password": "admin123",
            "role": "AGENCY_OWNER",
            "tests": [
                ("GET", "/test/admin-only", None, 200),  # Agency owner is admin
                ("GET", "/test/self-or-admin/b3333333-3333-3333-3333-333333333333", None, 200),  # Can access agency users
                ("GET", "/test/model-access/b3333333-3333-3333-3333-333333333333", None, 200),  # Can access agency models
            ]
        },
        {
            "user": "sarah@elitemodels.com",
            "password": "admin123", 
            "role": "MODEL",
            "tests": [
                ("GET", "/test/admin-only", None, 403),  # Not admin
                ("GET", "/test/self-or-admin/b3333333-3333-3333-3333-333333333333", None, 200),  # Accessing self
                ("GET", "/test/self-or-admin/b4444444-4444-4444-4444-444444444444", None, 403),  # Cannot access other user
                ("GET", "/test/model-access/b3333333-3333-3333-3333-333333333333", None, 200),  # Accessing self
            ]
        },
        {
            "user": "john@elitemodels.com",
            "password": "admin123",
            "role": "CHATTER", 
            "tests": [
                ("GET", "/test/admin-only", None, 403),  # Not admin
                ("GET", "/test/self-or-admin/b6666666-6666-6666-6666-666666666666", None, 200),  # Accessing self
                ("GET", "/test/model-access/b3333333-3333-3333-3333-333333333333", None, 200),  # Assigned to Sarah
                ("GET", "/test/model-access/b5555555-5555-5555-5555-555555555555", None, 403),  # Not assigned to Lisa
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🧪 Testing {test_case['role']} - {test_case['user']}")
        
        # Login
        response = client.post("/api/v1/auth/login-fix", json={
            "email": test_case["user"],
            "password": test_case["password"]
        })
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            continue
            
        token = response.cookies.get("access_token")
        
        # Run tests
        for method, path, body, expected_status in test_case["tests"]:
            response = client.request(
                method, 
                path, 
                json=body,
                cookies={"access_token": token}
            )
            
            if response.status_code == expected_status:
                print(f"  ✅ {method} {path} -> {expected_status}")
            else:
                print(f"  ❌ {method} {path} -> Expected {expected_status}, got {response.status_code}")
                print(f"     Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_decorators())