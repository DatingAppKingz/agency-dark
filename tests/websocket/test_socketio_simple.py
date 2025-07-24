#!/usr/bin/env python3
"""
Simple Socket.IO test using curl to check if it's working
"""

import requests
import json


def test_socketio_endpoint():
    """Test if Socket.IO endpoint is available"""
    base_url = "http://localhost:8000"
    
    print("🔍 Testing Socket.IO availability...")
    
    # Socket.IO usually exposes these endpoints
    endpoints = [
        "/socket.io/",
        "/socket.io/?EIO=4&transport=polling",
        "/socket.io/?transport=websocket"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"\n📍 {endpoint}")
            print(f"   Status: {response.status_code}")
            if response.status_code < 500:
                print(f"   Response: {response.text[:100]}...")
        except Exception as e:
            print(f"   Error: {e}")
    
    # Test with authentication
    print("\n🔐 Testing with authentication...")
    
    # Login first
    login_response = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": "model1@testagencypremium.com", "password": "Test123!"}
    )
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print(f"✅ Got token: {token[:50]}...")
        
        # Try Socket.IO with auth
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{base_url}/socket.io/?EIO=4&transport=polling",
            headers=headers
        )
        print(f"\n📍 Socket.IO with auth:")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
    else:
        print(f"❌ Login failed: {login_response.text}")


if __name__ == "__main__":
    test_socketio_endpoint()