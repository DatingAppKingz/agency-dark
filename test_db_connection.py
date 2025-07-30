import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_connection():
    # Test different URL formats
    urls = [
        "postgresql+asyncpg://postgres:postgres@localhost:5432/agencydark",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/agencydark",  # Docker port
    ]
    
    for url in urls:
        print(f"\nTesting: {url}")
        try:
            engine = create_async_engine(url, echo=True)
            async with engine.begin() as conn:
                result = await conn.execute("SELECT 1")
                print(f"✓ Success! Result: {result.scalar()}")
            await engine.dispose()
        except Exception as e:
            print(f"✗ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())