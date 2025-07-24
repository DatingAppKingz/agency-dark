import redis.asyncio as redis
from typing import Optional, Any, List, Dict, Set, Tuple
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
    
    async def get_pattern(self, pattern: str) -> Dict:
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
    
    async def info(self) -> Dict:
        """Get Redis server information."""
        if not self._redis:
            return {}
        
        try:
            return await self._redis.info()
        except Exception as e:
            logger.error(f"Redis info error: {e}")
            return {}
    
    async def incr(self, key: str) -> Optional[int]:
        """Increment a key by 1."""
        return await self.increment(key, 1)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set a timeout on key."""
        if not self._redis:
            return False
        
        try:
            return await self._redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False
    
    async def ttl(self, key: str) -> Optional[int]:
        """Get the time to live for a key in seconds."""
        if not self._redis:
            return None
        
        try:
            ttl = await self._redis.ttl(key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error(f"Redis ttl error: {e}")
            return None
    
    async def persist(self, key: str) -> bool:
        """Remove the expiration from a key."""
        if not self._redis:
            return False
        
        try:
            return await self._redis.persist(key)
        except Exception as e:
            logger.error(f"Redis persist error: {e}")
            return False
    
    async def setnx(self, key: str, value: Any) -> bool:
        """Set key to value if key does not exist."""
        if not self._redis:
            return False
        
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            return await self._redis.setnx(key, value)
        except Exception as e:
            logger.error(f"Redis setnx error: {e}")
            return False
    
    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple keys at once."""
        if not self._redis:
            return [None] * len(keys)
        
        try:
            values = await self._redis.mget(keys)
            result = []
            for value in values:
                if value is None:
                    result.append(None)
                else:
                    try:
                        result.append(json.loads(value))
                    except json.JSONDecodeError:
                        result.append(value)
            return result
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            return [None] * len(keys)
    
    async def mset(self, mapping: Dict[str, Any]) -> bool:
        """Set multiple keys at once."""
        if not self._redis:
            return False
        
        try:
            # Convert all values to JSON strings
            json_mapping = {}
            for key, value in mapping.items():
                if not isinstance(value, str):
                    json_mapping[key] = json.dumps(value)
                else:
                    json_mapping[key] = value
            
            await self._redis.mset(json_mapping)
            return True
        except Exception as e:
            logger.error(f"Redis mset error: {e}")
            return False
    
    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get a field from a hash."""
        if not self._redis:
            return None
        
        try:
            value = await self._redis.hget(name, key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis hget error: {e}")
            return None
    
    async def hset(self, name: str, key: str, value: Any) -> bool:
        """Set a field in a hash."""
        if not self._redis:
            return False
        
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            await self._redis.hset(name, key, value)
            return True
        except Exception as e:
            logger.error(f"Redis hset error: {e}")
            return False
    
    async def hgetall(self, name: str) -> Dict:
        """Get all fields and values from a hash."""
        if not self._redis:
            return {}
        
        try:
            data = await self._redis.hgetall(name)
            result = {}
            for key, value in data.items():
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            return result
        except Exception as e:
            logger.error(f"Redis hgetall error: {e}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete fields from a hash."""
        if not self._redis:
            return 0
        
        try:
            return await self._redis.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Redis hdel error: {e}")
            return 0
    
    async def sadd(self, key: str, *values: Any) -> int:
        """Add members to a set."""
        if not self._redis:
            return 0
        
        try:
            # Convert values to strings
            str_values = []
            for value in values:
                if not isinstance(value, str):
                    str_values.append(json.dumps(value))
                else:
                    str_values.append(value)
            return await self._redis.sadd(key, *str_values)
        except Exception as e:
            logger.error(f"Redis sadd error: {e}")
            return 0
    
    async def srem(self, key: str, *values: Any) -> int:
        """Remove members from a set."""
        if not self._redis:
            return 0
        
        try:
            # Convert values to strings
            str_values = []
            for value in values:
                if not isinstance(value, str):
                    str_values.append(json.dumps(value))
                else:
                    str_values.append(value)
            return await self._redis.srem(key, *str_values)
        except Exception as e:
            logger.error(f"Redis srem error: {e}")
            return 0
    
    async def smembers(self, key: str) -> Set[Any]:
        """Get all members of a set."""
        if not self._redis:
            return set()
        
        try:
            members = await self._redis.smembers(key)
            result = set()
            for member in members:
                try:
                    result.add(json.loads(member))
                except json.JSONDecodeError:
                    result.add(member)
            return result
        except Exception as e:
            logger.error(f"Redis smembers error: {e}")
            return set()
    
    async def sismember(self, key: str, value: Any) -> bool:
        """Check if value is a member of the set."""
        if not self._redis:
            return False
        
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            return await self._redis.sismember(key, value)
        except Exception as e:
            logger.error(f"Redis sismember error: {e}")
            return False
    
    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to the head of a list."""
        if not self._redis:
            return 0
        
        try:
            # Convert values to strings
            str_values = []
            for value in values:
                if not isinstance(value, str):
                    str_values.append(json.dumps(value))
                else:
                    str_values.append(value)
            return await self._redis.lpush(key, *str_values)
        except Exception as e:
            logger.error(f"Redis lpush error: {e}")
            return 0
    
    async def rpush(self, key: str, *values: Any) -> int:
        """Push values to the tail of a list."""
        if not self._redis:
            return 0
        
        try:
            # Convert values to strings
            str_values = []
            for value in values:
                if not isinstance(value, str):
                    str_values.append(json.dumps(value))
                else:
                    str_values.append(value)
            return await self._redis.rpush(key, *str_values)
        except Exception as e:
            logger.error(f"Redis rpush error: {e}")
            return 0
    
    async def lpop(self, key: str) -> Optional[Any]:
        """Remove and return the first element of a list."""
        if not self._redis:
            return None
        
        try:
            value = await self._redis.lpop(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis lpop error: {e}")
            return None
    
    async def rpop(self, key: str) -> Optional[Any]:
        """Remove and return the last element of a list."""
        if not self._redis:
            return None
        
        try:
            value = await self._redis.rpop(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis rpop error: {e}")
            return None
    
    async def lrange(self, key: str, start: int, stop: int) -> List[Any]:
        """Get a range of elements from a list."""
        if not self._redis:
            return []
        
        try:
            values = await self._redis.lrange(key, start, stop)
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except json.JSONDecodeError:
                    result.append(value)
            return result
        except Exception as e:
            logger.error(f"Redis lrange error: {e}")
            return []
    
    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """Trim a list to the specified range."""
        if not self._redis:
            return False
        
        try:
            await self._redis.ltrim(key, start, stop)
            return True
        except Exception as e:
            logger.error(f"Redis ltrim error: {e}")
            return False
    
    async def llen(self, key: str) -> int:
        """Get the length of a list."""
        if not self._redis:
            return 0
        
        try:
            return await self._redis.llen(key)
        except Exception as e:
            logger.error(f"Redis llen error: {e}")
            return 0
    
    async def zadd(self, key: str, mapping: Dict[Any, float]) -> int:
        """Add members to a sorted set with scores."""
        if not self._redis:
            return 0
        
        try:
            # Convert member keys to strings
            str_mapping = {}
            for member, score in mapping.items():
                if not isinstance(member, str):
                    str_mapping[json.dumps(member)] = score
                else:
                    str_mapping[member] = score
            return await self._redis.zadd(key, str_mapping)
        except Exception as e:
            logger.error(f"Redis zadd error: {e}")
            return 0
    
    async def zrange(self, key: str, start: int, stop: int, withscores: bool = False) -> List[Any]:
        """Get a range of members from a sorted set."""
        if not self._redis:
            return []
        
        try:
            result = await self._redis.zrange(key, start, stop, withscores=withscores)
            if withscores:
                # Return list of tuples (member, score)
                parsed_result = []
                for member, score in result:
                    try:
                        parsed_member = json.loads(member)
                    except json.JSONDecodeError:
                        parsed_member = member
                    parsed_result.append((parsed_member, score))
                return parsed_result
            else:
                # Return list of members
                parsed_result = []
                for member in result:
                    try:
                        parsed_result.append(json.loads(member))
                    except json.JSONDecodeError:
                        parsed_result.append(member)
                return parsed_result
        except Exception as e:
            logger.error(f"Redis zrange error: {e}")
            return []
    
    async def zrem(self, key: str, *members: Any) -> int:
        """Remove members from a sorted set."""
        if not self._redis:
            return 0
        
        try:
            # Convert members to strings
            str_members = []
            for member in members:
                if not isinstance(member, str):
                    str_members.append(json.dumps(member))
                else:
                    str_members.append(member)
            return await self._redis.zrem(key, *str_members)
        except Exception as e:
            logger.error(f"Redis zrem error: {e}")
            return 0


redis_client = RedisClient()