"""Clear all data from database while preserving structure."""
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
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def clear_all_data():
    """Clear all data from all tables."""
    async with AsyncSessionLocal() as session:
        try:
            # Get all table names
            result = await session.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename NOT IN ('alembic_version')
                ORDER BY tablename
            """))
            tables = [row[0] for row in result]
            
            print(f"Found {len(tables)} tables to clear")
            
            # Disable foreign key checks temporarily
            await session.execute(text("SET session_replication_role = 'replica';"))
            
            # Clear each table
            for table in tables:
                try:
                    await session.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                    print(f"✓ Cleared table: {table}")
                except Exception as e:
                    print(f"✗ Error clearing {table}: {e}")
            
            # Re-enable foreign key checks
            await session.execute(text("SET session_replication_role = 'origin';"))
            
            # Commit changes
            await session.commit()
            print("\n✅ All data cleared successfully!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await session.rollback()
        finally:
            await session.close()

async def main():
    """Main function."""
    print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
    print(f"Database: {DATABASE_URL}")
    
    confirm = input("\nType 'DELETE ALL DATA' to confirm: ")
    if confirm == "DELETE ALL DATA":
        await clear_all_data()
    else:
        print("❌ Operation cancelled")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())