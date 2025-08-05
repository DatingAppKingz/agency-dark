"""Seed model assignments for testing."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)

async def seed_assignments():
    async with engine.begin() as conn:
        # Get agency admin to be the assigner
        result = await conn.execute(text("""
            SELECT id FROM users WHERE email = 'admin@elitemodels.com'
        """))
        admin_id = result.scalar()
        
        if not admin_id:
            print("❌ Agency admin not found")
            return
            
        # Create assignments for Elite Models Agency
        assignments = [
            # John (chatter) -> Sarah, Emma
            {
                "chatter_email": "john@elitemodels.com",
                "model_emails": ["sarah@elitemodels.com", "emma@elitemodels.com"]
            },
            # Mike (chatter) -> Lisa
            {
                "chatter_email": "mike@elitemodels.com", 
                "model_emails": ["lisa@elitemodels.com"]
            },
            # Alex (chatter) -> Jessica, Ashley
            {
                "chatter_email": "alex@premiumtalent.com",
                "model_emails": ["jessica@premiumtalent.com", "ashley@premiumtalent.com"]
            }
        ]
        
        for assignment in assignments:
            # Get chatter ID
            result = await conn.execute(text("""
                SELECT id, agency_id FROM users WHERE email = :email AND role = 'CHATTER'
            """), {"email": assignment["chatter_email"]})
            chatter = result.fetchone()
            
            if not chatter:
                print(f"❌ Chatter {assignment['chatter_email']} not found")
                continue
                
            chatter_id, agency_id = chatter
            
            # Assign to each model
            for model_email in assignment["model_emails"]:
                # Get model ID
                result = await conn.execute(text("""
                    SELECT id FROM users WHERE email = :email AND role = 'MODEL'
                """), {"email": model_email})
                model_id = result.scalar()
                
                if not model_id:
                    print(f"❌ Model {model_email} not found")
                    continue
                
                # Check if assignment already exists
                result = await conn.execute(text("""
                    SELECT id FROM model_assignments 
                    WHERE chatter_id = :chatter_id AND model_id = :model_id
                """), {"chatter_id": chatter_id, "model_id": model_id})
                
                if result.scalar():
                    print(f"⚠️  Assignment already exists: {assignment['chatter_email']} -> {model_email}")
                    continue
                
                # Create assignment
                await conn.execute(text("""
                    INSERT INTO model_assignments 
                    (chatter_id, model_id, agency_id, assigned_by, notes)
                    VALUES 
                    (:chatter_id, :model_id, :agency_id, :assigned_by, :notes)
                """), {
                    "chatter_id": chatter_id,
                    "model_id": model_id,
                    "agency_id": agency_id,
                    "assigned_by": admin_id,
                    "notes": "Initial assignment for testing"
                })
                
                print(f"✅ Assigned {assignment['chatter_email']} -> {model_email}")
        
        print("\n✅ Model assignments seeded successfully!")

async def main():
    await seed_assignments()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())