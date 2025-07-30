"""Create database tables from models."""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from sqlalchemy.ext.asyncio import create_async_engine
from models.base import Base
from models import *  # Import all models to register them
import os

# Override DATABASE_URL to use the external port
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/agencydark"
)

async def create_tables():
    """Create all tables in the database."""
    print(f"Connecting to database: {DATABASE_URL}")
    
    # Create engine without the problematic pool configuration
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,  # Print SQL statements
    )
    
    async with engine.begin() as conn:
        # Drop all tables first (for clean slate)
        print("Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        
    await engine.dispose()
    print("All tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())