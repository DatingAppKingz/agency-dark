#!/usr/bin/env python3
"""
Benchmark query performance improvements from database optimizations.
Tests the effectiveness of indexes added in migrations 004 and 022.
"""
import asyncio
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import asyncpg
from datetime import datetime, timedelta
import random
import uuid
from typing import List, Dict, Any

class QueryPerformanceBenchmark:
    def __init__(self):
        self.test_db_name = "agencydark_perf_test"
        self.db_params = {
            'host': 'localhost',
            'port': 5432,
            'user': 'mariuszbudzisz'
        }
        self.agencies = []
        self.users = []
        self.models = []
        self.fans = []
        
    async def setup_test_database(self):
        """Create and populate test database."""
        print("Setting up test database...")
        
        # Create database
        conn = psycopg2.connect(database='postgres', **self.db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(f"DROP DATABASE IF EXISTS {self.test_db_name}")
        cur.execute(f"CREATE DATABASE {self.test_db_name}")
        
        cur.close()
        conn.close()
        
        # Connect with asyncpg
        self.pool = await asyncpg.create_pool(
            host='localhost',
            port=5432,
            user='mariuszbudzisz',
            database=self.test_db_name,
            min_size=10,
            max_size=20
        )
        
        # Run migrations
        await self._run_migrations()
        
        # Populate test data
        await self._populate_test_data()
        
    async def _run_migrations(self):
        """Run database migrations."""
        print("Running migrations...")
        import subprocess
        from pathlib import Path
        
        backend_dir = Path(__file__).parent.parent
        env = {
            'DATABASE_URL': f"postgresql+asyncpg://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'DATABASE_SYNC_URL': f"postgresql://mariuszbudzisz@localhost:5432/{self.test_db_name}",
            'PYTHONPATH': str(backend_dir)
        }
        
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            cwd=backend_dir,
            env={**subprocess.os.environ, **env},
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Migration failed: {result.stderr}")
            raise Exception("Migration failed")
            
        print("Migrations completed")
        
    async def _populate_test_data(self):
        """Populate database with test data."""
        print("Populating test data...")
        
        async with self.pool.acquire() as conn:
            # Create agencies
            print("Creating 10 agencies...")
            for i in range(10):
                agency_id = str(uuid.uuid4())
                await conn.execute("""
                    INSERT INTO agencies (id, name, slug, created_at, updated_at)
                    VALUES ($1, $2, $3, NOW(), NOW())
                """, agency_id, f"Agency {i}", f"agency-{i}")
                self.agencies.append(agency_id)
            
            # Create users (100 per agency)
            print("Creating 1000 users...")
            for agency_id in self.agencies:
                for i in range(100):
                    user_id = str(uuid.uuid4())
                    is_active = random.choice([True, True, True, False])  # 75% active
                    is_verified = random.choice([True, True, False])  # 66% verified
                    last_login = datetime.now() - timedelta(days=random.randint(0, 90))
                    
                    await conn.execute("""
                        INSERT INTO users (id, agency_id, email, username, hashed_password, 
                                         role, is_active, is_verified, last_login, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                    """, user_id, agency_id, f"user{i}@agency{self.agencies.index(agency_id)}.com",
                        f"user{i}_a{self.agencies.index(agency_id)}", "hashed",
                        random.choice(['agency_owner', 'agency_admin', 'chatter', 'chatter']),
                        is_active, is_verified, last_login)
                    self.users.append((user_id, agency_id))
            
            # Create model profiles (50 per agency)
            print("Creating 500 model profiles...")
            for agency_id in self.agencies:
                for i in range(50):
                    model_id = str(uuid.uuid4())
                    is_active = random.choice([True, True, True, False])  # 75% active
                    total_earnings = random.uniform(0, 100000)
                    last_sync = datetime.now() - timedelta(hours=random.randint(0, 72))
                    
                    await conn.execute("""
                        INSERT INTO model_profiles (id, agency_id, onlyfans_id, onlyfans_username,
                                                  display_name, is_active, total_earnings, 
                                                  last_sync_at, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                    """, model_id, agency_id, f"of_{model_id[:8]}", f"model{i}_a{self.agencies.index(agency_id)}",
                        f"Model {i}", is_active, total_earnings, last_sync)
                    self.models.append((model_id, agency_id))
            
            # Create fans (1000 per model = 500k total)
            print("Creating 500,000 fans (this will take a moment)...")
            batch_size = 1000
            fan_data = []
            
            for model_id, agency_id in self.models:
                for i in range(1000):
                    fan_id = str(uuid.uuid4())
                    is_subscriber = random.choice([True, True, False])  # 66% subscribers
                    is_paying = random.choice([True, False]) if is_subscriber else False
                    total_spent = random.uniform(0, 5000) if is_paying else 0
                    last_active = datetime.now() - timedelta(days=random.randint(0, 30))
                    
                    fan_data.append((
                        fan_id, model_id, f"of_{fan_id[:8]}", f"fan_{fan_id[:8]}",
                        is_subscriber, is_paying, total_spent, last_active
                    ))
                    
                    # Insert in batches
                    if len(fan_data) >= batch_size:
                        await conn.executemany("""
                            INSERT INTO fans (id, model_id, onlyfans_user_id, username,
                                            is_subscriber, is_paying, total_spent, last_active_at,
                                            created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                        """, fan_data)
                        fan_data = []
                        
                        if len(self.fans) % 50000 == 0:
                            print(f"  Created {len(self.fans)} fans...")
                    
                    self.fans.append((fan_id, model_id))
            
            # Insert remaining fans
            if fan_data:
                await conn.executemany("""
                    INSERT INTO fans (id, model_id, onlyfans_user_id, username,
                                    is_subscriber, is_paying, total_spent, last_active_at,
                                    created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                """, fan_data)
            
            # Create notifications (10k total)
            print("Creating 10,000 notifications...")
            notification_data = []
            for i in range(10000):
                user_id, agency_id = random.choice(self.users)
                notification_data.append((
                    str(uuid.uuid4()), agency_id, user_id,
                    random.choice(['info', 'warning', 'error', 'success']),
                    f"Notification {i}", f"Message {i}",
                    random.choice([True, False, False])  # 33% read
                ))
                
                if len(notification_data) >= batch_size:
                    await conn.executemany("""
                        INSERT INTO notifications (id, agency_id, user_id, type, title, message, read, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    """, notification_data)
                    notification_data = []
            
            if notification_data:
                await conn.executemany("""
                    INSERT INTO notifications (id, agency_id, user_id, type, title, message, read, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                """, notification_data)
            
            # Create audit logs (50k total)
            print("Creating 50,000 audit logs...")
            audit_data = []
            for i in range(50000):
                user_id, agency_id = random.choice(self.users)
                created_at = datetime.now() - timedelta(days=random.randint(0, 90))
                audit_data.append((
                    str(uuid.uuid4()), agency_id, user_id,
                    random.choice(['login', 'logout', 'update', 'create', 'delete']),
                    random.choice(['user', 'model', 'fan', 'transaction']),
                    str(uuid.uuid4()), created_at
                ))
                
                if len(audit_data) >= batch_size:
                    await conn.executemany("""
                        INSERT INTO audit_logs (id, agency_id, user_id, action, resource_type, resource_id, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, audit_data)
                    audit_data = []
            
            if audit_data:
                await conn.executemany("""
                    INSERT INTO audit_logs (id, agency_id, user_id, action, resource_type, resource_id, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, audit_data)
            
        print("Test data populated")
        
    async def run_benchmarks(self):
        """Run performance benchmarks."""
        print("\n" + "="*60)
        print("QUERY PERFORMANCE BENCHMARKS")
        print("="*60)
        
        results = {}
        
        # Test 1: Agency-scoped user queries
        results['user_queries'] = await self._benchmark_user_queries()
        
        # Test 2: Model profile queries
        results['model_queries'] = await self._benchmark_model_queries()
        
        # Test 3: Fan queries
        results['fan_queries'] = await self._benchmark_fan_queries()
        
        # Test 4: Notification queries
        results['notification_queries'] = await self._benchmark_notification_queries()
        
        # Test 5: Audit log queries
        results['audit_queries'] = await self._benchmark_audit_queries()
        
        # Test 6: Complex join queries
        results['join_queries'] = await self._benchmark_join_queries()
        
        return results
        
    async def _benchmark_user_queries(self):
        """Benchmark user-related queries."""
        print("\n1. User Query Benchmarks")
        print("-" * 40)
        
        results = {}
        agency_id = random.choice(self.agencies)
        
        async with self.pool.acquire() as conn:
            # Query 1: Active users in agency (uses idx_users_agency_role)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE agency_id = $1 AND is_active = true AND is_verified = true
                    ORDER BY created_at DESC
                    LIMIT 20
                """, agency_id)
            results['active_users'] = (time.time() - start) / 100
            
            # Query 2: Users by role (uses idx_users_agency_role)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, email, last_login
                    FROM users
                    WHERE agency_id = $1 AND role = 'chatter'
                    ORDER BY last_login DESC
                    LIMIT 50
                """, agency_id)
            results['users_by_role'] = (time.time() - start) / 100
            
            # Query 3: Recently logged in users (uses idx_users_last_login)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE last_login > NOW() - INTERVAL '7 days'
                    AND agency_id = $1
                    ORDER BY last_login DESC
                """, agency_id)
            results['recent_logins'] = (time.time() - start) / 100
            
        print(f"  Active users query: {results['active_users']*1000:.2f}ms avg")
        print(f"  Users by role query: {results['users_by_role']*1000:.2f}ms avg")
        print(f"  Recent logins query: {results['recent_logins']*1000:.2f}ms avg")
        
        return results
        
    async def _benchmark_model_queries(self):
        """Benchmark model profile queries."""
        print("\n2. Model Profile Query Benchmarks")
        print("-" * 40)
        
        results = {}
        agency_id = random.choice(self.agencies)
        
        async with self.pool.acquire() as conn:
            # Query 1: Active models by agency (uses idx_model_profiles_agency_active)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, onlyfans_username, total_earnings
                    FROM model_profiles
                    WHERE agency_id = $1 AND is_active = true
                    ORDER BY total_earnings DESC
                    LIMIT 20
                """, agency_id)
            results['active_models'] = (time.time() - start) / 100
            
            # Query 2: Models needing sync (uses idx_model_profiles_last_sync)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, onlyfans_username, last_sync_at
                    FROM model_profiles
                    WHERE last_sync_at < NOW() - INTERVAL '24 hours'
                    AND is_active = true
                    ORDER BY last_sync_at ASC
                    LIMIT 10
                """)
            results['models_needing_sync'] = (time.time() - start) / 100
            
            # Query 3: Top earners (uses idx_model_profiles_earnings)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, onlyfans_username, total_earnings
                    FROM model_profiles
                    WHERE agency_id = $1
                    ORDER BY total_earnings DESC
                    LIMIT 10
                """, agency_id)
            results['top_earners'] = (time.time() - start) / 100
            
        print(f"  Active models query: {results['active_models']*1000:.2f}ms avg")
        print(f"  Models needing sync: {results['models_needing_sync']*1000:.2f}ms avg")
        print(f"  Top earners query: {results['top_earners']*1000:.2f}ms avg")
        
        return results
        
    async def _benchmark_fan_queries(self):
        """Benchmark fan-related queries."""
        print("\n3. Fan Query Benchmarks")
        print("-" * 40)
        
        results = {}
        model_id, _ = random.choice(self.models)
        
        async with self.pool.acquire() as conn:
            # Query 1: Active paying fans (uses idx_fans_active_subscribers)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, total_spent
                    FROM fans
                    WHERE model_id = $1 AND is_subscriber = true AND is_paying = true
                    ORDER BY total_spent DESC
                    LIMIT 50
                """, model_id)
            results['paying_fans'] = (time.time() - start) / 100
            
            # Query 2: Recently active fans (uses idx_fans_last_active)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, last_active_at
                    FROM fans
                    WHERE model_id = $1 AND last_active_at > NOW() - INTERVAL '7 days'
                    ORDER BY last_active_at DESC
                    LIMIT 100
                """, model_id)
            results['recently_active'] = (time.time() - start) / 100
            
            # Query 3: High value fans (uses idx_fans_total_spent)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, username, total_spent
                    FROM fans
                    WHERE model_id = $1 AND total_spent > 100
                    ORDER BY total_spent DESC
                """, model_id)
            results['high_value_fans'] = (time.time() - start) / 100
            
        print(f"  Paying fans query: {results['paying_fans']*1000:.2f}ms avg")
        print(f"  Recently active fans: {results['recently_active']*1000:.2f}ms avg")
        print(f"  High value fans: {results['high_value_fans']*1000:.2f}ms avg")
        
        return results
        
    async def _benchmark_notification_queries(self):
        """Benchmark notification queries."""
        print("\n4. Notification Query Benchmarks")
        print("-" * 40)
        
        results = {}
        user_id, agency_id = random.choice(self.users)
        
        async with self.pool.acquire() as conn:
            # Query 1: Unread notifications (uses idx_notifications_user_read)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, title, message, created_at
                    FROM notifications
                    WHERE user_id = $1 AND read = false
                    ORDER BY created_at DESC
                    LIMIT 20
                """, user_id)
            results['unread_notifications'] = (time.time() - start) / 100
            
            # Query 2: Agency unread count (uses idx_notifications_agency_unread)
            start = time.time()
            for _ in range(100):
                await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM notifications
                    WHERE agency_id = $1 AND read = false
                """, agency_id)
            results['agency_unread_count'] = (time.time() - start) / 100
            
        print(f"  Unread notifications: {results['unread_notifications']*1000:.2f}ms avg")
        print(f"  Agency unread count: {results['agency_unread_count']*1000:.2f}ms avg")
        
        return results
        
    async def _benchmark_audit_queries(self):
        """Benchmark audit log queries."""
        print("\n5. Audit Log Query Benchmarks")
        print("-" * 40)
        
        results = {}
        agency_id = random.choice(self.agencies)
        
        async with self.pool.acquire() as conn:
            # Query 1: Recent audit logs (uses idx_audit_logs_agency_date)
            start = time.time()
            for _ in range(100):
                await conn.fetch("""
                    SELECT id, action, resource_type, created_at
                    FROM audit_logs
                    WHERE agency_id = $1 AND created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT 50
                """, agency_id)
            results['recent_audit_logs'] = (time.time() - start) / 100
            
            # Query 2: Resource audit trail (uses idx_audit_logs_resource)
            start = time.time()
            for _ in range(100):
                resource_id = str(uuid.uuid4())
                await conn.fetch("""
                    SELECT id, action, user_id, created_at
                    FROM audit_logs
                    WHERE resource_type = 'user' AND resource_id = $1
                    ORDER BY created_at DESC
                """, resource_id)
            results['resource_audit_trail'] = (time.time() - start) / 100
            
        print(f"  Recent audit logs: {results['recent_audit_logs']*1000:.2f}ms avg")
        print(f"  Resource audit trail: {results['resource_audit_trail']*1000:.2f}ms avg")
        
        return results
        
    async def _benchmark_join_queries(self):
        """Benchmark complex join queries."""
        print("\n6. Complex Join Query Benchmarks")
        print("-" * 40)
        
        results = {}
        agency_id = random.choice(self.agencies)
        
        async with self.pool.acquire() as conn:
            # Query 1: Models with fan counts
            start = time.time()
            for _ in range(20):  # Fewer iterations for complex queries
                await conn.fetch("""
                    SELECT 
                        m.id,
                        m.onlyfans_username,
                        m.total_earnings,
                        COUNT(DISTINCT f.id) as fan_count,
                        COUNT(DISTINCT f.id) FILTER (WHERE f.is_paying = true) as paying_fan_count
                    FROM model_profiles m
                    LEFT JOIN fans f ON f.model_id = m.id
                    WHERE m.agency_id = $1 AND m.is_active = true
                    GROUP BY m.id, m.onlyfans_username, m.total_earnings
                    ORDER BY m.total_earnings DESC
                    LIMIT 10
                """, agency_id)
            results['models_with_fan_counts'] = (time.time() - start) / 20
            
            # Query 2: User activity summary
            start = time.time()
            for _ in range(20):
                await conn.fetch("""
                    SELECT 
                        u.id,
                        u.username,
                        u.role,
                        COUNT(DISTINCT al.id) as audit_count,
                        MAX(al.created_at) as last_action
                    FROM users u
                    LEFT JOIN audit_logs al ON al.user_id = u.id
                    WHERE u.agency_id = $1 
                        AND u.is_active = true
                        AND al.created_at > NOW() - INTERVAL '30 days'
                    GROUP BY u.id, u.username, u.role
                    ORDER BY audit_count DESC
                    LIMIT 20
                """, agency_id)
            results['user_activity_summary'] = (time.time() - start) / 20
            
        print(f"  Models with fan counts: {results['models_with_fan_counts']*1000:.2f}ms avg")
        print(f"  User activity summary: {results['user_activity_summary']*1000:.2f}ms avg")
        
        return results
        
    async def test_index_effectiveness(self):
        """Test the effectiveness of indexes by comparing with and without."""
        print("\n" + "="*60)
        print("INDEX EFFECTIVENESS TEST")
        print("="*60)
        
        agency_id = random.choice(self.agencies)
        
        async with self.pool.acquire() as conn:
            # Test query with index
            await conn.execute("SET enable_indexscan = ON")
            await conn.execute("SET enable_bitmapscan = ON")
            
            # Warm up
            await conn.fetch("""
                SELECT id, username, email, role
                FROM users
                WHERE agency_id = $1 AND is_active = true
                ORDER BY created_at DESC
                LIMIT 20
            """, agency_id)
            
            # Measure with index
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE agency_id = $1 AND is_active = true
                    ORDER BY created_at DESC
                    LIMIT 20
                """, agency_id)
            with_index = (time.time() - start) / 50
            
            # Test query without index
            await conn.execute("SET enable_indexscan = OFF")
            await conn.execute("SET enable_bitmapscan = OFF")
            
            # Measure without index
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE agency_id = $1 AND is_active = true
                    ORDER BY created_at DESC
                    LIMIT 20
                """, agency_id)
            without_index = (time.time() - start) / 50
            
            # Reset settings
            await conn.execute("SET enable_indexscan = ON")
            await conn.execute("SET enable_bitmapscan = ON")
            
        print(f"\nQuery: Active users by agency")
        print(f"  With index: {with_index*1000:.2f}ms avg")
        print(f"  Without index: {without_index*1000:.2f}ms avg")
        print(f"  Speedup: {without_index/with_index:.1f}x")
        
        return {
            'with_index': with_index,
            'without_index': without_index,
            'speedup': without_index / with_index
        }
        
    async def analyze_query_plans(self):
        """Analyze query execution plans."""
        print("\n" + "="*60)
        print("QUERY EXECUTION PLAN ANALYSIS")
        print("="*60)
        
        agency_id = random.choice(self.agencies)
        model_id, _ = random.choice(self.models)
        
        async with self.pool.acquire() as conn:
            # Plan 1: Active users query
            print("\n1. Active users query plan:")
            print("-" * 40)
            plan = await conn.fetch("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id, username, email, role
                FROM users
                WHERE agency_id = $1 AND is_active = true AND is_verified = true
                ORDER BY created_at DESC
                LIMIT 20
            """, agency_id)
            for row in plan:
                print(row['QUERY PLAN'])
            
            # Plan 2: Paying fans query
            print("\n2. Paying fans query plan:")
            print("-" * 40)
            plan = await conn.fetch("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id, onlyfans_username, total_spent
                FROM fans
                WHERE model_id = $1 AND is_subscriber = true AND is_paying = true
                ORDER BY total_spent DESC
                LIMIT 50
            """, model_id)
            for row in plan:
                print(row['QUERY PLAN'])
            
            # Plan 3: Complex join query
            print("\n3. Models with fan counts query plan:")
            print("-" * 40)
            plan = await conn.fetch("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT 
                    m.id,
                    m.onlyfans_username,
                    COUNT(DISTINCT f.id) as fan_count
                FROM model_profiles m
                LEFT JOIN fans f ON f.model_id = m.id
                WHERE m.agency_id = $1 AND m.is_active = true
                GROUP BY m.id, m.onlyfans_username
                LIMIT 10
            """, agency_id)
            for row in plan:
                print(row['QUERY PLAN'])
                
    async def cleanup(self):
        """Clean up test database."""
        print("\nCleaning up...")
        
        if hasattr(self, 'pool'):
            await self.pool.close()
        
        conn = psycopg2.connect(database='postgres', **self.db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
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
        
    async def run(self):
        """Run all benchmarks."""
        try:
            await self.setup_test_database()
            
            # Run benchmarks
            results = await self.run_benchmarks()
            
            # Test index effectiveness
            index_test = await self.test_index_effectiveness()
            
            # Analyze query plans
            await self.analyze_query_plans()
            
            # Summary
            print("\n" + "="*60)
            print("BENCHMARK SUMMARY")
            print("="*60)
            
            total_queries = 0
            total_time = 0
            
            for category, queries in results.items():
                for query_name, time_taken in queries.items():
                    total_queries += 1
                    total_time += time_taken
                    
            avg_time = (total_time / total_queries) * 1000
            print(f"\nTotal queries benchmarked: {total_queries}")
            print(f"Average query time: {avg_time:.2f}ms")
            print(f"Index speedup: {index_test['speedup']:.1f}x")
            
            # Performance assessment
            if avg_time < 10:
                print("\n✅ EXCELLENT: Average query time under 10ms")
            elif avg_time < 50:
                print("\n✅ GOOD: Average query time under 50ms")
            elif avg_time < 100:
                print("\n⚠️  ACCEPTABLE: Average query time under 100ms")
            else:
                print("\n❌ POOR: Average query time over 100ms")
                
        except Exception as e:
            print(f"\n❌ Benchmark error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()


if __name__ == '__main__':
    benchmark = QueryPerformanceBenchmark()
    asyncio.run(benchmark.run())