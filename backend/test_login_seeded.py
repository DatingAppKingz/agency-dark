"""Test login with seeded accounts."""

import requests
import json

# Base URL
BASE_URL = "http://localhost:8001"


def test_login(email, password, role_name):
    """Test login for a specific user."""
    print(f"\n=== Testing {role_name} Login ===")
    print(f"Email: {email}")
    
    login_data = {
        "email": email,
        "password": password
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json=login_data
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Login successful!")
        print(f"User: {data['user']['email']}")
        print(f"Role: {data['user']['role']}")
        print(f"Agency ID: {data['user']['agency_id']}")
        return data['access_token']
    else:
        print(f"Login failed: {response.json()}")
        return None


def test_authenticated_request(token, role_name):
    """Test authenticated endpoint."""
    print(f"\n  Testing authenticated request for {role_name}...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers=headers
    )
    
    if response.status_code == 200:
        print("  ✓ Authentication working!")
    else:
        print(f"  ✗ Authentication failed: {response.status_code}")


if __name__ == "__main__":
    print("Testing AgencyDark Seeded Accounts")
    print("==================================")
    
    # Test accounts
    test_accounts = [
        ("admin@agencydark.com", "admin123", "Super Admin"),
        ("owner@elitemodels.com", "owner123", "Agency Owner"),
        ("sarah@elitemodels.com", "model123", "Model"),
        ("mike@elitemodels.com", "chatter123", "Chatter")
    ]
    
    for email, password, role in test_accounts:
        token = test_login(email, password, role)
        if token:
            test_authenticated_request(token, role)