import asyncio
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_imports():
    try:
        logger.info("Testing basic imports...")
        import fastapi
        logger.info("✓ FastAPI imported")
        
        logger.info("Testing database connection...")
        from core.database import engine
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            logger.info("✓ Database connected")
        
        logger.info("Testing Redis connection...")
        from core.redis import redis_client
        await redis_client.ping()
        logger.info("✓ Redis connected")
        
        logger.info("Attempting to import main app...")
        from main import app
        logger.info("✓ Main app imported successfully\!")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_imports())
    sys.exit(0 if success else 1)
