#!/usr/bin/env python3
"""
Generate data for performance benchmarking in the existing database.
"""
import asyncio
import asyncpg
import uuid
from datetime import datetime, timedelta
import random

async def generate_data():
    """Generate test data for benchmarking."""
    
    pool = await asyncpg.create_pool(
        host='localhost',
        port=5432,
        user='mariuszbudzisz',
        database='agencydark',
        min_size=5,
        max_size=10
    )
    
    print("Generating benchmark data...")
    
    try:
        async with pool.acquire() as conn:
            # Create one test agency
            agency_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO agencies (id, name, slug, created_at, updated_at)
                VALUES ($1, $2, $3, NOW(), NOW())
                ON CONFLICT (slug) DO UPDATE SET updated_at = NOW()
                RETURNING id
            """, agency_id, "Benchmark Agency", "benchmark-agency")
            
            print(f"Created agency: {agency_id}")
            
            # Create 100 users
            print("Creating users...")
            user_ids = []
            for i in range(100):
                user_id = str(uuid.uuid4())
                try:
                    await conn.execute("""
                        INSERT INTO users (id, agency_id, email, username, hashed_password,
                                         role, is_active, is_verified, last_login, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                    """, user_id, agency_id, f"user{i}@benchmark.com", f"user{i}",
                        "hashed", random.choice(['agency_admin', 'chatter', 'chatter', 'chatter']),
                        random.choice([True, True, True, False]),
                        random.choice([True, True, False]),
                        datetime.now() - timedelta(days=random.randint(0, 30)))
                    user_ids.append(user_id)
                except Exception as e:
                    pass  # Skip duplicates
            
            print(f"Created {len(user_ids)} users")
            
            # Create 20 model profiles
            print("Creating model profiles...")
            model_ids = []
            for i in range(20):
                model_id = str(uuid.uuid4())
                try:
                    await conn.execute("""
                        INSERT INTO model_profiles (id, agency_id, onlyfans_id, onlyfans_username,
                                                  display_name, is_active, total_earnings,
                                                  last_sync_at, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                    """, model_id, agency_id, f"of_{i}", f"model{i}",
                        f"Model {i}", random.choice([True, True, True, False]),
                        random.uniform(1000, 50000),
                        datetime.now() - timedelta(hours=random.randint(0, 48)))
                    model_ids.append(model_id)
                except Exception as e:
                    pass  # Skip duplicates
            
            print(f"Created {len(model_ids)} models")
            
            # Create fans for each model
            print("Creating fans...")
            fan_count = 0
            for model_id in model_ids:
                for i in range(100):
                    fan_id = str(uuid.uuid4())
                    try:
                        await conn.execute("""
                            INSERT INTO fans (id, model_id, onlyfans_user_id, username,
                                            is_subscriber, is_paying, total_spent, last_active_at,
                                            created_at, updated_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                        """, fan_id, model_id, f"of_fan_{fan_id[:8]}", f"fan_{fan_id[:8]}",
                            random.choice([True, True, False]),
                            random.choice([True, False]),
                            random.uniform(0, 1000) if random.choice([True, False]) else 0,
                            datetime.now() - timedelta(days=random.randint(0, 7)))
                        fan_count += 1
                    except Exception as e:
                        pass
            
            print(f"Created {fan_count} fans")
            
            # Create notifications
            print("Creating notifications...")
            notif_count = 0
            for _ in range(500):
                try:
                    await conn.execute("""
                        INSERT INTO notifications (id, agency_id, user_id, type, title, message, read, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    """, str(uuid.uuid4()), agency_id, random.choice(user_ids) if user_ids else None,
                        random.choice(['info', 'warning', 'error', 'success']),
                        f"Notification {notif_count}", f"Message {notif_count}",
                        random.choice([True, False, False]))
                    notif_count += 1
                except Exception as e:
                    pass
            
            print(f"Created {notif_count} notifications")
            
            # Create audit logs
            print("Creating audit logs...")
            audit_count = 0
            for _ in range(1000):
                try:
                    await conn.execute("""
                        INSERT INTO audit_logs (id, agency_id, user_id, action, resource_type, resource_id, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, str(uuid.uuid4()), agency_id, random.choice(user_ids) if user_ids else None,
                        random.choice(['login', 'logout', 'update', 'create', 'delete']),
                        random.choice(['user', 'model', 'fan']),
                        str(uuid.uuid4()),
                        datetime.now() - timedelta(days=random.randint(0, 30)))
                    audit_count += 1
                except Exception as e:
                    pass
            
            print(f"Created {audit_count} audit logs")
            
            # Update statistics
            await conn.execute("ANALYZE")
            print("\nDatabase statistics updated")
            
    finally:
        await pool.close()
    
    print("\nBenchmark data generation completed!")

if __name__ == '__main__':
    asyncio.run(generate_data())