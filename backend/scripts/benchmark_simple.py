#!/usr/bin/env python3
"""
Simplified query performance benchmark focusing on index effectiveness.
"""
import asyncio
import time
import asyncpg
import uuid
from datetime import datetime, timedelta
import random

async def run_simple_benchmark():
    """Run a simplified benchmark to test index effectiveness."""
    
    # Database connection
    pool = await asyncpg.create_pool(
        host='localhost',
        port=5432,
        user='mariuszbudzisz',
        database='agencydark',
        min_size=5,
        max_size=10
    )
    
    print("="*60)
    print("SIMPLIFIED QUERY PERFORMANCE BENCHMARK")
    print("="*60)
    
    try:
        async with pool.acquire() as conn:
            # Get some sample data
            agencies = await conn.fetch("SELECT id FROM agencies LIMIT 5")
            if not agencies:
                print("No agencies found in database")
                return
                
            agency_id = agencies[0]['id']
            
            # Test 1: Users by agency and role (uses idx_users_agency_role)
            print("\n1. Testing users by agency and role query...")
            
            # With index
            await conn.execute("SET enable_indexscan = ON")
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE agency_id = $1 AND role = 'chatter'
                    LIMIT 20
                """, agency_id)
            with_index_time = (time.time() - start) / 50
            
            # Without index
            await conn.execute("SET enable_indexscan = OFF")
            await conn.execute("SET enable_bitmapscan = OFF")
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, username, email, role
                    FROM users
                    WHERE agency_id = $1 AND role = 'chatter'
                    LIMIT 20
                """, agency_id)
            without_index_time = (time.time() - start) / 50
            
            print(f"  With index: {with_index_time*1000:.2f}ms")
            print(f"  Without index: {without_index_time*1000:.2f}ms")
            print(f"  Speedup: {without_index_time/with_index_time:.1f}x")
            
            # Reset
            await conn.execute("SET enable_indexscan = ON")
            await conn.execute("SET enable_bitmapscan = ON")
            
            # Test 2: Active users (uses idx_users_active_verified)
            print("\n2. Testing active verified users query...")
            
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, username, email
                    FROM users
                    WHERE is_active = true AND is_verified = true
                    LIMIT 50
                """)
            active_users_time = (time.time() - start) / 50
            print(f"  Query time: {active_users_time*1000:.2f}ms")
            
            # Test 3: Model profiles by agency (uses idx_model_profiles_agency_active)
            print("\n3. Testing active models by agency query...")
            
            start = time.time()
            for _ in range(50):
                await conn.fetch("""
                    SELECT id, onlyfans_username, total_earnings
                    FROM model_profiles
                    WHERE agency_id = $1 AND is_active = true
                    ORDER BY total_earnings DESC
                    LIMIT 10
                """, agency_id)
            models_time = (time.time() - start) / 50
            print(f"  Query time: {models_time*1000:.2f}ms")
            
            # Test 4: Analyze query plan
            print("\n4. Query execution plan analysis:")
            print("-" * 40)
            
            plan = await conn.fetch("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id, username, email, role
                FROM users
                WHERE agency_id = $1 AND role = 'chatter'
                LIMIT 20
            """, agency_id)
            
            print("Users by agency and role plan:")
            for row in plan:
                print(f"  {row['QUERY PLAN']}")
            
            # Test 5: Check indexes
            print("\n5. Available indexes:")
            print("-" * 40)
            
            indexes = await conn.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('users', 'model_profiles', 'fans', 'notifications', 'audit_logs')
                ORDER BY tablename, indexname
            """)
            
            current_table = None
            for idx in indexes:
                if idx['tablename'] != current_table:
                    current_table = idx['tablename']
                    print(f"\n{current_table}:")
                print(f"  - {idx['indexname']}")
            
            # Test 6: Table statistics
            print("\n6. Table statistics:")
            print("-" * 40)
            
            stats = await conn.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_autovacuum
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND tablename IN ('users', 'model_profiles', 'fans', 'notifications', 'audit_logs')
                ORDER BY n_live_tup DESC
            """)
            
            for stat in stats:
                print(f"\n{stat['tablename']}:")
                print(f"  Rows: {stat['row_count']:,}")
                print(f"  Dead rows: {stat['dead_rows']:,}")
                print(f"  Last vacuum: {stat['last_vacuum'] or 'Never'}")
                print(f"  Last autovacuum: {stat['last_autovacuum'] or 'Never'}")
                
    finally:
        await pool.close()
    
    print("\n" + "="*60)
    print("Benchmark completed")
    print("="*60)

if __name__ == '__main__':
    asyncio.run(run_simple_benchmark())