import asyncio
import asyncpg

async def test_connection():
    try:
        # Test connection
        conn = await asyncpg.connect(
            host='localhost',
            port=5433,
            user='postgres',
            password='postgres',
            database='agencydark'
        )
        version = await conn.fetchval('SELECT version()')
        print(f"Connected successfully!")
        print(f"PostgreSQL version: {version}")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())