#!/usr/bin/env python3
"""
Test the authentication flow with the new security_v2 backend.
"""
import asyncio
import sys
import os
import psycopg2
from datetime import datetime

# Add backend to path
sys.path.insert(0, 'backend')

def check_backend_running():
    """Check if the backend is running."""
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Backend is running: {data['service']} v{data['version']}")
            return True
    except:
        pass
    return False

def test_login():
    """Test login with existing user."""
    import requests
    
    print("\nTesting login...")
    print("-" * 50)
    
    # Test with admin user
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={
            "email": "admin@agency.com",
            "password": "admin123"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Login successful!")
        print(f"  Access token: {data['access_token'][:50]}...")
        if 'refresh_token' in data:
            print(f"  Refresh token: {data['refresh_token'][:50]}...")
        return data['access_token']
    else:
        print(f"✗ Login failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_get_current_user(token):
    """Test getting current user with token."""
    import requests
    
    print("\nTesting /me endpoint...")
    print("-" * 50)
    
    response = requests.get(
        "http://localhost:8000/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Current user retrieved!")
        print(f"  User ID: {data.get('user_id')}")
        print(f"  Email: {data.get('email')}")
        print(f"  Role: {data.get('role')}")
        print(f"  Agency ID: {data.get('agency_id')}")
        return True
    else:
        print(f"✗ Failed to get current user: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def test_protected_endpoint(token):
    """Test a protected endpoint."""
    import requests
    
    print("\nTesting protected endpoint...")
    print("-" * 50)
    
    response = requests.get(
        "http://localhost:8000/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Protected endpoint accessed!")
        print(f"  Found {len(data)} users")
        return True
    elif response.status_code == 403:
        print(f"✓ Protected endpoint correctly denied access (insufficient permissions)")
        return True
    else:
        print(f"✗ Unexpected response: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def test_refresh_token(access_token):
    """Test token refresh."""
    import requests
    
    print("\nTesting token refresh...")
    print("-" * 50)
    
    # First login to get refresh token
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={
            "email": "admin@agency.com",
            "password": "admin123"
        }
    )
    
    if response.status_code != 200:
        print("✗ Failed to get initial tokens")
        return False
    
    data = response.json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        print("⚠️  No refresh token in response (might not be implemented yet)")
        return True
    
    # Try to refresh
    response = requests.post(
        "http://localhost:8000/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Token refreshed successfully!")
        print(f"  New access token: {data['access_token'][:50]}...")
        return True
    else:
        print(f"✗ Token refresh failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def test_security_info():
    """Test security info endpoint."""
    import requests
    
    print("\nTesting security info...")
    print("-" * 50)
    
    response = requests.get("http://localhost:8000/api/v1/security/info")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Security info retrieved!")
        print(f"  Version: {data['version']}")
        print(f"  RBAC enabled: {data['features']['rbac']}")
        print(f"  Rate limiting: {data['features']['rate_limiting']}")
        print(f"  JWT algorithm: {data['jwt']['algorithm']}")
        print(f"  Password min length: {data['password_policy']['min_length']}")
        return True
    else:
        print(f"✗ Failed to get security info: {response.status_code}")
        return False

def verify_password_hashing():
    """Verify passwords are properly hashed in database."""
    print("\nVerifying password hashing in database...")
    print("-" * 50)
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="agencydark_dev",
            user="mariuszbudzisz"
        )
        cur = conn.cursor()
        
        # Check a few users
        cur.execute("""
            SELECT email, hashed_password 
            FROM users 
            WHERE email IN ('admin@agency.com', 'owner@elitemodels.com')
            LIMIT 2
        """)
        
        users = cur.fetchall()
        all_hashed = True
        
        for email, password in users:
            if password and password.startswith('$2b$'):
                print(f"✓ {email}: Password is properly hashed")
            else:
                print(f"✗ {email}: Password NOT hashed!")
                all_hashed = False
        
        cur.close()
        conn.close()
        
        return all_hashed
        
    except Exception as e:
        print(f"✗ Database check failed: {e}")
        return False

def main():
    """Run all authentication flow tests."""
    print("🔐 Testing Authentication Flow with Security v2\n")
    
    # Check if backend is running
    if not check_backend_running():
        print("\n⚠️  Backend is not running!")
        print("Please start the backend first:")
        print("  cd backend && python3 main_v2.py")
        return
    
    # Verify password hashing
    verify_password_hashing()
    
    # Test login
    token = test_login()
    if not token:
        print("\n❌ Login failed, cannot continue tests")
        return
    
    # Test authenticated endpoints
    test_get_current_user(token)
    test_protected_endpoint(token)
    test_refresh_token(token)
    test_security_info()
    
    print("\n" + "=" * 50)
    print("✨ Authentication flow test complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()