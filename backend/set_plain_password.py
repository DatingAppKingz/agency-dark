#!/usr/bin/env python3
"""
Set plain text password for admin user
"""

import asyncio
import asyncpg
import os

async def set_plain_password():
    """Set plain text password for admin user"""
    
    # Database connection
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    print("Setting plain text password for admin@agency.com...")
    
    # Update the password to plain text
    result = await conn.execute("""
        UPDATE users 
        SET hashed_password = 'admin123'
        WHERE email = 'admin@agency.com'
    """)
    
    if result == "UPDATE 1":
        print("✅ Password set to plain text 'admin123' for admin@agency.com")
    else:
        print("⚠️  User admin@agency.com not found in database")
    
    # Verify the password was set
    row = await conn.fetchrow("""
        SELECT email, hashed_password 
        FROM users 
        WHERE email = 'admin@agency.com'
    """)
    
    if row:
        print(f"Verification: {row['email']} has password: {row['hashed_password']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(set_plain_password())