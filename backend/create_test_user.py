#!/usr/bin/env python3
"""Create a simple test user for API testing"""

import asyncio
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal, create_tables
from core.security import get_password_hash
from core.domain.models import Agency, User, UserRole


async def create_test_data():
    """Create test agency and user"""
    async with AsyncSessionLocal() as session:
        try:
            # Create test agency
            agency = Agency(
                id=uuid.uuid4(),
                name="Test Agency",
                slug="test-agency",
                domain="test.agency.com",
                subscription_status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(agency)
            await session.flush()
            
            # Create test user
            user = User(
                id=uuid.uuid4(),
                agency_id=agency.id,
                email="test@example.com",
                hashed_password=get_password_hash("password123"),
                full_name="Test User",
                role=UserRole.AGENCY_ADMIN,
                is_active=True,
                is_verified=True,
                verified_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(user)
            
            await session.commit()
            print(f"✅ Created test agency: {agency.name} (ID: {agency.id})")
            print(f"✅ Created test user: {user.email} with password: password123")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating test data: {e}")
            raise


async def main():
    """Run the seed script"""
    print("Creating test data...")
    await create_tables()
    await create_test_data()
    print("✅ Test data created successfully!")


if __name__ == "__main__":
    asyncio.run(main())