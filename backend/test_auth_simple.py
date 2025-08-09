"""
Simple test of authentication flow.
"""
import requests
import json

# Test login
print("Testing login endpoint...")
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@agency.com", "password": "admin123"}
)

if response.status_code == 200:
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login successful!")
    print(f"Token: {token[:20]}..." if token else "No token")
    
    # Test /me endpoint
    if token:
        print("\nTesting /me endpoint...")
        me_response = requests.get(
            "http://localhost:8000/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if me_response.status_code == 200:
            user_data = me_response.json()
            print(f"✅ /me endpoint successful!")
            print(f"User: {user_data.get('email')}")
            print(f"Role: {user_data.get('role')}")
        else:
            print(f"❌ /me endpoint failed: {me_response.status_code}")
            print(me_response.text)
else:
    print(f"❌ Login failed: {response.status_code}")
    print(response.text)