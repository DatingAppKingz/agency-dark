"""Test authentication endpoints."""

import requests
import json

# Base URL
BASE_URL = "http://localhost:8001"


def test_register():
    """Test user registration."""
    print("\n=== Testing Registration ===")
    
    # Register a new user
    register_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123",
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json=register_data
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


def test_login():
    """Test user login."""
    print("\n=== Testing Login ===")
    
    login_data = {
        "email": "test@example.com",
        "password": "testpassword123"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json=login_data
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


def test_get_me(token):
    """Test getting current user."""
    print("\n=== Testing Get Me ===")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_auth_endpoint(token):
    """Test authenticated endpoint."""
    print("\n=== Testing Auth Endpoint ===")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/v1/auth/test-auth",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_health():
    """Test health endpoint."""
    print("\n=== Testing Health Check ===")
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    print("Testing AgencyDark Authentication API")
    
    # Test health
    test_health()
    
    # Test registration
    token = test_register()
    
    if not token:
        # If registration failed (user might exist), try login
        token = test_login()
    
    if token:
        # Test authenticated endpoints
        test_get_me(token)
        test_auth_endpoint(token)
    else:
        print("\nFailed to get authentication token!")