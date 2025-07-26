#!/usr/bin/env python3
import requests
import json

API_URL = "http://localhost:8000/api/v1"

print("Testing AgencyDark API Connection...\n")

# Test 1: Health check
print("1. Testing root endpoint...")
try:
    response = requests.get("http://localhost:8000/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Login
print("\n2. Testing login endpoint...")
try:
    login_data = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = requests.post(f"{API_URL}/auth/login", json=login_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Success! Access token received")
        print(f"   User: {data.get('user', {}).get('email', 'Unknown')}")
    else:
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Check CORS headers
print("\n3. Testing CORS configuration...")
try:
    headers = {
        "Origin": "http://localhost:5173"
    }
    response = requests.options(f"{API_URL}/auth/login", headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   CORS Headers:")
    print(f"   - Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'Not set')}")
    print(f"   - Access-Control-Allow-Credentials: {response.headers.get('Access-Control-Allow-Credentials', 'Not set')}")
    print(f"   - Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'Not set')}")
except Exception as e:
    print(f"   Error: {e}")

print("\n✅ API test complete!")