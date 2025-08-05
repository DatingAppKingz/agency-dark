"""Test data scoping with repository pattern."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models.user_simple import User, UserRole
from core.repositories.user_repository import UserRepository

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_data_scoping():
    """Test that data scoping works correctly for different roles."""
    
    async with AsyncSessionLocal() as db:
        # Get test users
        result = await db.execute(text("""
            SELECT id, email, role, agency_id, full_name 
            FROM users 
            WHERE email IN (
                'admin@agency.com',
                'owner@elitemodels.com', 
                'sarah@elitemodels.com',
                'john@elitemodels.com',
                'owner@premiumtalent.com'
            )
        """))
        
        users = {}
        for row in result:
            users[row.email] = {
                'id': row.id,
                'email': row.email,
                'role': row.role,
                'agency_id': row.agency_id,
                'full_name': row.full_name
            }
        
        print("🧪 Testing Data Scoping with Repository Pattern\n")
        
        # Test 1: Super Admin sees all users
        print("1️⃣ Super Admin Test")
        super_admin = User(
            id=users['admin@agency.com']['id'],
            email='admin@agency.com',
            role=UserRole.SUPER_ADMIN.value,
            agency_id=None
        )
        
        repo = UserRepository(db, super_admin)
        all_users = await repo.get_all()
        print(f"   Super Admin sees {len(all_users)} users (should see all)")
        
        # Test 2: Agency Owner sees only agency users
        print("\n2️⃣ Agency Owner Test")
        agency_owner = User(
            id=users['owner@elitemodels.com']['id'],
            email='owner@elitemodels.com',
            role=UserRole.AGENCY_OWNER.value,
            agency_id=users['owner@elitemodels.com']['agency_id']
        )
        
        repo = UserRepository(db, agency_owner)
        agency_users = await repo.get_all()
        print(f"   Elite Models Owner sees {len(agency_users)} users")
        print(f"   Users: {[u.email for u in agency_users]}")
        
        # Verify they can't see users from other agencies
        other_owner = await repo.get_by_email('owner@premiumtalent.com')
        print(f"   Can see Premium Talent owner? {other_owner is not None} (should be False)")
        
        # Test 3: Model sees only themselves
        print("\n3️⃣ Model Test")
        model = User(
            id=users['sarah@elitemodels.com']['id'],
            email='sarah@elitemodels.com',
            role=UserRole.MODEL.value,
            agency_id=users['sarah@elitemodels.com']['agency_id']
        )
        
        repo = UserRepository(db, model)
        model_users = await repo.get_all()
        print(f"   Model Sarah sees {len(model_users)} users (should be 1)")
        if model_users:
            print(f"   Can see: {model_users[0].email}")
        
        # Test 4: Chatter with assignments
        print("\n4️⃣ Chatter Test")
        chatter = User(
            id=users['john@elitemodels.com']['id'],
            email='john@elitemodels.com',
            role=UserRole.CHATTER.value,
            agency_id=users['john@elitemodels.com']['agency_id']
        )
        
        repo = UserRepository(db, chatter)
        chatter_users = await repo.get_all()
        print(f"   Chatter John sees {len(chatter_users)} users")
        
        # Get assigned models
        assigned_models = await repo.get_models_for_chatter(str(chatter.id))
        print(f"   Assigned models: {[m.email for m in assigned_models]}")
        
        # Test 5: Cross-agency isolation
        print("\n5️⃣ Cross-Agency Isolation Test")
        # Try to get a user from another agency
        elite_owner_repo = UserRepository(db, agency_owner)
        premium_user = await elite_owner_repo.get_by_id(users['owner@premiumtalent.com']['id'])
        print(f"   Elite owner can access Premium owner? {premium_user is not None} (should be False)")
        
        print("\n✅ Data scoping tests completed!")


async def main():
    await test_data_scoping()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())