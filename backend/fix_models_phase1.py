#!/usr/bin/env python3
"""
Phase 1: Fix model Base imports and consolidate to core.database
"""
import os
import re
from pathlib import Path

# Define the models directory
MODELS_DIR = Path(__file__).parent / "models"

# Files that need Base import updates
files_to_update = [
    "agency.py", "analytics.py", "api_key.py", "audit.py", "chat.py",
    "content.py", "fan_claim.py", "financial.py", "model.py", "subscriber.py",
    "sync_log.py", "temp_file.py", "user.py", "webhook.py", "model_settings.py"
]

# Files that use core.database (leave as is)
files_using_core_database = [
    "api_key_audit.py", "external_api.py", "media.py", "mobile_device.py",
    "mobile_session.py", "notification.py", "saved_search.py", "scheduled_task.py",
    "sync_conflict_log.py", "sync_error_log.py", "task_result.py", "translation.py"
]


def update_base_imports(filepath):
    """Update Base imports in a model file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern 1: from models.base import Base, BaseModel
    pattern1 = r'from models\.base import Base, BaseModel'
    replacement1 = 'from core.database import Base
from models.base import BaseModel'
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: from models.base import BaseModel (only)
    pattern2 = r'from models\.base import BaseModel(?!\s*,\s*Base)'
    if 'from models.base import BaseModel' in content and 'Base' not in content:
        # This file only imports BaseModel, leave it as is
        pass
    
    # Pattern 3: Fix relative imports
    pattern3 = r'from \.base import Base, BaseModel'
    content = re.sub(pattern3, replacement1, content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


def update_models_init():
    """Update models/__init__.py to import from core.database"""
    init_file = MODELS_DIR / "__init__.py"
    with open(init_file, 'r') as f:
        content = f.read()
    
    # Update the Base import
    content = re.sub(
        r'from models\.base import Base, BaseModel',
        'from core.database import Base
from models.base import BaseModel',
        content
    )
    
    with open(init_file, 'w') as f:
        f.write(content)


def create_base_model_update():
    """Update base.py to use Base from core.database"""
    base_file = MODELS_DIR / "base.py"
    new_content = '''"""Base model class for common functionality."""
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func
from core.database import Base


class BaseModel(Base):
    """Base model class that includes common columns for all models."""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def dict(self):
        """Convert model to dictionary."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
'''
    
    with open(base_file, 'w') as f:
        f.write(new_content)


def main():
    print("Phase 1: Fixing Base imports in models...")
    
    # Step 1: Update base.py
    print("\n1. Updating models/base.py...")
    create_base_model_update()
    print("   ✅ Updated base.py to use Base from core.database")
    
    # Step 2: Update models that use models.base
    print("\n2. Updating model files...")
    updated_count = 0
    for filename in files_to_update:
        filepath = MODELS_DIR / filename
        if filepath.exists():
            if update_base_imports(filepath):
                print(f"   ✅ Updated {filename}")
                updated_count += 1
            else:
                print(f"   ℹ️  No changes needed for {filename}")
        else:
            print(f"   ⚠️  File not found: {filename}")
    
    # Step 3: Update models/__init__.py
    print("\n3. Updating models/__init__.py...")
    update_models_init()
    print("   ✅ Updated models/__init__.py")
    
    print(f"\n✅ Phase 1 Complete! Updated {updated_count + 2} files")
    print("\nFiles already using core.database (no changes needed):")
    for filename in files_using_core_database:
        print(f"   - {filename}")
    
    print("\n⚠️  Note: After running this script, you should:")
    print("1. Review the changes")
    print("2. Test that imports still work")
    print("3. Proceed to Phase 2 if successful")


if __name__ == "__main__":
    main()