#!/usr/bin/env python3
"""
Create test users directly in the database
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import uuid
from datetime import datetime

# Database connection
DB_URL = "postgresql://postgres:i6cx9yJ3vBLHT6nb@db.qrabdwmdewqzpozgfiju.supabase.co:5432/postgres"

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_test_data():
    """Create test users and agencies"""
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    try:
        # Create main agency
        agency_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO agencies (id, name, slug, domain, subscription_status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, (
            agency_id,
            "Test Agency Premium",
            "test-agency-premium",
            "premium.testagency.com",
            "ACTIVE",
            datetime.utcnow(),
            datetime.utcnow()
        ))
        result = cur.fetchone()
        if result:
            agency_id = result['id']
        print(f"✅ Created agency: Test Agency Premium (ID: {agency_id})")
        
        # Create users with different roles
        users = [
            {
                "email": "superadmin@agencydark.com",
                "password": "SuperAdmin123!",
                "full_name": "Super Administrator",
                "role": "SUPER_ADMIN",
                "agency_id": None
            },
            {
                "email": "owner@testagency.com",
                "password": "AgencyOwner123!",
                "full_name": "John Agency Owner",
                "role": "AGENCY_OWNER",
                "agency_id": agency_id
            },
            {
                "email": "admin@testagency.com",
                "password": "AgencyAdmin123!",
                "full_name": "Sarah Admin",
                "role": "AGENCY_ADMIN",
                "agency_id": agency_id
            },
            {
                "email": "member@testagency.com",
                "password": "AgencyMember123!",
                "full_name": "Mike Member",
                "role": "AGENCY_MEMBER",
                "agency_id": agency_id
            },
            {
                "email": "model@testagency.com",
                "password": "ModelUser123!",
                "full_name": "Emma Model",
                "role": "MODEL",
                "agency_id": agency_id
            },
            {
                "email": "chatter@testagency.com",
                "password": "ChatterUser123!",
                "full_name": "Chris Chatter",
                "role": "CHATTER",
                "agency_id": agency_id
            }
        ]
        
        for user_data in users:
            user_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO users (
                    id, agency_id, email, hashed_password, full_name, 
                    role, is_active, is_verified, verified_at, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET 
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    hashed_password = EXCLUDED.hashed_password
                RETURNING id
            """, (
                user_id,
                user_data["agency_id"],
                user_data["email"],
                hash_password(user_data["password"]),
                user_data["full_name"],
                user_data["role"],
                True,
                True,
                datetime.utcnow(),
                datetime.utcnow(),
                datetime.utcnow()
            ))
            
            result = cur.fetchone()
            if result:
                user_id = result['id']
            
            print(f"✅ Created {user_data['role']}: {user_data['email']}")
            
            # Create model profile for MODEL user
            if user_data["role"] == "MODEL":
                model_profile_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO model_profiles (
                        id, user_id, agency_id, stage_name, 
                        onlyfans_username, subscription_price, is_active,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    model_profile_id,
                    user_id,
                    agency_id,
                    "Emma Rose",
                    "emmarose_of",
                    9.99,
                    True,
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
                print(f"   📸 Created model profile: Emma Rose")
        
        # Create commission rules
        tiers = [
            ("TIER_1", "Tier 1 - Starter", 70.00, 0, 5000),
            ("TIER_2", "Tier 2 - Growth", 65.00, 5001, 10000),
            ("TIER_3", "Tier 3 - Premium", 60.00, 10001, None)
        ]
        
        for tier, name, percentage, min_subs, max_subs in tiers:
            cur.execute("""
                INSERT INTO commission_rules (
                    id, agency_id, name, tier, percentage,
                    min_subscribers, max_subscribers, is_active,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(uuid.uuid4()),
                agency_id,
                name,
                tier,
                percentage,
                min_subs,
                max_subs,
                True,
                datetime.utcnow(),
                datetime.utcnow()
            ))
        print("✅ Created commission rules")
        
        conn.commit()
        print("\n" + "="*60)
        print("Test data created successfully!")
        print("="*60)
        
        print("\n📝 Test Credentials:")
        print("-" * 40)
        for user in users:
            print(f"{user['role']}:")
            print(f"  Email: {user['email']}")
            print(f"  Password: {user['password']}")
            print()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_test_data()