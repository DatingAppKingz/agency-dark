"""Simple login test."""

import requests

# Test login
response = requests.post(
    "http://localhost:8001/api/v1/auth/login",
    json={"email": "admin@agencydark.com", "password": "admin123"}
)

print(f"Status: {response.status_code}")
print(f"Headers: {response.headers}")
print(f"Content: {response.text}")

if response.status_code == 200:
    data = response.json()
    print(f"Token: {data['access_token'][:20]}...")
    
    # Test dashboard
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    dash_response = requests.get(
        "http://localhost:8001/api/v1/analytics/dashboard",
        headers=headers
    )
    print(f"\nDashboard Status: {dash_response.status_code}")
    if dash_response.status_code == 200:
        dash_data = dash_response.json()
        print(f"Total Revenue: ${dash_data['total_revenue']}")
        print(f"Total Models: {dash_data['total_models']}")
        print(f"Active Chats: {dash_data['active_chats']}")
    else:
        print(f"Dashboard Error: {dash_response.text}")
else:
    print(f"Login Error: {response.text}")