"""Seed initial data for development."""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os

from models.base import Base
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model, ModelStatus, Platform
from api.v1.endpoints.auth_simple import get_password_hash
from seed_config import get_seed_config, SEED_USERS

# Override DATABASE_URL to use the external port
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/agencydark"
)


async def seed_data():
    """Seed initial data."""
    print("Seeding initial data...")
    
    # Create engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as db:
        # Check if data already exists
        stmt = select(User).limit(1)
        existing_user = await db.scalar(stmt)
        
        if existing_user:
            print("Data already exists, skipping seed.")
            return
        
        # Create agencies
        print("Creating agencies...")
        
        agency1 = Agency(
            name="Elite Models Agency",
            slug="elite-models",
            email="admin@elitemodels.com",
            phone="+1234567890",
            country="US",
            timezone="America/New_York",
            primary_color="#3B82F6",
            secondary_color="#1E40AF",
            default_commission_rate=20.00,
            max_models=50,
            max_chatters=25,
            is_active=True,
            is_verified=True
        )
        
        agency2 = Agency(
            name="Premium Content Creators",
            slug="premium-creators",
            email="hello@premiumcreators.com",
            phone="+0987654321",
            country="UK",
            timezone="Europe/London",
            primary_color="#10B981",
            secondary_color="#059669",
            default_commission_rate=25.00,
            max_models=30,
            max_chatters=15,
            is_active=True,
            is_verified=True
        )
        
        db.add_all([agency1, agency2])
        await db.commit()
        
        # Create users
        print("Creating users...")
        
        # Super admin
        super_admin = User(
            email="admin@agencydark.com",
            username="admin",
            password_hash=get_password_hash(SEED_USERS["super_admin"]["password"]),
            first_name="Super",
            last_name="Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
            is_superuser=True
        )
        
        # Agency owners
        agency1_owner = User(
            email="owner@elitemodels.com",
            username="elite_owner",
            password_hash=get_password_hash(SEED_USERS["agency_owner"]["password"]),
            first_name="John",
            last_name="Elite",
            role=UserRole.AGENCY_OWNER,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        agency2_owner = User(
            email="owner@premiumcreators.com",
            username="premium_owner",
            password_hash=get_password_hash(SEED_USERS["agency_owner"]["password"]),
            first_name="Jane",
            last_name="Premium",
            role=UserRole.AGENCY_OWNER,
            agency_id=agency2.id,
            is_active=True,
            is_verified=True
        )
        
        # Agency admins
        agency1_admin = User(
            email="admin@elitemodels.com",
            username="elite_admin",
            password_hash=get_password_hash(SEED_USERS["super_admin"]["password"]),
            first_name="Admin",
            last_name="Elite",
            role=UserRole.AGENCY_ADMIN,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        # Models
        model1_user = User(
            email="sarah@elitemodels.com",
            username="sarah_model",
            password_hash=get_password_hash(SEED_USERS["model"]["password"]),
            first_name="Sarah",
            last_name="Johnson",
            role=UserRole.MODEL,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        model2_user = User(
            email="emma@elitemodels.com",
            username="emma_model",
            password_hash=get_password_hash(SEED_USERS["model"]["password"]),
            first_name="Emma",
            last_name="Wilson",
            role=UserRole.MODEL,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        model3_user = User(
            email="olivia@premiumcreators.com",
            username="olivia_model",
            password_hash=get_password_hash(SEED_USERS["model"]["password"]),
            first_name="Olivia",
            last_name="Brown",
            role=UserRole.MODEL,
            agency_id=agency2.id,
            is_active=True,
            is_verified=True
        )
        
        # Chatters
        chatter1 = User(
            email="mike@elitemodels.com",
            username="mike_chatter",
            password_hash=get_password_hash(SEED_USERS["chatter"]["password"]),
            first_name="Mike",
            last_name="Davis",
            role=UserRole.CHATTER,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        chatter2 = User(
            email="lisa@elitemodels.com",
            username="lisa_chatter",
            password_hash=get_password_hash(SEED_USERS["chatter"]["password"]),
            first_name="Lisa",
            last_name="Garcia",
            role=UserRole.CHATTER,
            agency_id=agency1.id,
            is_active=True,
            is_verified=True
        )
        
        db.add_all([
            super_admin, agency1_owner, agency2_owner, agency1_admin,
            model1_user, model2_user, model3_user, chatter1, chatter2
        ])
        await db.commit()
        
        # Create model profiles
        print("Creating model profiles...")
        
        model1 = Model(
            user_id=model1_user.id,
            agency_id=agency1.id,
            stage_name="Sarah J",
            real_name="Sarah Johnson",
            bio="Fitness enthusiast and lifestyle blogger",
            platform=Platform.ONLYFANS,
            platform_username="sarahj_fitness",
            platform_url="https://onlyfans.com/sarahj_fitness",
            status=ModelStatus.ACTIVE,
            verification_status="verified",
            profile_photo_url="https://example.com/sarah.jpg",
            followers_count=15000,
            posts_count=450,
            total_earnings=25000.00,
            categories=["fitness", "lifestyle"],
            tags=["gym", "health", "motivation"],
            languages=["en"],
            chat_enabled=True
        )
        
        model2 = Model(
            user_id=model2_user.id,
            agency_id=agency1.id,
            stage_name="Emma W",
            real_name="Emma Wilson",
            bio="Travel blogger and photographer",
            platform=Platform.ONLYFANS,
            platform_username="emma_travels",
            platform_url="https://onlyfans.com/emma_travels",
            status=ModelStatus.ACTIVE,
            verification_status="verified",
            profile_photo_url="https://example.com/emma.jpg",
            followers_count=22000,
            posts_count=680,
            total_earnings=38000.00,
            categories=["travel", "photography"],
            tags=["wanderlust", "adventure", "explore"],
            languages=["en", "es"],
            chat_enabled=True
        )
        
        model3 = Model(
            user_id=model3_user.id,
            agency_id=agency2.id,
            stage_name="Olivia B",
            real_name="Olivia Brown",
            bio="Fashion and beauty influencer",
            platform=Platform.FANSLY,
            platform_username="oliviab_style",
            platform_url="https://fansly.com/oliviab_style",
            status=ModelStatus.ACTIVE,
            verification_status="verified",
            profile_photo_url="https://example.com/olivia.jpg",
            followers_count=18500,
            posts_count=520,
            total_earnings=31000.00,
            categories=["fashion", "beauty"],
            tags=["style", "makeup", "ootd"],
            languages=["en", "fr"],
            chat_enabled=True
        )
        
        db.add_all([model1, model2, model3])
        await db.commit()
        
        print("\nInitial data seeded successfully!")
        
        # Only show test accounts in development
        config = get_seed_config()
        if config["environment"] == "development":
            print("\nTest Accounts (DEVELOPMENT ONLY):")
            print("=================================\n")
            print("Super Admin:")
            print(f"  Email: {SEED_USERS['super_admin']['email']}")
            print("  Password: [Set via SEED_ADMIN_PASSWORD env var]\n")
            
            print("Agency Owner (Elite Models):")
            print(f"  Email: {SEED_USERS['agency_owner']['email']}")
            print("  Password: [Set via SEED_OWNER_PASSWORD env var]\n")
            
            print("Model (Sarah):")
            print(f"  Email: {SEED_USERS['model']['email']}")
            print("  Password: [Set via SEED_MODEL_PASSWORD env var]\n")
            
            print("Chatter (Mike):")
            print(f"  Email: {SEED_USERS['chatter']['email']}")
            print("  Password: [Set via SEED_CHATTER_PASSWORD env var]\n")
        else:
            print("\nRunning in production mode - test account details hidden.")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())