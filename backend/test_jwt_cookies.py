#!/usr/bin/env python3
"""Test script to verify JWT cookie implementation."""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/v1"

# Test user credentials
TEST_USER = {
    "email": "admin@agency.com",
    "password": "admin123"
}

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_login_with_cookies():
    """Test login endpoint and verify cookies are set."""
    print_section("Testing Login with Cookies")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Test login
    print("1. Testing login endpoint...")
    response = session.post(
        f"{BASE_URL}/auth/login",
        json=TEST_USER
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Login successful")
        
        # Check cookies
        print("\n2. Checking cookies...")
        cookies = session.cookies.get_dict()
        
        if 'access_token' in cookies:
            print("   ✅ access_token cookie is set")
        else:
            print("   ❌ access_token cookie is NOT set")
            
        if 'refresh_token' in cookies:
            print("   ✅ refresh_token cookie is set")
        else:
            print("   ❌ refresh_token cookie is NOT set")
            
        # Print all cookies
        print("\n   All cookies:")
        for name, value in cookies.items():
            print(f"   - {name}: {value[:20]}..." if len(value) > 20 else f"   - {name}: {value}")
            
        # Test /me endpoint using cookies
        print("\n3. Testing /me endpoint with cookies...")
        me_response = session.get(f"{BASE_URL}/auth/me")
        
        print(f"   Status: {me_response.status_code}")
        
        if me_response.status_code == 200:
            print("   ✅ Successfully accessed protected endpoint with cookies")
            user_data = me_response.json()
            print(f"   User: {user_data.get('email', 'N/A')}")
        else:
            print("   ❌ Failed to access protected endpoint")
            print(f"   Response: {me_response.text}")
            
        # Test refresh endpoint
        print("\n4. Testing refresh endpoint with cookies...")
        refresh_response = session.post(f"{BASE_URL}/auth/refresh", json={})
        
        print(f"   Status: {refresh_response.status_code}")
        
        if refresh_response.status_code == 200:
            print("   ✅ Successfully refreshed tokens")
            # Check if cookies were updated
            new_cookies = session.cookies.get_dict()
            print(f"   Cookies after refresh: {list(new_cookies.keys())}")
        else:
            print("   ❌ Failed to refresh tokens")
            print(f"   Response: {refresh_response.text}")
            
        # Test logout
        print("\n5. Testing logout...")
        logout_response = session.post(f"{BASE_URL}/auth/logout")
        
        print(f"   Status: {logout_response.status_code}")
        
        if logout_response.status_code == 200:
            print("   ✅ Successfully logged out")
            # Check if cookies were cleared
            final_cookies = session.cookies.get_dict()
            if not final_cookies.get('access_token') and not final_cookies.get('refresh_token'):
                print("   ✅ Cookies were cleared")
            else:
                print("   ⚠️  Some cookies may still be present")
        else:
            print("   ❌ Failed to logout")
            print(f"   Response: {logout_response.text}")
            
    else:
        print("   ❌ Login failed")
        print(f"   Response: {response.text}")

def test_traditional_bearer_token():
    """Test that traditional Bearer token authentication still works."""
    print_section("Testing Traditional Bearer Token Auth")
    
    # Login to get token
    print("1. Getting token via login...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json=TEST_USER
    )
    
    if response.status_code == 200:
        data = response.json()
        access_token = data.get('access_token')
        
        if access_token:
            print("   ✅ Got access token")
            
            # Test with Bearer token
            print("\n2. Testing /me endpoint with Bearer token...")
            headers = {"Authorization": f"Bearer {access_token}"}
            me_response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
            
            print(f"   Status: {me_response.status_code}")
            
            if me_response.status_code == 200:
                print("   ✅ Bearer token authentication still works")
            else:
                print("   ❌ Bearer token authentication failed")
                print(f"   Response: {me_response.text}")
        else:
            print("   ❌ No access token in response")
    else:
        print("   ❌ Login failed")
        print(f"   Response: {response.text}")

if __name__ == "__main__":
    print(f"\n🚀 Testing JWT Cookie Implementation")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test cookie-based auth
        test_login_with_cookies()
        
        # Test traditional Bearer token auth
        test_traditional_bearer_token()
        
        print("\n✅ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the backend")
        print("   Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")