"""Create model_assignments table manually."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=True)

async def create_table():
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'model_assignments'
            )
        """))
        exists = result.scalar()
        
        if exists:
            print("Table model_assignments already exists")
            return
            
        # Create the table
        await conn.execute(text("""
            CREATE TABLE model_assignments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chatter_id UUID NOT NULL REFERENCES users(id),
                model_id UUID NOT NULL REFERENCES users(id),
                agency_id UUID NOT NULL REFERENCES agencies(id),
                is_active BOOLEAN NOT NULL DEFAULT true,
                assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
                assigned_by UUID NOT NULL REFERENCES users(id),
                notes TEXT,
                priority VARCHAR(50) DEFAULT 'normal',
                CONSTRAINT unique_chatter_model_assignment UNIQUE (chatter_id, model_id)
            )
        """))
        
        # Create indexes
        await conn.execute(text("CREATE INDEX idx_model_assignments_chatter ON model_assignments(chatter_id)"))
        await conn.execute(text("CREATE INDEX idx_model_assignments_model ON model_assignments(model_id)"))
        await conn.execute(text("CREATE INDEX idx_model_assignments_agency ON model_assignments(agency_id)"))
        await conn.execute(text("CREATE INDEX idx_model_assignments_active ON model_assignments(is_active)"))
        
        print("✅ Created model_assignments table with indexes")

async def main():
    await create_table()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())