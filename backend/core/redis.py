import redis.asyncio as redis
from typing import Optional, Any
import json
import logging
from core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    async def initialize(self):
        try:
            self._redis = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close(self):
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
    
    async def ping(self) -> bool:
        if not self._redis:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        if not self._redis:
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except json.JSONDecodeError:
            return value
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        if not self._redis:
            return False
        
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            
            if ttl:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        if not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        if not self._redis:
            return False
        
        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        if not self._redis:
            return None
        
        try:
            return await self._redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return None
    
    async def get_pattern(self, pattern: str) -> dict:
        if not self._redis:
            return {}
        
        try:
            keys = await self._redis.keys(pattern)
            result = {}
            for key in keys:
                value = await self.get(key)
                if value is not None:
                    result[key] = value
            return result
        except Exception as e:
            logger.error(f"Redis pattern get error: {e}")
            return {}
    
    def make_key(self, tenant_id: str, prefix: str, *args) -> str:
        parts = [tenant_id, prefix] + list(args)
        return ":".join(str(part) for part in parts)


redis_client = RedisClient()