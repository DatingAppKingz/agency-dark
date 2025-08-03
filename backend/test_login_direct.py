#!/usr/bin/env python3
"""
Direct test of login functionality
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from core.config import settings
from models.user import User
from core.security import verify_password

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def test_login():
    """Test login directly"""
    async with AsyncSessionLocal() as db:
        try:
            # Find user
            result = await db.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ User not found")
                return
                
            print(f"✅ User found: {user.email}")
            print(f"   Active: {user.is_active}")
            print(f"   Verified: {user.is_verified}")
            print(f"   Role: {user.role}")
            
            # Test password
            password_valid = verify_password("password123", user.hashed_password)
            print(f"   Password valid: {'✅' if password_valid else '❌'}")
            
            if not user.is_active:
                print("❌ User is not active")
            elif not user.is_verified:
                print("❌ User is not verified")
            elif password_valid:
                print("✅ Login should work!")
            else:
                print("❌ Invalid password")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Testing login directly...")
    asyncio.run(test_login())