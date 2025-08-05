"""Check database schema and find existing users."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ['DATABASE_URL'] = 'postgresql+asyncpg://mariuszbudzisz@localhost/agencydark_dev'

from core.database import engine

async def check_schema():
    """Check database schema and users."""
    async with AsyncSession(engine) as session:
        # Check users table columns
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """))
        
        print("Users table columns:")
        for row in result:
            print(f"  - {row[0]}: {row[1]}")
        
        # Check if any users exist
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        print(f"\nTotal users in database: {user_count}")
        
        if user_count > 0:
            # Get first few users
            result = await session.execute(text("""
                SELECT id, email, first_name, last_name, is_active 
                FROM users 
                LIMIT 5
            """))
            print("\nExisting users:")
            for row in result:
                print(f"  - ID: {row[0]}, Email: {row[1]}, Name: {row[2]} {row[3]}, Active: {row[4]}")
        
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())