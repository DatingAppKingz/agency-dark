#!/usr/bin/env python3
"""
Simple migration rollback test - just test migration 037.
"""
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
from pathlib import Path

def test_migration_037_rollback():
    """Test that migration 037 can be rolled back properly."""
    
    test_db_name = "agencydark_test_037"
    db_params = {
        'host': 'localhost',
        'port': 5432,
        'user': 'mariuszbudzisz'
    }
    
    print("Creating test database...")
    
    # Connect to postgres database to create our test database
    conn = psycopg2.connect(database='postgres', **db_params)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Drop if exists and create new
    cur.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
    cur.execute(f"CREATE DATABASE {test_db_name}")
    
    cur.close()
    conn.close()
    
    print(f"Test database '{test_db_name}' created")
    
    # Create UUID extension
    conn = psycopg2.connect(database=test_db_name, **db_params)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    cur.close()
    conn.close()
    
    backend_dir = Path(__file__).parent.parent
    env = {
        'DATABASE_URL': f"postgresql+asyncpg://mariuszbudzisz@localhost:5432/{test_db_name}",
        'DATABASE_SYNC_URL': f"postgresql://mariuszbudzisz@localhost:5432/{test_db_name}",
        'PYTHONPATH': str(backend_dir)
    }
    
    try:
        # Run migrations up to 036
        print("\nMigrating to revision 036...")
        result = subprocess.run(
            ['alembic', 'upgrade', '036'],
            cwd=backend_dir,
            env={**subprocess.os.environ, **env},
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("❌ Failed to migrate to 036")
            print(result.stderr)
            return False
            
        print("✅ Migrated to 036")
        
        # Migrate to 037
        print("\nMigrating to revision 037...")
        result = subprocess.run(
            ['alembic', 'upgrade', '037'],
            cwd=backend_dir,
            env={**subprocess.os.environ, **env},
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("❌ Failed to migrate to 037")
            print(result.stderr)
            return False
            
        print("✅ Migrated to 037")
        
        # Check tables
        conn = psycopg2.connect(database=test_db_name, **db_params)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'notification%'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        print(f"\nNotification tables after migration 037: {tables}")
        
        cur.close()
        conn.close()
        
        # Rollback to 036
        print("\nRolling back to revision 036...")
        result = subprocess.run(
            ['alembic', 'downgrade', '036'],
            cwd=backend_dir,
            env={**subprocess.os.environ, **env},
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("❌ Failed to rollback to 036")
            print(result.stderr)
            return False
            
        print("✅ Rolled back to 036")
        
        # Check if notifications table still exists (it should, from migration 001)
        conn = psycopg2.connect(database=test_db_name, **db_params)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'notifications'
            ORDER BY column_name
        """)
        
        if cur.rowcount > 0:
            columns = [row[0] for row in cur.fetchall()]
            print(f"\nNotifications table columns after rollback: {columns}")
        else:
            print("\nNotifications table does not exist after rollback")
        
        cur.close()
        conn.close()
        
        print("\n✅ Migration 037 rollback test passed!")
        return True
        
    finally:
        # Cleanup
        print("\nCleaning up...")
        conn = psycopg2.connect(database='postgres', **db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{test_db_name}'
            AND pid <> pg_backend_pid()
        """)
        
        cur.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
        cur.close()
        conn.close()
        
        print("Test database dropped")


if __name__ == '__main__':
    test_migration_037_rollback()