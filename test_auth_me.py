#!/usr/bin/env python3
import requests
import json

# Login
login_url = "http://localhost:8000/api/v1/auth/login"
login_data = {
    "email": "model@testagency.com",
    "password": "Test123!"
}

print("1. Testing login...")
login_response = requests.post(login_url, json=login_data)
print(f"Login status: {login_response.status_code}")

if login_response.status_code == 200:
    tokens = login_response.json()
    access_token = tokens['access_token']
    print(f"Access token: {access_token[:50]}...")
    
    # Test auth/me
    print("\n2. Testing auth/me...")
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = requests.get("http://localhost:8000/api/v1/auth/me", headers=headers)
    print(f"Auth/me status: {me_response.status_code}")
    print(f"Response: {json.dumps(me_response.json(), indent=2)}")
else:
    print(f"Login failed: {login_response.text}")