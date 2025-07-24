#!/usr/bin/env python3
"""
Seed test data via API calls
This approach avoids environment configuration issues
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"

def register_user(email, password, full_name, agency_name=None):
    """Register a new user via API"""
    data = {
        "email": email,
        "password": password,
        "full_name": full_name
    }
    if agency_name:
        data["agency_name"] = agency_name
        data["agency_domain"] = f"{agency_name.lower().replace(' ', '')}.com"
    
    response = requests.post(f"{BASE_URL}/auth/register", json=data)
    if response.status_code == 200:
        print(f"✅ Created user: {email}")
        return response.json()
    else:
        print(f"❌ Failed to create user {email}: {response.text}")
        return None


def main():
    print("=" * 60)
    print("Seeding Test Data via API")
    print("=" * 60)
    
    # Create users for testing different roles
    users = []
    
    # 1. Agency Owner with new agency
    owner = register_user(
        "owner@testagency.com",
        "AgencyOwner123!",
        "John Agency Owner",
        "Test Agency Premium"
    )
    if owner:
        users.append(owner)
    
    # 2. Agency Admin (will need to be added to agency by owner)
    admin = register_user(
        "admin@testagency.com",
        "AgencyAdmin123!",
        "Sarah Admin"
    )
    if admin:
        users.append(admin)
    
    # 3. Model user
    model = register_user(
        "model@testagency.com",
        "ModelUser123!",
        "Emma Model"
    )
    if model:
        users.append(model)
    
    # 4. Chatter user
    chatter = register_user(
        "chatter@testagency.com",
        "ChatterUser123!",
        "Chris Chatter"
    )
    if chatter:
        users.append(chatter)
    
    # 5. Competitor agency owner
    competitor = register_user(
        "owner@competitor.com",
        "CompetitorOwner123!",
        "Jane Competitor",
        "Competitor Agency"
    )
    if competitor:
        users.append(competitor)
    
    print("\n" + "=" * 60)
    print(f"Created {len(users)} test users")
    print("=" * 60)
    
    print("\n📝 Test Credentials:")
    print("-" * 40)
    print("AGENCY OWNER:")
    print("  Email: owner@testagency.com")
    print("  Password: AgencyOwner123!")
    print("\nAGENCY ADMIN:")
    print("  Email: admin@testagency.com")
    print("  Password: AgencyAdmin123!")
    print("\nMODEL:")
    print("  Email: model@testagency.com")
    print("  Password: ModelUser123!")
    print("\nCHATTER:")
    print("  Email: chatter@testagency.com")
    print("  Password: ChatterUser123!")
    print("\nCOMPETITOR:")
    print("  Email: owner@competitor.com")
    print("  Password: CompetitorOwner123!")
    
    print("\n⚠️  Note: Users are created with default 'agency_member' role.")
    print("Role elevation and agency assignment need to be done manually via database.")


if __name__ == "__main__":
    main()