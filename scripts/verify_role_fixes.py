#!/usr/bin/env python3
"""
Verify that user roles have been fixed
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def check_user_role(email, password, expected_role):
    """Login and check user role"""
    print(f"\nChecking {email}...")
    
    # Force a fresh session (no cookies/cached tokens)
    session = requests.Session()
    
    # Login with fresh session
    response = session.post(f"{BASE_URL}/auth/login", json={
        "email": email,
        "password": password
    })
    
    if response.status_code != 200:
        print(f"  ❌ Login failed: {response.text}")
        return False
        
    token = response.json()["access_token"]
    
    # Get user info with fresh token
    headers = {"Authorization": f"Bearer {token}"}
    me_response = session.get(f"{BASE_URL}/auth/me", headers=headers)
    
    if me_response.status_code != 200:
        print(f"  ❌ Failed to get user info: {me_response.text}")
        return False
        
    user_data = me_response.json()
    actual_role = user_data.get("role", "").lower()
    
    if actual_role == expected_role.lower():
        print(f"  ✅ Role is correct: {actual_role}")
        print(f"  ✅ Agency ID: {user_data.get('agency_id', 'None')}")
        return True
    else:
        print(f"  ❌ Role mismatch: expected {expected_role}, got {actual_role}")
        return False

def main():
    print("=" * 60)
    print("Verifying User Roles")
    print("=" * 60)
    
    users_to_check = [
        ("owner@testagency.com", "AgencyOwner123!", "agency_owner"),
        ("admin@testagency.com", "AgencyAdmin123!", "agency_admin"),
        ("model@testagency.com", "ModelUser123!", "model"),
        ("chatter@testagency.com", "ChatterUser123!", "chatter"),
    ]
    
    success_count = 0
    for email, password, expected_role in users_to_check:
        if check_user_role(email, password, expected_role):
            success_count += 1
            
    print("\n" + "=" * 60)
    print(f"Results: {success_count}/{len(users_to_check)} users have correct roles")
    
    if success_count == len(users_to_check):
        print("✅ All user roles are fixed!")
    else:
        print("❌ Some users still have incorrect roles")
        print("\nTry running: python scripts/run_sql_fix.py")

if __name__ == "__main__":
    main()