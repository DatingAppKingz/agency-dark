#!/usr/bin/env python3
"""
Simple script to create test users using raw SQL
"""
import asyncio
import asyncpg
import bcrypt
import uuid
from datetime import datetime
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost:5432/agencydark")
# Convert to asyncpg format
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def create_test_users():
    """Create test users directly in database"""
    # Connect to database
    conn = await asyncpg.connect(f"postgresql://{DATABASE_URL}")
    
    try:
        # Create test agency
        agency_id = uuid.uuid4()
        agency_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM agencies WHERE domain = $1)",
            "test-agency"
        )
        
        if not agency_exists:
            await conn.execute("""
                INSERT INTO agencies (id, name, slug, domain, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, agency_id, "Test Agency", "test-agency", "test-agency", datetime.utcnow(), datetime.utcnow())
            print(f"✅ Created test agency: Test Agency")
        else:
            agency_id = await conn.fetchval(
                "SELECT id FROM agencies WHERE domain = $1",
                "test-agency"
            )
            print(f"ℹ️  Test agency already exists")
        
        # Test users data
        test_users = [
            {
                "email": "test@example.com",
                "username": "testuser",
                "password": "password123",
                "role": "agency_admin",
                "description": "Agency Admin"
            },
            {
                "email": "admin@example.com",
                "username": "admin",
                "password": "admin123",
                "role": "super_admin",
                "description": "Super Admin"
            },
            {
                "email": "model@example.com",
                "username": "modeluser",
                "password": "model123",
                "role": "model",
                "description": "Model"
            },
            {
                "email": "chatter@example.com",
                "username": "chatteruser",
                "password": "chatter123",
                "role": "chatter",
                "description": "Chatter"
            }
        ]
        
        for user_data in test_users:
            user_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM users WHERE email = $1)",
                user_data["email"]
            )
            
            if not user_exists:
                user_id = uuid.uuid4()
                hashed_password = hash_password(user_data["password"])
                
                await conn.execute("""
                    INSERT INTO users (
                        id, email, full_name, hashed_password, agency_id, 
                        role, is_active, is_verified, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, 
                    user_id, 
                    user_data["email"], 
                    user_data["username"],  # Using username as full_name
                    hashed_password, 
                    agency_id,
                    user_data["role"], 
                    True, 
                    True, 
                    datetime.utcnow(), 
                    datetime.utcnow()
                )
                print(f"✅ Created {user_data['description']} user: {user_data['email']}")
                print(f"   Password: {user_data['password']}")
            else:
                print(f"ℹ️  User already exists: {user_data['email']}")
        
        print("\n✅ Test user creation complete!")
        print("\nYou can now login with:")
        print("- test@example.com / password123 (Agency Admin)")
        print("- admin@example.com / admin123 (Super Admin)")
        print("- model@example.com / model123 (Model)")
        print("- chatter@example.com / chatter123 (Chatter)")
        
    except Exception as e:
        print(f"❌ Error creating test users: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


if __name__ == "__main__":
    print("Creating test users for AgencyDark...")
    asyncio.run(create_test_users())