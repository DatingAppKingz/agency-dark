#!/usr/bin/env python3
"""
Script to create a test user for development/testing
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db, engine
from models.user import User, UserRole
from models.agency import Agency
from core.security import get_password_hash
import uuid
from datetime import datetime


async def create_test_user():
    """Create a test user and agency"""
    async with AsyncSession(engine) as session:
        try:
            # Check if test agency exists
            from sqlalchemy import select
            result = await session.execute(
                select(Agency).where(Agency.domain == "test-agency")
            )
            agency = result.scalar_one_or_none()
            
            if not agency:
                # Create test agency
                agency = Agency(
                    id=uuid.uuid4(),
                    name="Test Agency",
                    domain="test-agency",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                session.add(agency)
                await session.commit()
                print(f"✅ Created test agency: {agency.name}")
            else:
                print(f"ℹ️  Test agency already exists: {agency.name}")
            
            # Check if test user exists
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Create test user
                user = User(
                    id=uuid.uuid4(),
                    email="test@example.com",
                    username="testuser",
                    hashed_password=get_password_hash("password123"),
                    agency_id=agency.id,
                    role=UserRole.AGENCY_ADMIN,
                    is_active=True,
                    is_verified=True,
                    created_at=datetime.utcnow()
                )
                session.add(user)
                await session.commit()
                print(f"✅ Created test user: {user.email}")
                print(f"   Username: {user.username}")
                print(f"   Password: password123")
                print(f"   Role: {user.role.value}")
            else:
                print(f"ℹ️  Test user already exists: {user.email}")
                
            # Create additional test users
            test_users = [
                {
                    "email": "admin@example.com",
                    "username": "admin",
                    "password": "admin123",
                    "role": UserRole.SUPER_ADMIN
                },
                {
                    "email": "model@example.com", 
                    "username": "modeluser",
                    "password": "model123",
                    "role": UserRole.MODEL
                },
                {
                    "email": "chatter@example.com",
                    "username": "chatteruser",
                    "password": "chatter123",
                    "role": UserRole.CHATTER
                }
            ]
            
            for test_user_data in test_users:
                result = await session.execute(
                    select(User).where(User.email == test_user_data["email"])
                )
                existing_user = result.scalar_one_or_none()
                
                if not existing_user:
                    new_user = User(
                        id=uuid.uuid4(),
                        email=test_user_data["email"],
                        username=test_user_data["username"],
                        hashed_password=get_password_hash(test_user_data["password"]),
                        agency_id=agency.id,
                        role=test_user_data["role"],
                        is_active=True,
                        is_verified=True,
                        created_at=datetime.utcnow()
                    )
                    session.add(new_user)
                    await session.commit()
                    print(f"✅ Created {test_user_data['role'].value} user: {test_user_data['email']}")
                    print(f"   Password: {test_user_data['password']}")
                else:
                    print(f"ℹ️  User already exists: {test_user_data['email']}")
                    
        except Exception as e:
            print(f"❌ Error creating test users: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    print("Creating test users for AgencyDark...")
    asyncio.run(create_test_user())
    print("\n✅ Test user creation complete!")
    print("\nYou can now login with:")
    print("- test@example.com / password123 (Agency Admin)")
    print("- admin@example.com / admin123 (Super Admin)")
    print("- model@example.com / model123 (Model)")
    print("- chatter@example.com / chatter123 (Chatter)")