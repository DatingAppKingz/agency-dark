#!/usr/bin/env python3
"""
Test migrations directly by importing them.
"""
import os
import sys
import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_migration(filepath):
    """Load a migration module directly."""
    spec = importlib.util.spec_from_file_location("migration", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_direct_migrations():
    """Test migrations by loading them directly."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Create test database
    test_db = "test_direct_migrations"
    engine = create_engine("postgresql://postgres:postgres@localhost/postgres")
    
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db}"))
        conn.execute(text("COMMIT"))
        conn.execute(text(f"CREATE DATABASE {test_db}"))
    
    print(f"Created test database: {test_db}")
    
    # Connect to test database
    test_engine = create_engine(f"postgresql://postgres:postgres@localhost/{test_db}")
    
    # Get first few migrations
    migrations = sorted([
        f for f in versions_dir.glob('*.py')
        if f.name.startswith('00')
    ])[:5]  # Test first 5 migrations
    
    print(f"\nTesting {len(migrations)} migrations:")
    
    for migration_file in migrations:
        print(f"\nLoading {migration_file.name}...")
        try:
            module = load_migration(migration_file)
            print(f"  Revision: {module.revision}")
            print(f"  Down revision: {module.down_revision}")
            
            # Check if the migration functions exist
            if hasattr(module, 'upgrade'):
                print("  ✓ upgrade() function exists")
            if hasattr(module, 'downgrade'):
                print("  ✓ downgrade() function exists")
                
        except Exception as e:
            print(f"  ✗ Error loading migration: {e}")
    
    # Cleanup
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db}"))
    
    print("\nTest completed!")

if __name__ == '__main__':
    test_direct_migrations()