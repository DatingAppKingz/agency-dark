#!/usr/bin/env python3
"""
Test the full migration sequence from scratch.

This script creates a test database, runs all migrations in sequence,
and verifies that the schema is correctly created.
"""
import os
import sys
import subprocess
import asyncio
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import config as alembic_config
from alembic import script as alembic_script
from alembic.runtime import migration

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings


class MigrationTester:
    """Test migration sequence and validate database schema."""
    
    def __init__(self):
        # Create test database URL
        self.test_db_name = "agencydark_test_migrations"
        # Get the base URL without database name
        if "/agencydark" in settings.DATABASE_URL:
            self.base_url = settings.DATABASE_URL.replace("/agencydark", "")
        else:
            # Split at the last slash to remove any database name
            parts = settings.DATABASE_URL.rsplit('/', 1)
            self.base_url = parts[0]
        
        self.test_url = f"{self.base_url}/{self.test_db_name}"
        self.test_url_sync = self.test_url.replace("postgresql+asyncpg://", "postgresql://")
        
    async def setup_test_database(self):
        """Create a fresh test database."""
        print("Creating test database...")
        
        # Connect to postgres database to create test database
        engine = create_engine(self.base_url.replace("postgresql+asyncpg://", "postgresql://") + "/postgres")
        
        with engine.connect() as conn:
            # Terminate existing connections
            conn.execute(text("COMMIT"))
            conn.execute(text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{self.test_db_name}' AND pid <> pg_backend_pid()"
            ))
            
            # Drop if exists and create new
            conn.execute(text("COMMIT"))
            conn.execute(text(f"DROP DATABASE IF EXISTS {self.test_db_name}"))
            conn.execute(text("COMMIT"))
            conn.execute(text(f"CREATE DATABASE {self.test_db_name}"))
            
        print(f"Test database '{self.test_db_name}' created successfully")
    
    def run_migrations(self):
        """Run all migrations using Alembic."""
        print("\nRunning migrations...")
        
        # Set test database URL in environment
        os.environ["DATABASE_URL"] = self.test_url
        
        # Change to backend directory
        backend_dir = Path(__file__).parent.parent
        os.chdir(backend_dir)
        
        # Run alembic upgrade
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Migration failed:\n{result.stderr}")
            return False
        
        print("All migrations completed successfully")
        return True
    
    def verify_schema(self):
        """Verify that all expected tables exist."""
        print("\nVerifying database schema...")
        
        engine = create_engine(self.test_url_sync)
        inspector = inspect(engine)
        
        # Get all tables
        tables = inspector.get_table_names()
        
        # Expected tables (from migrations)
        expected_tables = [
            # Core tables
            'users',
            'agencies',
            'models',
            'fans',
            'subscriptions',
            'content',
            
            # Chat tables
            'chat_conversations',
            'chat_messages',
            'chat_participants',
            'chat_templates',
            
            # Financial tables
            'financial_transactions',
            'billing_cycles',
            'payouts',
            'invoices',
            'commission_rules',
            'earnings',
            'payment_methods',
            
            # API/Integration tables
            'api_keys',
            'api_key_usage',
            'sync_tasks',
            'sync_logs',
            'webhook_logs',
            'webhook_endpoints',
            
            # Analytics tables
            'analytics_revenue',
            'analytics_subscribers',
            'analytics_engagement',
            'model_performance_stats',
            
            # Other tables
            'notifications',
            'notification_preferences',
            'custom_fields',
            'custom_field_values',
            'features',
            'bulk_operations',
            'audit_logs',
            'user_sessions',
            'translations',
            'media_files',
            'fan_profiles',
            
            # Alembic
            'alembic_version'
        ]
        
        print(f"\nFound {len(tables)} tables in database")
        
        # Check for missing tables
        missing_tables = set(expected_tables) - set(tables)
        if missing_tables:
            print(f"\n⚠️  Missing tables: {', '.join(sorted(missing_tables))}")
        
        # Check for unexpected tables
        extra_tables = set(tables) - set(expected_tables)
        if extra_tables:
            print(f"\n📋 Additional tables found: {', '.join(sorted(extra_tables))}")
        
        # Verify indexes
        print("\nVerifying indexes...")
        index_count = 0
        for table in tables:
            indexes = inspector.get_indexes(table)
            index_count += len(indexes)
        
        print(f"Total indexes: {index_count}")
        
        # Verify foreign keys
        print("\nVerifying foreign key constraints...")
        fk_count = 0
        for table in tables:
            foreign_keys = inspector.get_foreign_keys(table)
            fk_count += len(foreign_keys)
        
        print(f"Total foreign key constraints: {fk_count}")
        
        return len(missing_tables) == 0
    
    def test_rollback(self):
        """Test migration rollback functionality."""
        print("\n\nTesting migration rollback...")
        
        # Get current revision
        cfg = alembic_config.Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", self.test_url_sync)
        
        engine = create_engine(self.test_url_sync)
        with engine.connect() as connection:
            context = migration.MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            print(f"Current revision: {current_rev}")
        
        # Downgrade by one revision
        print("Testing downgrade to previous revision...")
        result = subprocess.run(
            ["alembic", "downgrade", "-1"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Rollback failed:\n{result.stderr}")
            return False
        
        # Check new revision
        with engine.connect() as connection:
            context = migration.MigrationContext.configure(connection)
            new_rev = context.get_current_revision()
            print(f"After rollback revision: {new_rev}")
        
        # Upgrade back to head
        print("Testing upgrade back to head...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Re-upgrade failed:\n{result.stderr}")
            return False
        
        print("Rollback test completed successfully")
        return True
    
    def cleanup(self):
        """Drop the test database."""
        print("\nCleaning up test database...")
        
        engine = create_engine(self.base_url.replace("postgresql+asyncpg://", "postgresql://") + "/postgres")
        
        with engine.connect() as conn:
            # Terminate connections
            conn.execute(text("COMMIT"))
            conn.execute(text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{self.test_db_name}' AND pid <> pg_backend_pid()"
            ))
            
            # Drop database
            conn.execute(text("COMMIT"))
            conn.execute(text(f"DROP DATABASE IF EXISTS {self.test_db_name}"))
            
        print("Test database dropped")
    
    async def run_tests(self):
        """Run all migration tests."""
        try:
            # 1. Setup test database
            await self.setup_test_database()
            
            # 2. Run migrations
            if not self.run_migrations():
                print("\n❌ Migration test failed")
                return False
            
            # 3. Verify schema
            if not self.verify_schema():
                print("\n❌ Schema verification failed")
                return False
            
            # 4. Test rollback
            if not self.test_rollback():
                print("\n❌ Rollback test failed")
                return False
            
            print("\n✅ All migration tests passed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            return False
        
        finally:
            # Always cleanup
            self.cleanup()


async def main():
    """Run migration tests."""
    tester = MigrationTester()
    success = await tester.run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())