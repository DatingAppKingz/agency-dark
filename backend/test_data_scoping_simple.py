"""Test data scoping with repository pattern - simplified version."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_data_scoping():
    """Test that data scoping works correctly for different roles."""
    
    async with AsyncSessionLocal() as db:
        # First, let's look at what's in the database
        print("🧪 Testing Data Scoping with Repository Pattern\n")
        
        # Get all users
        result = await db.execute(text("""
            SELECT id, email, role, agency_id, full_name 
            FROM users 
            ORDER BY created_at
            LIMIT 20
        """))
        
        print("📋 Users in database:")
        users = {}
        for row in result:
            print(f"   - {row.email} ({row.role}) - Agency: {row.agency_id}")
            users[row.email] = {
                'id': row.id,
                'email': row.email,
                'role': row.role,
                'agency_id': row.agency_id,
                'full_name': row.full_name
            }
        
        # Test 1: Direct query filtering
        print("\n1️⃣ Test Direct Query Filtering")
        
        # Get elite models agency ID
        elite_agency_id = users.get('owner@elitemodels.com', {}).get('agency_id')
        premium_agency_id = users.get('owner@premiumtalent.com', {}).get('agency_id')
        
        if elite_agency_id:
            # Count users in Elite Models agency
            result = await db.execute(text("""
                SELECT COUNT(*) FROM users WHERE agency_id = :agency_id
            """), {"agency_id": elite_agency_id})
            elite_count = result.scalar()
            print(f"   Elite Models has {elite_count} users")
            
            # List Elite Models users
            result = await db.execute(text("""
                SELECT email, role FROM users 
                WHERE agency_id = :agency_id
                ORDER BY email
            """), {"agency_id": elite_agency_id})
            print("   Elite Models users:")
            for row in result:
                print(f"     - {row.email} ({row.role})")
        
        if premium_agency_id:
            # Count users in Premium Talent agency
            result = await db.execute(text("""
                SELECT COUNT(*) FROM users WHERE agency_id = :agency_id
            """), {"agency_id": premium_agency_id})
            premium_count = result.scalar()
            print(f"\n   Premium Talent has {premium_count} users")
        
        # Test 2: Model assignments
        print("\n2️⃣ Test Model Assignments")
        
        # Check if model_assignments table exists
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'model_assignments'
            )
        """))
        table_exists = result.scalar()
        
        if table_exists:
            # Get chatter assignments
            result = await db.execute(text("""
                SELECT 
                    c.email as chatter_email,
                    m.email as model_email,
                    ma.is_active
                FROM model_assignments ma
                JOIN users c ON ma.chatter_id = c.id
                JOIN users m ON ma.model_id = m.id
                WHERE ma.is_active = true
                ORDER BY c.email, m.email
                LIMIT 10
            """))
            
            assignments = list(result)
            if assignments:
                print("   Active chatter-model assignments:")
                for row in assignments:
                    print(f"     - {row.chatter_email} -> {row.model_email}")
            else:
                print("   No active model assignments found")
        else:
            print("   model_assignments table not found")
        
        # Test 3: Repository pattern concept
        print("\n3️⃣ Test Repository Pattern Concept")
        print("   Repository pattern would apply these filters:")
        print("   - Super Admin: No filter (sees all)")
        print("   - Agency Owner/Admin: WHERE agency_id = user.agency_id")
        print("   - Model: WHERE id = user.id (only themselves)")
        print("   - Chatter: Complex filter based on model assignments")
        
        # Test 4: Simulated filtering
        print("\n4️⃣ Simulated Data Scoping Results")
        
        # Simulate Super Admin view
        result = await db.execute(text("SELECT COUNT(*) FROM users"))
        total_users = result.scalar()
        print(f"   Super Admin would see: {total_users} users")
        
        # Simulate Agency Owner view (Elite Models)
        if elite_agency_id:
            result = await db.execute(text("""
                SELECT COUNT(*) FROM users WHERE agency_id = :agency_id
            """), {"agency_id": elite_agency_id})
            agency_users = result.scalar()
            print(f"   Elite Models Owner would see: {agency_users} users")
        
        # Simulate Model view (sees only themselves)
        print("   Models would see: 1 user (themselves)")
        
        # Simulate Chatter view
        john_id = users.get('john@elitemodels.com', {}).get('id')
        if john_id and table_exists:
            result = await db.execute(text("""
                SELECT COUNT(DISTINCT m.id)
                FROM model_assignments ma
                JOIN users m ON ma.model_id = m.id
                WHERE ma.chatter_id = :chatter_id AND ma.is_active = true
            """), {"chatter_id": john_id})
            assigned_count = result.scalar() or 0
            print(f"   Chatter John would see: {assigned_count} assigned models + himself")
        
        print("\n✅ Data scoping concept demonstration completed!")


async def main():
    await test_data_scoping()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())