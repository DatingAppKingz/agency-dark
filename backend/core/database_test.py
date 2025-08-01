"""
Test database configuration to avoid model conflicts
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

# Create separate base for tests
TestBase = declarative_base()

# Copy model definitions for testing
def create_test_models():
    """Create test-specific models that don't conflict."""
    from models.base import BaseModel
    
    # Create test base model
    class TestBaseModel(TestBase):
        __abstract__ = True
        __table_args__ = {"extend_existing": True}
        
        # Copy columns from BaseModel
        id = BaseModel.id.property.columns[0].copy()
        created_at = BaseModel.created_at.property.columns[0].copy()
        updated_at = BaseModel.updated_at.property.columns[0].copy()
    
    return TestBaseModel

# Test engine factory
def create_test_engine(database_url: str):
    """Create test engine with proper configuration."""
    return create_async_engine(
        database_url,
        echo=False,
        poolclass=NullPool,  # Disable pooling for tests
        connect_args={
            "server_settings": {"jit": "off"},
            "command_timeout": 60,
        }
    )
