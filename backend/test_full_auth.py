"""
Test full authentication flow.
"""
import requests
import json

# Login
print("1. Testing login...")
login_resp = requests.post('http://localhost:8000/api/v1/auth/login',
    json={'email': 'admin@agency.com', 'password': 'admin123'})

print(f"Login response: {login_resp.status_code}")
if login_resp.status_code != 200:
    print(f"Error: {login_resp.text}")
    exit(1)

data = login_resp.json()
token = data['access_token']
print(f"Token: {token[:50]}...")

# Test /me endpoint
print("\n2. Testing /me endpoint...")
me_resp = requests.get('http://localhost:8000/api/v1/auth/me',
    headers={'Authorization': f'Bearer {token}'})

print(f"Me response: {me_resp.status_code}")
if me_resp.status_code == 200:
    print("✅ Authentication flow working!")
    print(f"User data: {json.dumps(me_resp.json(), indent=2)}")
else:
    print(f"❌ Error: {me_resp.text}")