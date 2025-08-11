#!/usr/bin/env python3
"""Test authentication endpoints to diagnose issues"""

import requests
import json
import time

# Test authentication endpoints
def test_auth():
    base_url = "http://localhost:8000/api/v1/auth"
    
    # 1. Login
    print("1. Testing Login...")
    login_response = requests.post(f"{base_url}/login", 
        json={"email": "admin@agency.com", "password": "admin123"})
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return
    
    tokens = login_response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    
    print(f"✅ Login successful")
    print(f"   Access token: {access_token[:30]}...")
    print(f"   Refresh token: {refresh_token[:30] if refresh_token else 'None'}...")
    
    # Save cookies from login response
    cookies = login_response.cookies
    
    # 2. Test /me endpoint
    print("\n2. Testing /me endpoint...")
    me_response = requests.get(f"{base_url}/me",
        headers={"Authorization": f"Bearer {access_token}"})
    
    if me_response.status_code == 200:
        print(f"✅ /me endpoint works")
        user_data = me_response.json()
        print(f"   User: {user_data.get('email')}, Role: {user_data.get('role')}")
    else:
        print(f"❌ /me failed: {me_response.status_code}")
        print(me_response.text)
    
    # 3. Test refresh endpoint
    print("\n3. Testing /refresh endpoint...")
    
    # Try with cookie
    refresh_response = requests.post(f"{base_url}/refresh",
        cookies={"refresh_token": refresh_token} if refresh_token else cookies)
    
    if refresh_response.status_code == 200:
        print(f"✅ Refresh token works")
        new_tokens = refresh_response.json()
        print(f"   New access token: {new_tokens.get('access_token', '')[:30]}...")
    else:
        print(f"❌ Refresh failed: {refresh_response.status_code}")
        print(f"   Error: {refresh_response.text[:200]}")
        
        # Try with Authorization header instead
        print("\n   Trying with Authorization header...")
        refresh_response2 = requests.post(f"{base_url}/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"} if refresh_token else {})
        
        if refresh_response2.status_code == 200:
            print(f"✅ Refresh works with Authorization header")
        else:
            print(f"❌ Still failed: {refresh_response2.status_code}")
    
    # 4. Test verify-token endpoint
    print("\n4. Testing /verify-token endpoint...")
    verify_response = requests.get(f"{base_url}/verify-token",
        headers={"Authorization": f"Bearer {access_token}"})
    
    if verify_response.status_code == 200:
        print(f"✅ Token verification works")
        verify_data = verify_response.json()
        print(f"   Response: {verify_data}")
    else:
        print(f"❌ Verify failed: {verify_response.status_code}")
        print(f"   Error: {verify_response.text[:200]}")
        
        # Check if it's a 404 (endpoint doesn't exist)
        if verify_response.status_code == 404:
            print("\n   Endpoint might not be implemented. Let's check available endpoints...")
            
    # 5. Test logout
    print("\n5. Testing /logout endpoint...")
    logout_response = requests.post(f"{base_url}/logout",
        headers={"Authorization": f"Bearer {access_token}"})
    
    if logout_response.status_code in [200, 204]:
        print(f"✅ Logout works")
    else:
        print(f"❌ Logout failed: {logout_response.status_code}")
        print(f"   Error: {logout_response.text[:200]}")

if __name__ == "__main__":
    test_auth()