#!/usr/bin/env python3
"""
Fix SQLAlchemy model conflicts by adding extend_existing=True to all models
"""
import os
import re
from pathlib import Path

def fix_model_file(file_path):
    """Add __table_args__ to a model file if needed."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already has __table_args__
    if '__table_args__' in content:
        print(f"✓ {file_path.name} already has __table_args__")
        return False
    
    # Find class definitions that inherit from BaseModel
    pattern = r'(class\s+\w+\(BaseModel\):\s*\n(?:\s*""".*?"""\s*\n)?)'
    
    def add_table_args(match):
        class_def = match.group(1)
        # Add __table_args__ after docstring
        return class_def + '    __table_args__ = {"extend_existing": True}\n\n'
    
    new_content = re.sub(pattern, add_table_args, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print(f"✅ Fixed {file_path.name}")
        return True
    
    return False

def main():
    """Fix all model files."""
    backend_dir = Path(__file__).parent.parent
    models_dir = backend_dir / "models"
    
    print("Fixing SQLAlchemy model conflicts...")
    print("="*50)
    
    fixed_count = 0
    
    # Fix all Python files in models directory
    for file_path in models_dir.glob("*.py"):
        if file_path.name == "__init__.py" or file_path.name == "base.py":
            continue
        
        if fix_model_file(file_path):
            fixed_count += 1
    
    print("="*50)
    print(f"Fixed {fixed_count} model files")
    
    # Also create a better base configuration
    base_config_path = backend_dir / "core" / "database_test.py"
    base_config_content = '''"""
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
'''
    
    with open(base_config_path, 'w') as f:
        f.write(base_config_content)
    
    print(f"\n✅ Created {base_config_path.name} for test isolation")

if __name__ == "__main__":
    main()