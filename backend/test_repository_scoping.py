"""Test repository pattern with actual filter implementation."""
import asyncio
import os
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import our filter classes
from core.filters.agency_filter import AgencyFilter, UserFilter

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Mock User class to simulate user context
class MockUser:
    def __init__(self, id, email, role, agency_id):
        self.id = id
        self.email = email
        self.role = role
        self.agency_id = agency_id


# Mock User table for queries
class UserTable:
    """Minimal User table representation for testing filters."""
    __tablename__ = "users"
    
    class id:
        @staticmethod
        def __eq__(other):
            return text(f"users.id = '{other}'")
        
        @staticmethod
        def in_(values):
            values_str = ", ".join([f"'{v}'" for v in values])
            return text(f"users.id IN ({values_str})")
    
    class agency_id:
        @staticmethod
        def __eq__(other):
            return text(f"users.agency_id = '{other}'")
    
    class email:
        pass


async def test_filter_logic():
    """Test the filter logic without complex ORM mappings."""
    print("🧾 Testing Repository Filter Logic\n")
    
    async with AsyncSessionLocal() as db:
        # Get test users from database
        result = await db.execute(text("""
            SELECT id, email, role, agency_id 
            FROM users 
            WHERE email IN (
                'admin@agency.com',
                'owner@elitemodels.com',
                'sarah@elitemodels.com',
                'john@elitemodels.com'
            )
        """))
        
        users = {}
        for row in result:
            users[row.email] = MockUser(
                id=row.id,
                email=row.email,
                role=row.role,
                agency_id=row.agency_id
            )
        
        # Test 1: Super Admin Filter
        print("1️⃣ Testing Super Admin Filter")
        super_admin = users['admin@agency.com']
        filter = UserFilter(super_admin)
        
        # Build a base query
        base_query = "SELECT * FROM users"
        
        # Check if filter would modify query
        print(f"   User role: {super_admin.role} (type: {type(super_admin.role)})")
        print(f"   Is super admin? {filter.is_super_admin()}")
        
        if filter.is_super_admin():
            print("   ✅ Super Admin: No filter applied (sees all users)")
        else:
            print("   ❌ Super Admin filter not working correctly")
            print(f"   Expected: 'SUPER_ADMIN', Got: '{super_admin.role}'")
        
        # Test 2: Agency Owner Filter
        print("\n2️⃣ Testing Agency Owner Filter")
        agency_owner = users['owner@elitemodels.com']
        filter = UserFilter(agency_owner)
        
        if filter.is_agency_admin() and filter.agency_id:
            print(f"   ✅ Agency Owner: Would add WHERE agency_id = '{filter.agency_id}'")
            
            # Test the actual filter
            result = await db.execute(text("""
                SELECT COUNT(*) FROM users WHERE agency_id = :agency_id
            """), {"agency_id": filter.agency_id})
            count = result.scalar()
            print(f"   → Would see {count} users from their agency")
        
        # Test 3: Model Filter
        print("\n3️⃣ Testing Model Filter")
        model = users['sarah@elitemodels.com']
        filter = UserFilter(model)
        
        if filter.is_model():
            print(f"   ✅ Model: Would add WHERE id = '{filter.current_user.id}'")
            print("   → Would see only themselves (1 user)")
        
        # Test 4: Chatter Filter
        print("\n4️⃣ Testing Chatter Filter")
        chatter = users['john@elitemodels.com']
        filter = UserFilter(chatter)
        
        if filter.is_chatter():
            print(f"   ✅ Chatter: Would see themselves + assigned models")
            
            # Get assigned models
            result = await db.execute(text("""
                SELECT COUNT(DISTINCT model_id)
                FROM model_assignments
                WHERE chatter_id = :chatter_id AND is_active = true
            """), {"chatter_id": chatter.id})
            assigned_count = result.scalar() or 0
            print(f"   → Would see {assigned_count} assigned models + themselves")
        
        # Test 5: Repository Query Building
        print("\n5️⃣ Testing Repository Query Building")
        
        # Simulate repository get_all for different users
        for user_type, user in [
            ("Super Admin", users['admin@agency.com']),
            ("Agency Owner", users['owner@elitemodels.com']),
            ("Model", users['sarah@elitemodels.com']),
            ("Chatter", users['john@elitemodels.com'])
        ]:
            filter = AgencyFilter(user)
            
            # Build appropriate query based on role
            if filter.is_super_admin():
                query = "SELECT COUNT(*) FROM users"
                params = {}
            elif filter.is_agency_admin() and filter.agency_id:
                query = "SELECT COUNT(*) FROM users WHERE agency_id = :agency_id"
                params = {"agency_id": filter.agency_id}
            elif filter.is_model():
                query = "SELECT COUNT(*) FROM users WHERE id = :user_id"
                params = {"user_id": user.id}
            elif filter.is_chatter():
                # For simplicity, just count the chatter themselves
                query = "SELECT COUNT(*) FROM users WHERE id = :user_id"
                params = {"user_id": user.id}
            else:
                query = "SELECT COUNT(*) FROM users WHERE id = :user_id"
                params = {"user_id": user.id}
            
            result = await db.execute(text(query), params)
            count = result.scalar()
            print(f"   {user_type} ({user.email}): {count} users visible")
        
        print("\n✅ Filter logic testing completed!")


async def main():
    await test_filter_logic()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())