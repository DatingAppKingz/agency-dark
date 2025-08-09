"""Create test admin user."""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import engine
from models.user import User
from passlib.context import CryptContext
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

async def create_admin():
    """Create admin user."""
    async with AsyncSession(engine) as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Admin user already exists with id: {existing.id}")
            return
        
        # Create admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            first_name="Admin",
            last_name="User",
            role="admin",
            is_active=True,
            is_verified=True,
            is_superuser=True,
            email_verified_at=datetime.utcnow()
        )
        
        session.add(admin)
        await session.commit()
        print(f"Admin user created with id: {admin.id}")

if __name__ == "__main__":
    asyncio.run(create_admin())