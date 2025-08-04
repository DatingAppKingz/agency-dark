#!/usr/bin/env python3
"""Test script to verify CSRF protection implementation."""

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

def test_csrf_protection():
    """Test CSRF protection mechanisms."""
    print_section("Testing CSRF Protection")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Test 1: Get CSRF token
    print("1. Getting CSRF token...")
    csrf_response = session.get(f"{BASE_URL}/auth/csrf-token")
    
    print(f"   Status: {csrf_response.status_code}")
    
    if csrf_response.status_code == 200:
        csrf_data = csrf_response.json()
        csrf_token = csrf_data.get('csrf_token')
        print(f"   ✅ Got CSRF token: {csrf_token[:20]}...")
        
        # Check if CSRF cookie was set
        csrf_cookie = session.cookies.get('__Secure-CSRF-Token')
        if csrf_cookie:
            print(f"   ✅ CSRF cookie is set: {csrf_cookie[:20]}...")
        else:
            print("   ❌ CSRF cookie was NOT set")
    else:
        print("   ❌ Failed to get CSRF token")
        print(f"   Response: {csrf_response.text}")
        return
    
    # Test 2: Login without CSRF token (should fail)
    print("\n2. Testing login WITHOUT CSRF token...")
    no_csrf_response = requests.post(
        f"{BASE_URL}/auth/login",
        json=TEST_USER,
        cookies={'__Secure-CSRF-Token': csrf_token}  # Cookie only, no header
    )
    
    print(f"   Status: {no_csrf_response.status_code}")
    
    if no_csrf_response.status_code == 403:
        print("   ✅ Login correctly blocked without CSRF header")
    else:
        print("   ⚠️  Login succeeded without CSRF header (might be excluded)")
        
    # Test 3: Login with CSRF token
    print("\n3. Testing login WITH CSRF token...")
    headers = {'X-CSRF-Token': csrf_token}
    login_response = session.post(
        f"{BASE_URL}/auth/login",
        json=TEST_USER,
        headers=headers
    )
    
    print(f"   Status: {login_response.status_code}")
    
    if login_response.status_code == 200:
        print("   ✅ Login successful with CSRF token")
        login_data = login_response.json()
        
        # Check if new CSRF token was provided
        new_csrf_token = login_data.get('csrf_token')
        if new_csrf_token:
            print(f"   ✅ New CSRF token provided: {new_csrf_token[:20]}...")
            csrf_token = new_csrf_token  # Update for future requests
    else:
        print("   ❌ Login failed even with CSRF token")
        print(f"   Response: {login_response.text}")
        
    # Test 4: Access protected endpoint with CSRF
    print("\n4. Testing protected endpoint with CSRF...")
    
    # First, let's try without CSRF token
    print("   a) Without CSRF token...")
    no_csrf_me = session.get(f"{BASE_URL}/auth/me")
    print(f"      Status: {no_csrf_me.status_code}")
    
    if no_csrf_me.status_code == 200:
        print("      ✅ GET request successful (CSRF not required for safe methods)")
    
    # Test 5: Test state-changing operation
    print("\n5. Testing state-changing operation (logout)...")
    
    # Try logout without CSRF
    print("   a) Logout without CSRF token...")
    no_csrf_logout = requests.post(
        f"{BASE_URL}/auth/logout",
        cookies=session.cookies
    )
    
    print(f"      Status: {no_csrf_logout.status_code}")
    
    if no_csrf_logout.status_code == 403:
        print("      ✅ Logout correctly blocked without CSRF token")
    else:
        print("      ⚠️  Logout succeeded without CSRF token")
        
    # Try logout with CSRF
    print("   b) Logout with CSRF token...")
    csrf_logout = session.post(
        f"{BASE_URL}/auth/logout",
        headers={'X-CSRF-Token': csrf_token}
    )
    
    print(f"      Status: {csrf_logout.status_code}")
    
    if csrf_logout.status_code == 200:
        print("      ✅ Logout successful with CSRF token")
    else:
        print("      ❌ Logout failed even with CSRF token")
        print(f"      Response: {csrf_logout.text}")

def test_csrf_token_mismatch():
    """Test CSRF token mismatch scenarios."""
    print_section("Testing CSRF Token Mismatch")
    
    session = requests.Session()
    
    # Get a valid CSRF token
    csrf_response = session.get(f"{BASE_URL}/auth/csrf-token")
    if csrf_response.status_code == 200:
        valid_csrf_token = csrf_response.json().get('csrf_token')
        
        # Test with wrong CSRF token
        print("1. Testing with mismatched CSRF token...")
        wrong_token = "wrong-csrf-token-12345"
        
        response = session.post(
            f"{BASE_URL}/auth/login",
            json=TEST_USER,
            headers={'X-CSRF-Token': wrong_token}
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 403:
            print("   ✅ Request correctly blocked with wrong CSRF token")
        else:
            print("   ❌ Request succeeded with wrong CSRF token!")
            
        # Test with manipulated token
        print("\n2. Testing with manipulated CSRF token...")
        if ':' in valid_csrf_token:
            parts = valid_csrf_token.split(':')
            manipulated = f"{parts[0]}:tampered:{parts[-1]}"
            
            response = session.post(
                f"{BASE_URL}/auth/login",
                json=TEST_USER,
                headers={'X-CSRF-Token': manipulated}
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 403:
                print("   ✅ Request correctly blocked with manipulated token")
            else:
                print("   ❌ Request succeeded with manipulated token!")

if __name__ == "__main__":
    print(f"\n🚀 Testing CSRF Protection Implementation")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test CSRF protection
        test_csrf_protection()
        
        # Test token mismatch scenarios
        test_csrf_token_mismatch()
        
        print("\n✅ All CSRF tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the backend")
        print("   Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")