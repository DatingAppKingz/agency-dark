#!/usr/bin/env python3
"""Create test agency if it doesn't exist"""

import asyncio
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.domain.models import Agency, SubscriptionStatus


async def create_test_agency():
    """Create test agency"""
    async with AsyncSessionLocal() as session:
        try:
            # Check if agency exists
            result = await session.execute(
                select(Agency).where(Agency.slug == "test-agency")
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"✅ Test agency already exists: {existing.name}")
                return existing
            
            # Create new agency
            agency = Agency(
                id=uuid.uuid4(),
                name="Test Agency",
                slug="test-agency",
                domain="test.agency.com",
                subscription_status=SubscriptionStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(agency)
            await session.commit()
            
            print(f"✅ Created test agency: {agency.name} (ID: {agency.id})")
            return agency
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating agency: {e}")
            raise


async def main():
    """Run the script"""
    await create_test_agency()


if __name__ == "__main__":
    asyncio.run(main())