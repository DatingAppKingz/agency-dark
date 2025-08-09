#!/usr/bin/env python3
"""Reset test user password"""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.security_v2 import hash_password
from core.domain.models import User


async def reset_test_user_password():
    """Reset test user password to password123"""
    async with AsyncSessionLocal() as session:
        try:
            # Find test user
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Update password
                user.hashed_password = hash_password("password123")
                await session.commit()
                print(f"✅ Password reset for {user.email}")
                print(f"   Email: test@example.com")
                print(f"   Password: password123")
            else:
                print("❌ User test@example.com not found")
                
        except Exception as e:
            await session.rollback()
            print(f"❌ Error: {e}")
            raise


async def main():
    """Run the reset script"""
    await reset_test_user_password()


if __name__ == "__main__":
    asyncio.run(main())