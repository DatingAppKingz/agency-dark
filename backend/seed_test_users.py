"""Seed database with comprehensive test data."""
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
            
            # 1. Create agencies first
            print("Creating agencies...")
            await session.execute(text("""
                INSERT INTO agencies (id, name, slug, created_at, updated_at) 
                VALUES 
                (:id1, :name1, :slug1, NOW(), NOW()),
                (:id2, :name2, :slug2, NOW(), NOW()),
                (:id3, :name3, :slug3, NOW(), NOW())
            """), {
                "id1": "11111111-1111-1111-1111-111111111111",
                "name1": "Elite Models Agency",
                "slug1": "elite-models",
                "id2": "22222222-2222-2222-2222-222222222222",
                "name2": "Premium Talent Management",
                "slug2": "premium-talent",
                "id3": "33333333-3333-3333-3333-333333333333",
                "name3": "Rising Stars Agency",
                "slug3": "rising-stars",
            })
            print("✓ Created 3 agencies")
            
            # 2. Create users
            print("Creating users...")
            
            # Super Admin (no agency)
            await session.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at) 
                VALUES (:id, :email, :password, :name, :role, true, true, NOW(), NOW())
            """), {
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "email": "admin@agency.com",
                "password": hashed_password,
                "name": "Super Admin",
                "role": "SUPER_ADMIN",
            })
            
            # Elite Models Agency users
            users_data = [
                # Agency Owner
                {
                    "id": "b1111111-1111-1111-1111-111111111111",
                    "email": "owner@elitemodels.com",
                    "name": "James Thompson",
                    "role": "AGENCY_OWNER",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                # Agency Admin
                {
                    "id": "b2222222-2222-2222-2222-222222222222",
                    "email": "admin@elitemodels.com",
                    "name": "Mary Johnson",
                    "role": "AGENCY_ADMIN",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                # Models
                {
                    "id": "b3333333-3333-3333-3333-333333333333",
                    "email": "sarah@elitemodels.com",
                    "name": "Sarah Johnson",
                    "role": "MODEL",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                {
                    "id": "b4444444-4444-4444-4444-444444444444",
                    "email": "emma@elitemodels.com",
                    "name": "Emma Davis",
                    "role": "MODEL",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                {
                    "id": "b5555555-5555-5555-5555-555555555555",
                    "email": "lisa@elitemodels.com",
                    "name": "Lisa Brown",
                    "role": "MODEL",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                # Chatters
                {
                    "id": "b6666666-6666-6666-6666-666666666666",
                    "email": "john@elitemodels.com",
                    "name": "John Smith",
                    "role": "CHATTER",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                {
                    "id": "b7777777-7777-7777-7777-777777777777",
                    "email": "mike@elitemodels.com",
                    "name": "Mike Wilson",
                    "role": "CHATTER",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                # Agency Member
                {
                    "id": "b8888888-8888-8888-8888-888888888888",
                    "email": "support@elitemodels.com",
                    "name": "Support Staff",
                    "role": "AGENCY_MEMBER",
                    "agency_id": "11111111-1111-1111-1111-111111111111"
                },
                # Premium Talent users
                {
                    "id": "c1111111-1111-1111-1111-111111111111",
                    "email": "owner@premiumtalent.com",
                    "name": "Robert Martinez",
                    "role": "AGENCY_OWNER",
                    "agency_id": "22222222-2222-2222-2222-222222222222"
                },
                {
                    "id": "c2222222-2222-2222-2222-222222222222",
                    "email": "jessica@premiumtalent.com",
                    "name": "Jessica White",
                    "role": "MODEL",
                    "agency_id": "22222222-2222-2222-2222-222222222222"
                },
                {
                    "id": "c3333333-3333-3333-3333-333333333333",
                    "email": "ashley@premiumtalent.com",
                    "name": "Ashley Green",
                    "role": "MODEL",
                    "agency_id": "22222222-2222-2222-2222-222222222222"
                },
                {
                    "id": "c4444444-4444-4444-4444-444444444444",
                    "email": "alex@premiumtalent.com",
                    "name": "Alex Turner",
                    "role": "CHATTER",
                    "agency_id": "22222222-2222-2222-2222-222222222222"
                },
                # Rising Stars users
                {
                    "id": "d1111111-1111-1111-1111-111111111111",
                    "email": "owner@risingstars.com",
                    "name": "Linda Chen",
                    "role": "AGENCY_OWNER",
                    "agency_id": "33333333-3333-3333-3333-333333333333"
                },
                {
                    "id": "d2222222-2222-2222-2222-222222222222",
                    "email": "sophia@risingstars.com",
                    "name": "Sophia Rodriguez",
                    "role": "MODEL",
                    "agency_id": "33333333-3333-3333-3333-333333333333"
                },
            ]
            
            # Insert users with agencies
            for user in users_data:
                await session.execute(text("""
                    INSERT INTO users (id, email, hashed_password, full_name, role, agency_id, is_active, is_verified, created_at, updated_at) 
                    VALUES (:id, :email, :password, :name, :role, :agency_id, true, true, NOW(), NOW())
                """), {
                    "id": user["id"],
                    "email": user["email"],
                    "password": hashed_password,
                    "name": user["name"],
                    "role": user["role"],
                    "agency_id": user["agency_id"]
                })
            
            print(f"✓ Created {len(users_data) + 1} users")
            
            await session.commit()
            print("\n✅ Test data seeded successfully!")
            
            # Show summary
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"\nTotal users in database: {user_count}")
            
            result = await session.execute(text("SELECT COUNT(*) FROM agencies"))
            agency_count = result.scalar()
            print(f"Total agencies in database: {agency_count}")
            
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
            
            # Show test credentials
            print("\n" + "="*60)
            print("TEST CREDENTIALS - ALL PASSWORDS: admin123")
            print("="*60)
            
            print("\n🔵 SUPER ADMIN")
            print("  Email: admin@agency.com")
            print("  Purpose: Full platform control")
            
            print("\n🟢 AGENCY OWNERS")
            print("  Elite Models: owner@elitemodels.com")
            print("  Premium Talent: owner@premiumtalent.com")
            print("  Rising Stars: owner@risingstars.com")
            
            print("\n🟡 AGENCY ADMINS")
            print("  Elite Models: admin@elitemodels.com")
            
            print("\n🟣 MODELS")
            print("  Sarah (Elite): sarah@elitemodels.com")
            print("  Emma (Elite): emma@elitemodels.com")
            print("  Lisa (Elite): lisa@elitemodels.com")
            print("  Jessica (Premium): jessica@premiumtalent.com")
            print("  Ashley (Premium): ashley@premiumtalent.com")
            print("  Sophia (Rising): sophia@risingstars.com")
            
            print("\n🟠 CHATTERS")
            print("  John (Elite): john@elitemodels.com")
            print("  Mike (Elite): mike@elitemodels.com")
            print("  Alex (Premium): alex@premiumtalent.com")
            
            print("\n⚪ AGENCY MEMBERS")
            print("  Support (Elite): support@elitemodels.com")
            
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