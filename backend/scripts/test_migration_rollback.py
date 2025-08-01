#!/usr/bin/env python3
"""
Test migration rollback functionality.
This script tests that migrations can be rolled back properly.
"""
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
from pathlib import Path

class MigrationRollbackTester:
    def __init__(self):
        self.test_db_name = "agencydark_test_rollback"
        self.db_params = {
            'host': 'localhost',
            'port': 5432,
            'user': 'mariuszbudzisz'
        }
        
    def setup_test_database(self):
        """Create a fresh test database."""
        print(f"Creating test database...")
        
        # Connect to postgres database to create our test database
        conn = psycopg2.connect(database='postgres', **self.db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Drop if exists and create new
        cur.execute(f"DROP DATABASE IF EXISTS {self.test_db_name}")
        cur.execute(f"CREATE DATABASE {self.test_db_name}")
        
        cur.close()
        conn.close()
        
        print(f"Test database '{self.test_db_name}' created successfully")
        
        # Create UUID extension in the test database
        conn = psycopg2.connect(database=self.test_db_name, **self.db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
        cur.close()
        conn.close()
        
    def run_migration_to(self, revision):
        """Run migrations up to a specific revision."""
        print(f"\nMigrating to revision: {revision}")
        
        # Change to backend directory
        backend_dir = Path(__file__).parent.parent
        
        # Set up environment for alembic
        env = {
            'DATABASE_URL': f"postgresql+asyncpg://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'DATABASE_SYNC_URL': f"postgresql://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'PYTHONPATH': str(backend_dir)
        }
        
        try:
            # Run alembic upgrade to specific revision
            result = subprocess.run(
                ['alembic', 'upgrade', revision],
                cwd=backend_dir,
                env={**subprocess.os.environ, **env},
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Migration to {revision} failed:")
                print(result.stderr)
                return False
                
            print(f"✅ Successfully migrated to {revision}")
            return True
            
        except Exception as e:
            print(f"❌ Error running migration: {str(e)}")
            return False
            
    def downgrade_to(self, revision):
        """Downgrade to a specific revision."""
        print(f"\nDowngrading to revision: {revision}")
        
        # Change to backend directory
        backend_dir = Path(__file__).parent.parent
        
        # Set up environment for alembic
        env = {
            'DATABASE_URL': f"postgresql+asyncpg://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'DATABASE_SYNC_URL': f"postgresql://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'PYTHONPATH': str(backend_dir)
        }
        
        try:
            # Run alembic downgrade
            result = subprocess.run(
                ['alembic', 'downgrade', revision],
                cwd=backend_dir,
                env={**subprocess.os.environ, **env},
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Downgrade to {revision} failed:")
                print(result.stderr)
                return False
                
            print(f"✅ Successfully downgraded to {revision}")
            return True
            
        except Exception as e:
            print(f"❌ Error running downgrade: {str(e)}")
            return False
            
    def get_table_count(self):
        """Get the number of tables in the database."""
        conn = psycopg2.connect(database=self.test_db_name, **self.db_params)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            AND table_name != 'alembic_version'
        """)
        
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        return count
        
    def test_sequential_rollback(self):
        """Test rolling back migrations one by one."""
        print("\n" + "="*50)
        print("Testing sequential rollback")
        print("="*50)
        
        # List of revisions to test (from newest to oldest)
        revisions = [
            ('037', 'Notifications'),
            ('036', 'Translation'),
            ('035', 'Chat System'),
            ('034', 'Delta Sync'),
            ('033', 'ML Models V2'),
            ('032', 'API Key Audit'),
            ('031', 'Query Optimization'),
            ('030', 'Branding'),
            ('029', 'Webhooks'),
            ('028', 'API Keys'),
            ('027', 'Commissions'),
            ('026', 'Reports'),
            ('025', 'Fraud'),
            ('024', 'Alerts'),
            ('023', 'Models rename'),
            ('022', 'Query indexes'),
            ('021', 'Chat'),
            ('020', 'Theme'),
            ('019', 'Performance'),
            ('018', 'User sessions'),
            ('017', 'Tags'),
            ('016', 'Rate limiting'),
            ('015', 'AB Testing'),
            ('014', 'Advanced security'),
            ('013', 'Advanced query'),
            ('012', 'Dashboards'),
            ('011', 'Engagement'),
            ('010', 'Multi-model'),
            ('009', 'Tags update'),
            ('008', 'Fraud detection'),
            ('007', 'Fan management'),
            ('006', 'Referrals'),
            ('005', 'Proxy'),
            ('004', 'Analytics'),
            ('003', 'Email templates'),
            ('002', 'Fan profiles'),
            ('001', 'Initial')
        ]
        
        # First, run all migrations
        if not self.run_migration_to('head'):
            print("❌ Failed to run all migrations")
            return False
            
        initial_table_count = self.get_table_count()
        print(f"\nInitial table count: {initial_table_count}")
        
        # Test downgrading each migration
        for i, (rev, name) in enumerate(revisions):
            print(f"\n--- Testing rollback of {rev} ({name}) ---")
            
            # Downgrade to the previous revision
            if i < len(revisions) - 1:
                target_rev = revisions[i + 1][0]
            else:
                target_rev = 'base'
                
            if not self.downgrade_to(target_rev):
                print(f"❌ Failed to rollback {rev}")
                return False
                
            table_count = self.get_table_count()
            print(f"Table count after rollback: {table_count}")
            
            # Re-upgrade to test the migration works after rollback
            if not self.run_migration_to(rev):
                print(f"❌ Failed to re-apply migration {rev} after rollback")
                return False
                
        print("\n✅ All rollback tests passed!")
        return True
        
    def test_batch_rollback(self):
        """Test rolling back multiple migrations at once."""
        print("\n" + "="*50)
        print("Testing batch rollback")
        print("="*50)
        
        # Run all migrations
        if not self.run_migration_to('head'):
            print("❌ Failed to run all migrations")
            return False
            
        # Test rolling back to specific points
        test_points = [
            ('020', 'Roll back to before chat system'),
            ('010', 'Roll back to multi-model support'),
            ('005', 'Roll back to proxy configuration'),
            ('base', 'Roll back all migrations')
        ]
        
        for target, description in test_points:
            print(f"\n--- {description} ---")
            
            if not self.downgrade_to(target):
                print(f"❌ Failed to rollback to {target}")
                return False
                
            table_count = self.get_table_count()
            print(f"Table count: {table_count}")
            
            # Re-upgrade to head
            if target != 'base':
                if not self.run_migration_to('head'):
                    print(f"❌ Failed to re-upgrade from {target}")
                    return False
                    
        print("\n✅ Batch rollback tests passed!")
        return True
        
    def cleanup(self):
        """Drop the test database."""
        print("\nCleaning up test database...")
        
        conn = psycopg2.connect(database='postgres', **self.db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Terminate any connections to the test database
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{self.test_db_name}'
            AND pid <> pg_backend_pid()
        """)
        
        cur.execute(f"DROP DATABASE IF EXISTS {self.test_db_name}")
        cur.close()
        conn.close()
        
        print("Test database dropped")
        
    def run(self):
        """Run all rollback tests."""
        try:
            self.setup_test_database()
            
            # Run different rollback tests
            sequential_success = self.test_sequential_rollback()
            
            # Reset database for batch tests
            self.cleanup()
            self.setup_test_database()
            
            batch_success = self.test_batch_rollback()
            
            if sequential_success and batch_success:
                print("\n" + "="*50)
                print("✅ ALL ROLLBACK TESTS PASSED")
                print("="*50)
            else:
                print("\n" + "="*50)
                print("❌ SOME ROLLBACK TESTS FAILED")
                print("="*50)
                
        except Exception as e:
            print(f"\n❌ Test error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()


if __name__ == '__main__':
    tester = MigrationRollbackTester()
    tester.run()