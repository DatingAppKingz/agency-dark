"""Test password verification."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

os.environ['DATABASE_URL'] = 'postgresql+asyncpg://mariuszbudzisz@localhost/agencydark_dev'

from core.database import engine

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def test_password():
    """Test admin password."""
    async with AsyncSession(engine) as session:
        # Get admin user's hashed password
        result = await session.execute(text("""
            SELECT hashed_password 
            FROM users 
            WHERE email = 'admin@agency.com'
        """))
        
        hashed_password = result.scalar()
        
        if hashed_password:
            print(f"Found admin user")
            print(f"Hashed password starts with: {hashed_password[:20]}...")
            
            # Test password
            test_passwords = ['admin123', 'password', 'admin', 'Admin123!', 'password123']
            
            for password in test_passwords:
                if pwd_context.verify(password, hashed_password):
                    print(f"✓ Password '{password}' is correct!")
                    break
                else:
                    print(f"✗ Password '{password}' is incorrect")
        else:
            print("Admin user not found")
        
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_password())