"""Create a test user for authentication testing."""
import asyncio
import os
from datetime import datetime
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Set up environment
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://mariuszbudzisz@localhost/agencydark_dev'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['JWT_SECRET_KEY'] = 'your-secret-key-here'
os.environ['DISABLE_ML'] = 'true'

from core.database import engine, Base
from models.agency import Agency
from models.user import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_data():
    """Create test agency and user."""
    async with AsyncSession(engine) as session:
        # Check if agency exists
        result = await session.execute(select(Agency).where(Agency.name == "Test Agency"))
        agency = result.scalar_one_or_none()
        
        if not agency:
            # Create test agency
            agency = Agency(
                name="Test Agency",
                domain="testagency",
                email="admin@testagency.com",
                settings={},
                is_active=True
            )
            session.add(agency)
            await session.commit()
            await session.refresh(agency)
            print(f"Created agency: {agency.name} (ID: {agency.id})")
        else:
            print(f"Agency already exists: {agency.name} (ID: {agency.id})")
        
        # Check if user exists
        result = await session.execute(select(User).where(User.email == "admin@agency.com"))
        user = result.scalar_one_or_none()
        
        if not user:
            # Create test user
            user = User(
                agency_id=agency.id,
                email="admin@agency.com",
                username="admin",
                password_hash=pwd_context.hash("admin123"),
                first_name="Admin",
                last_name="User",
                role=UserRole.AGENCY_OWNER,
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
            print(f"Created user: {user.email} with password: admin123")
        else:
            print(f"User already exists: {user.email}")
        
        # Close the engine
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_test_data())