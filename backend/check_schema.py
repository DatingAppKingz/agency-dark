"""Check database schema."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mariuszbudzisz@localhost/agencydark_dev")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def check_schema():
    """Check database schema."""
    async with AsyncSessionLocal() as session:
        try:
            # Check agencies table
            print("AGENCIES TABLE COLUMNS:")
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'agencies'
                ORDER BY ordinal_position
            """))
            for row in result:
                print(f"  {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")
            
            print("\nUSERS TABLE COLUMNS:")
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'users'
                ORDER BY ordinal_position
            """))
            for row in result:
                print(f"  {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            await session.close()

async def main():
    """Main function."""
    await check_schema()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())