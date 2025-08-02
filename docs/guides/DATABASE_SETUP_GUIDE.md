# Database Setup Guide

## Prerequisites
- PostgreSQL 16 running on port 5433 (via Docker)
- Python environment with SQLAlchemy and Alembic

## Step 1: Connect to PostgreSQL

### Using Docker
```bash
# Connect to PostgreSQL container
docker-compose exec postgres psql -U postgres

# Or from host machine
psql -h localhost -p 5433 -U postgres
```

## Step 2: Create Database and User

```sql
-- Create database
CREATE DATABASE agencydark;

-- Create user with password
CREATE USER agencydark_user WITH PASSWORD 'agencydark_pass';

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE agencydark TO agencydark_user;

-- Additional permissions for schema creation
GRANT CREATE ON DATABASE agencydark TO agencydark_user;

-- Connect to the new database
\c agencydark

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO agencydark_user;
```

## Step 3: Update Database Configuration

### Update .env file
```env
# Database
DATABASE_URL=postgresql+asyncpg://agencydark_user:agencydark_pass@localhost:5433/agencydark
DATABASE_SYNC_URL=postgresql://agencydark_user:agencydark_pass@localhost:5433/agencydark

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Secret (generate a secure key)
JWT_SECRET_KEY=your-super-secret-jwt-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Update backend/core/config.py
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DATABASE_SYNC_URL: Optional[str] = None
    
    # Redis
    REDIS_URL: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # App
    APP_NAME: str = "AgencyDark"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

## Step 4: Create Database Models

### Create backend/models/base.py
```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, Integer
from datetime import datetime

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

### Core Models Structure
```
backend/models/
├── __init__.py
├── base.py
├── user.py
├── agency.py
├── model.py
├── chat.py
├── financial.py
└── analytics.py
```

## Step 5: Initialize Alembic

```bash
cd backend

# Initialize Alembic
alembic init alembic

# Update alembic.ini
# Set sqlalchemy.url = postgresql://agencydark_user:agencydark_pass@localhost:5433/agencydark
```

### Update alembic/env.py
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Import your models
from models.base import Base
from models import user, agency, model, chat, financial, analytics

# this is the Alembic Config object
config = context.config

# Set the SQLAlchemy URL from environment
from core.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_SYNC_URL)

target_metadata = Base.metadata
```

## Step 6: Create Initial Migration

```bash
# Create first migration
alembic revision --autogenerate -m "Initial schema with users and agencies"

# Review the generated migration file
# Apply migration
alembic upgrade head
```

## Step 7: Verify Database

```bash
# Connect to database
psql -h localhost -p 5433 -U agencydark_user -d agencydark

# List tables
\dt

# Describe a table
\d users
```

## Step 8: Create Seed Data Script

### Create backend/scripts/seed_data.py
```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.user import User
from models.agency import Agency
from core.security import get_password_hash

async def seed_data():
    async with get_db() as db:
        # Create test agency
        agency = Agency(
            name="Test Agency",
            domain="test.localhost",
            settings={}
        )
        db.add(agency)
        await db.commit()
        
        # Create test users
        users = [
            User(
                email="admin@test.com",
                username="admin",
                password_hash=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True,
                agency_id=agency.id
            ),
            User(
                email="user@test.com",
                username="user",
                password_hash=get_password_hash("user123"),
                is_active=True,
                agency_id=agency.id
            )
        ]
        
        db.add_all(users)
        await db.commit()
        
        print("Seed data created successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
```

## Troubleshooting

### Connection Issues
- Ensure PostgreSQL is running: `docker-compose ps`
- Check port 5433 is not in use: `lsof -i :5433`
- Verify credentials in .env file

### Migration Issues
- Drop and recreate database if needed
- Check model imports in alembic/env.py
- Ensure all models inherit from Base

### Permission Issues
```sql
-- If you get permission denied errors
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO agencydark_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO agencydark_user;
```

## Next Steps
1. Create all database models
2. Generate and run migrations
3. Seed initial data
4. Update API to use database models
5. Test with frontend application