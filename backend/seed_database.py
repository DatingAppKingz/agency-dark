"""Seed database with test data."""
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

async def seed_database():
    """Seed database with test data."""
    async with AsyncSessionLocal() as session:
        try:
            # Read SQL file
            with open('../manuals/seed_test_data.sql', 'r') as f:
                sql_content = f.read()
            
            # Remove comments and split by semicolons
            statements = []
            for line in sql_content.split('\n'):
                if not line.strip().startswith('--'):
                    statements.append(line)
            
            full_sql = '\n'.join(statements)
            
            # Execute statements one by one
            for statement in full_sql.split(';'):
                statement = statement.strip()
                if statement and statement.upper() not in ['BEGIN', 'COMMIT', '']:
                    try:
                        await session.execute(text(statement))
                    except Exception as e:
                        if 'Test data loaded successfully!' not in str(e):
                            print(f"Warning: {e}")
            
            await session.commit()
            print("\n✅ Test data seeded successfully!")
            
            # Show summary
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"Total users: {user_count}")
            
            result = await session.execute(text("SELECT COUNT(*) FROM agencies"))
            agency_count = result.scalar()
            print(f"Total agencies: {agency_count}")
            
            result = await session.execute(text("SELECT COUNT(*) FROM model_profiles"))
            model_count = result.scalar()
            print(f"Total models: {model_count}")
            
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