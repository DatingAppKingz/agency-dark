"""Simple seed script for test data."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_database():
    """Seed database with test data."""
    async with AsyncSessionLocal() as session:
        try:
            # Hash the test password once
            hashed_password = pwd_context.hash("admin123")
            
            # 1. Insert test users
            print("Creating users...")
            await session.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at, agency_id) 
                VALUES 
                -- Super Admin
                (:id1, :email1, :password, :name1, :role1, true, true, NOW(), NOW(), NULL),
                -- Agency Owner (Elite Models)
                (:id2, :email2, :password, :name2, :role2, true, true, NOW(), NOW(), :agency1),
                -- Agency Admin
                (:id3, :email3, :password, :name3, :role3, true, true, NOW(), NOW(), :agency1),
                -- Models
                (:id4, :email4, :password, :name4, :role4, true, true, NOW(), NOW(), :agency1),
                (:id5, :email5, :password, :name5, :role4, true, true, NOW(), NOW(), :agency1),
                (:id6, :email6, :password, :name6, :role4, true, true, NOW(), NOW(), :agency1),
                -- Chatters
                (:id7, :email7, :password, :name7, :role5, true, true, NOW(), NOW(), :agency1),
                (:id8, :email8, :password, :name8, :role5, true, true, NOW(), NOW(), :agency1),
                -- Agency Member
                (:id9, :email9, :password, :name9, :role6, true, true, NOW(), NOW(), :agency1),
                -- Premium Talent Agency
                (:id10, :email10, :password, :name10, :role2, true, true, NOW(), NOW(), :agency2),
                (:id11, :email11, :password, :name11, :role4, true, true, NOW(), NOW(), :agency2),
                (:id12, :email12, :password, :name12, :role4, true, true, NOW(), NOW(), :agency2),
                (:id13, :email13, :password, :name13, :role5, true, true, NOW(), NOW(), :agency2),
                -- Rising Stars Agency
                (:id14, :email14, :password, :name14, :role2, true, true, NOW(), NOW(), :agency3),
                (:id15, :email15, :password, :name15, :role4, true, true, NOW(), NOW(), :agency3)
            """), {
                "password": hashed_password,
                # Super Admin
                "id1": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "email1": "admin@agency.com",
                "name1": "Super Admin",
                "role1": "SUPER_ADMIN",
                # Elite Models Agency staff
                "agency1": "11111111-1111-1111-1111-111111111111",
                "id2": "b1111111-1111-1111-1111-111111111111",
                "email2": "owner@elitemodels.com",
                "name2": "James Thompson",
                "role2": "AGENCY_OWNER",
                "id3": "b2222222-2222-2222-2222-222222222222",
                "email3": "admin@elitemodels.com",
                "name3": "Mary Johnson",
                "role3": "AGENCY_ADMIN",
                "id4": "b3333333-3333-3333-3333-333333333333",
                "email4": "sarah@elitemodels.com",
                "name4": "Sarah Johnson",
                "role4": "MODEL",
                "id5": "b4444444-4444-4444-4444-444444444444",
                "email5": "emma@elitemodels.com",
                "name5": "Emma Davis",
                "id6": "b5555555-5555-5555-5555-555555555555",
                "email6": "lisa@elitemodels.com",
                "name6": "Lisa Brown",
                "id7": "b6666666-6666-6666-6666-666666666666",
                "email7": "john@elitemodels.com",
                "name7": "John Smith",
                "role5": "CHATTER",
                "id8": "b7777777-7777-7777-7777-777777777777",
                "email8": "mike@elitemodels.com",
                "name8": "Mike Wilson",
                "id9": "b8888888-8888-8888-8888-888888888888",
                "email9": "support@elitemodels.com",
                "name9": "Support Staff",
                "role6": "AGENCY_MEMBER",
                # Premium Talent
                "agency2": "22222222-2222-2222-2222-222222222222",
                "id10": "c1111111-1111-1111-1111-111111111111",
                "email10": "owner@premiumtalent.com",
                "name10": "Robert Martinez",
                "id11": "c2222222-2222-2222-2222-222222222222",
                "email11": "jessica@premiumtalent.com",
                "name11": "Jessica White",
                "id12": "c3333333-3333-3333-3333-333333333333",
                "email12": "ashley@premiumtalent.com",
                "name12": "Ashley Green",
                "id13": "c4444444-4444-4444-4444-444444444444",
                "email13": "alex@premiumtalent.com",
                "name13": "Alex Turner",
                # Rising Stars
                "agency3": "33333333-3333-3333-3333-333333333333",
                "id14": "d1111111-1111-1111-1111-111111111111",
                "email14": "owner@risingstars.com",
                "name14": "Linda Chen",
                "id15": "d2222222-2222-2222-2222-222222222222",
                "email15": "sophia@risingstars.com",
                "name15": "Sophia Rodriguez",
            })
            
            print("✓ Created 15 users")
            
            await session.commit()
            print("\n✅ Test data seeded successfully!")
            
            # Show summary
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"\nTotal users in database: {user_count}")
            
            # Show users by role
            result = await session.execute(text("""
                SELECT role, COUNT(*) as count 
                FROM users 
                GROUP BY role 
                ORDER BY role
            """))
            print("\nUsers by role:")
            for row in result:
                print(f"  {row.role}: {row.count}")
                
            print("\nAll test users use password: admin123")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await session.rollback()
        finally:
            await session.close()

async def main():
    """Main function."""
    print("🌱 Seeding database with test data...")
    await seed_database()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())