#!/usr/bin/env python3
"""
Hash passwords for all test accounts from TEST_DATA_GUIDE.md
"""

import asyncio
import asyncpg
import os
from passlib.context import CryptContext

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test accounts that need password hashing
TEST_ACCOUNTS = [
    {"email": "model1@example.com", "password": "ModelPass123!"},
    {"email": "model2@example.com", "password": "ModelPass123!"},
    {"email": "model3@example.com", "password": "ModelPass123!"},
    {"email": "agency_owner1@example.com", "password": "OwnerPass123!"},
    {"email": "agency_admin1@example.com", "password": "AdminPass123!"},
    {"email": "agency_user1@example.com", "password": "UserPass123!"},
    {"email": "client1@example.com", "password": "ClientPass123!"},
    {"email": "viewer1@example.com", "password": "ViewerPass123!"},
]

async def hash_passwords():
    """Hash passwords for all test accounts"""
    
    # Database connection
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Hashing passwords for test accounts...")
    print("=" * 60)
    
    for account in TEST_ACCOUNTS:
        email = account["email"]
        password = account["password"]
        hashed = pwd_context.hash(password)
        
        # Update the password in the database
        result = await conn.execute("""
            UPDATE users 
            SET hashed_password = $1 
            WHERE email = $2
        """, hashed, email)
        
        if result == "UPDATE 1":
            print(f"✅ Updated password for {email}")
        else:
            print(f"⚠️  User {email} not found in database")
    
    await conn.close()
    
    print("=" * 60)
    print("Password hashing complete!")
    
    # Also print a summary
    print("\nYou can now login with these accounts:")
    for account in TEST_ACCOUNTS:
        print(f"  - {account['email']} / {account['password']}")

if __name__ == "__main__":
    asyncio.run(hash_passwords())