"""Test the new API endpoints."""

import requests
import json

# Base URL
BASE_URL = "http://localhost:8001"

# Test credentials
TEST_USERS = {
    "admin": {"email": "admin@agencydark.com", "password": "admin123"},
    "owner": {"email": "owner@elitemodels.com", "password": "owner123"},
    "model": {"email": "sarah@elitemodels.com", "password": "model123"},
    "chatter": {"email": "mike@elitemodels.com", "password": "chatter123"}
}


def login(role):
    """Login and get token."""
    user = TEST_USERS[role]
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json=user
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data["user"]
    else:
        print(f"Login failed for {role}: {response.json()}")
        return None, None


def test_dashboard(token):
    """Test dashboard endpoint."""
    print("\n=== Testing Dashboard ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/api/v1/analytics/dashboard",
        headers=headers,
        params={"period": "week"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total Revenue: ${data['total_revenue']}")
        print(f"Total Models: {data['total_models']}")
        print(f"Active Chats: {data['active_chats']}")
        print(f"Total Subscribers: {data['total_subscribers']}")
    else:
        print(f"Error: {response.json()}")


def test_models(token):
    """Test models endpoint."""
    print("\n=== Testing Models ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/api/v1/models",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total Models: {data['total']}")
        print(f"Models on page: {len(data['models'])}")
        for model in data['models'][:3]:
            print(f"  - {model['stage_name']} ({model['platform']}) - Status: {model['status']}")
    else:
        print(f"Error: {response.json()}")


def test_conversations(token):
    """Test conversations endpoint."""
    print("\n=== Testing Conversations ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test active conversations
    response = requests.get(
        f"{BASE_URL}/api/v1/conversations/active",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total Active Chats: {data['total']}")
        print(f"Chats on page: {len(data['chats'])}")
    else:
        print(f"Error: {response.json()}")
    
    # Test conversation stats
    response = requests.get(
        f"{BASE_URL}/api/v1/conversations/stats",
        headers=headers
    )
    
    print(f"\nConversation Stats:")
    if response.status_code == 200:
        data = response.json()
        print(f"  Active Chats: {data['active_chats']}")
        print(f"  Messages Today: {data['total_messages_today']}")
        print(f"  Unread Messages: {data['unread_messages']}")
        print(f"  Revenue Today: ${data['revenue_today']}")
    else:
        print(f"Error: {response.json()}")


def test_revenue_analytics(token):
    """Test revenue analytics endpoint."""
    print("\n=== Testing Revenue Analytics ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{BASE_URL}/api/v1/analytics/revenue",
        headers=headers,
        params={"period": "month"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total Revenue: ${data['total_revenue']}")
        print(f"Subscription Revenue: ${data['subscription_revenue']}")
        print(f"Tip Revenue: ${data['tip_revenue']}")
        print(f"PPV Revenue: ${data['ppv_revenue']}")
        print(f"Growth Rate: {data['growth_rate']:.1f}%")
    else:
        print(f"Error: {response.json()}")


def main():
    """Run all tests."""
    print("Testing AgencyDark API Endpoints")
    print("================================")
    
    # Test as admin
    print("\n\n### Testing as Admin ###")
    token, user = login("admin")
    if token:
        print(f"Logged in as: {user['email']} (Role: {user['role']})")
        test_dashboard(token)
        test_models(token)
        test_conversations(token)
        test_revenue_analytics(token)
    
    # Test as agency owner
    print("\n\n### Testing as Agency Owner ###")
    token, user = login("owner")
    if token:
        print(f"Logged in as: {user['email']} (Role: {user['role']})")
        test_dashboard(token)
        test_models(token)
    
    # Test as model
    print("\n\n### Testing as Model ###")
    token, user = login("model")
    if token:
        print(f"Logged in as: {user['email']} (Role: {user['role']})")
        test_models(token)
        test_conversations(token)
    
    # Test as chatter
    print("\n\n### Testing as Chatter ###")
    token, user = login("chatter")
    if token:
        print(f"Logged in as: {user['email']} (Role: {user['role']})")
        test_conversations(token)


if __name__ == "__main__":
    main()