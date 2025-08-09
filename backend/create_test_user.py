"""
Create a test user for authentication testing.
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import engine
from core.security_v2 import hash_password
import uuid


async def create_test_user():
    """Create a test user directly in the database."""
    async with engine.begin() as conn:
        # Check if user exists
        result = await conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "admin@agency.com"}
        )
        existing = result.fetchone()
        
        if existing:
            print(f"User admin@agency.com already exists with ID: {existing[0]}")
            # Update password just in case
            await conn.execute(
                text("UPDATE users SET hashed_password = :password WHERE email = :email"),
                {
                    "email": "admin@agency.com",
                    "password": hash_password("admin123")
                }
            )
            print("Password updated to 'admin123'")
        else:
            # Create new user with minimal fields that exist in DB
            user_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO users (
                        id, email, hashed_password, 
                        is_active, is_verified, is_superuser,
                        role, permissions,
                        created_at, updated_at
                    ) VALUES (
                        :id, :email, :password,
                        true, true, true,
                        'super_admin', '{}',
                        NOW(), NOW()
                    )
                """),
                {
                    "id": user_id,
                    "email": "admin@agency.com",
                    "password": hash_password("admin123")
                }
            )
            print(f"Created user admin@agency.com with ID: {user_id}")
            print("Password: admin123")


if __name__ == "__main__":
    asyncio.run(create_test_user())