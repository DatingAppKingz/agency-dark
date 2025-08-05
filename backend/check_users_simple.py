"""Check existing users in the database."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ['DATABASE_URL'] = 'postgresql+asyncpg://mariuszbudzisz@localhost/agencydark_dev'

from core.database import engine

async def check_users():
    """Check existing users."""
    async with AsyncSession(engine) as session:
        # Get all users
        result = await session.execute(text("""
            SELECT id, email, full_name, role, is_active, is_verified 
            FROM users 
            WHERE is_active = true
            ORDER BY created_at DESC
            LIMIT 10
        """))
        
        print("Active users in database:")
        for row in result:
            print(f"\nID: {row[0]}")
            print(f"Email: {row[1]}")
            print(f"Name: {row[2]}")
            print(f"Role: {row[3]}")
            print(f"Active: {row[4]}, Verified: {row[5]}")
        
        # Check for admin user
        result = await session.execute(text("""
            SELECT email FROM users 
            WHERE email = 'admin@agency.com'
        """))
        admin = result.scalar()
        
        if admin:
            print(f"\n✓ Admin user exists: {admin}")
        else:
            print("\n✗ Admin user (admin@agency.com) does not exist")
        
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_users())