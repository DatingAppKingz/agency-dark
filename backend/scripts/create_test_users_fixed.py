#!/usr/bin/env python3
"""
Create test users with proper password hashing
"""
import asyncio
import asyncpg
import uuid
from datetime import datetime
import os
import sys
from passlib.context import CryptContext

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost:5432/agencydark")
# Convert to asyncpg format
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "")

# Use the same password context as the auth service
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a password using the same method as auth service"""
    return pwd_context.hash(password)


async def create_test_users():
    """Create test users directly in database"""
    # Connect to database
    conn = await asyncpg.connect(f"postgresql://{DATABASE_URL}")
    
    try:
        # Get the test agency
        agency_id = await conn.fetchval(
            "SELECT id FROM agencies WHERE domain = $1",
            "test-agency"
        )
        
        if not agency_id:
            print("❌ Test agency not found. Please run the previous script first.")
            return
        
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
            # Delete existing user if any
            await conn.execute(
                "DELETE FROM users WHERE email = $1",
                user_data["email"]
            )
            
            # Create new user with proper password hash
            user_id = uuid.uuid4()
            hashed_password = get_password_hash(user_data["password"])
            
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
            print(f"✅ Recreated {user_data['description']} user: {user_data['email']}")
            print(f"   Password: {user_data['password']}")
            print(f"   Hash (first 20 chars): {hashed_password[:20]}...")
        
        # Test password verification
        print("\n🔍 Testing password verification...")
        test_hash = await conn.fetchval(
            "SELECT hashed_password FROM users WHERE email = $1",
            "test@example.com"
        )
        if test_hash:
            verify_result = pwd_context.verify("password123", test_hash)
            print(f"   Verification test: {'✅ PASSED' if verify_result else '❌ FAILED'}")
        
        print("\n✅ Test user recreation complete!")
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
    print("Recreating test users with proper password hashing...")
    asyncio.run(create_test_users())