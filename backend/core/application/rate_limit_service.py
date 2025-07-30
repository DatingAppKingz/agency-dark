"""Rate limiting service for API and resource management."""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
import json

from models.user import User
from models.agency import Agency
from core.redis import redis_manager, RateLimiter
from core.exceptions import RateLimitError, ValidationError, NotFoundError


class RateLimitRule:
    """Rate limit rule configuration."""
    def __init__(
        self,
        endpoint: str,
        max_requests: int,
        window_seconds: int,
        burst_size: Optional[int] = None,
        role_limits: Optional[Dict[str, int]] = None
    ):
        self.endpoint = endpoint
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_size = burst_size or max_requests
        self.role_limits = role_limits or {}


class RateLimitService:
    """Service for managing rate limits."""
    
    # Default rate limit rules
    DEFAULT_RULES = {
        "auth": RateLimitRule("auth/*", 10, 300),  # 10 requests per 5 minutes
        "api_keys": RateLimitRule("api-keys/*", 20, 3600),  # 20 per hour
        "bulk_operations": RateLimitRule("bulk/*", 100, 3600, burst_size=20),  # 100 per hour, burst of 20
        "messages": RateLimitRule("messages/*", 1000, 60),  # 1000 per minute
        "analytics": RateLimitRule("analytics/*", 100, 300),  # 100 per 5 minutes
        "default": RateLimitRule("*", 300, 60)  # 300 per minute default
    }
    
    # Role-based multipliers
    ROLE_MULTIPLIERS = {
        "owner": 2.0,
        "admin": 1.5,
        "manager": 1.2,
        "chatter": 1.0,
        "model": 0.8
    }
    
    @staticmethod
    async def check_rate_limit(
        user_id: int,
        endpoint: str,
        user_role: Optional[str] = None,
        agency_id: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if user has exceeded rate limit for endpoint."""
        # Find matching rule
        rule = RateLimitService._get_rule_for_endpoint(endpoint)
        
        # Calculate actual limit based on user role
        base_limit = rule.max_requests
        if user_role and user_role in RateLimitService.ROLE_MULTIPLIERS:
            actual_limit = int(base_limit * RateLimitService.ROLE_MULTIPLIERS[user_role])
        else:
            actual_limit = base_limit
        
        # Check user-specific override
        custom_limit = await RateLimitService._get_custom_limit(user_id, endpoint)
        if custom_limit:
            actual_limit = custom_limit
        
        # Build rate limit key
        key = f"user:{user_id}:endpoint:{endpoint}"
        
        # Check rate limit
        allowed, remaining = await RateLimiter.check_rate_limit(
            key=key,
            max_requests=actual_limit,
            window=rule.window_seconds
        )
        
        # Calculate reset time
        reset_at = datetime.utcnow() + timedelta(seconds=rule.window_seconds)
        
        # Build response
        result = {
            "allowed": allowed,
            "limit": actual_limit,
            "remaining": remaining,
            "reset_at": reset_at.isoformat(),
            "window_seconds": rule.window_seconds
        }
        
        # If rate limited, add retry after
        if not allowed:
            result["retry_after"] = rule.window_seconds
        
        return allowed, result
    
    @staticmethod
    async def get_rate_limit_status(
        user_id: int,
        endpoints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get current rate limit status for user."""
        if not endpoints:
            # Get status for all default endpoints
            endpoints = list(RateLimitService.DEFAULT_RULES.keys())
        
        status = {}
        
        for endpoint in endpoints:
            rule = RateLimitService._get_rule_for_endpoint(endpoint)
            key = f"user:{user_id}:endpoint:{endpoint}"
            
            # Get current count from Redis
            current_key = f"rate_limit:{key}"
            current_count = await redis_manager.get(current_key)
            current = int(current_count) if current_count else 0
            
            # Get TTL
            ttl = await redis_manager.ttl(current_key)
            reset_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else datetime.utcnow()
            
            status[endpoint] = {
                "current": current,
                "limit": rule.max_requests,
                "remaining": max(0, rule.max_requests - current),
                "reset_at": reset_at.isoformat(),
                "window_seconds": rule.window_seconds
            }
        
        return {
            "user_id": user_id,
            "endpoints": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def set_custom_limit(
        db: AsyncSession,
        user_id: int,
        endpoint: str,
        max_requests: int,
        window_seconds: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Set custom rate limit for user and endpoint."""
        # Validate inputs
        if max_requests < 0:
            raise ValidationError("max_requests must be non-negative")
        
        # Default window from rule if not specified
        if not window_seconds:
            rule = RateLimitService._get_rule_for_endpoint(endpoint)
            window_seconds = rule.window_seconds
        
        # Store custom limit in Redis
        custom_key = f"custom_limit:{user_id}:{endpoint}"
        custom_data = {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "created_at": datetime.utcnow().isoformat()
        }
        
        if expires_at:
            custom_data["expires_at"] = expires_at.isoformat()
            expire_seconds = int((expires_at - datetime.utcnow()).total_seconds())
            await redis_manager.set(custom_key, json.dumps(custom_data), expire=expire_seconds)
        else:
            await redis_manager.set(custom_key, json.dumps(custom_data))
        
        return {
            "user_id": user_id,
            "endpoint": endpoint,
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "status": "active"
        }
    
    @staticmethod
    async def reset_rate_limit(
        user_id: int,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reset rate limit counters for user."""
        if endpoint:
            # Reset specific endpoint
            key = f"rate_limit:user:{user_id}:endpoint:{endpoint}"
            await redis_manager.delete(key)
            reset_endpoints = [endpoint]
        else:
            # Reset all endpoints
            pattern = f"rate_limit:user:{user_id}:endpoint:*"
            await redis_manager.flush_pattern(pattern)
            reset_endpoints = ["all"]
        
        return {
            "user_id": user_id,
            "reset_endpoints": reset_endpoints,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def get_agency_limits(
        db: AsyncSession,
        agency_id: int
    ) -> Dict[str, Any]:
        """Get rate limits for entire agency."""
        # Get agency
        agency = await db.get(Agency, agency_id)
        if not agency:
            raise NotFoundError("Agency not found")
        
        # Calculate agency limits based on plan
        base_multiplier = 1.0
        if agency.features:
            plan = agency.features.get("plan", "basic")
            if plan == "enterprise":
                base_multiplier = 5.0
            elif plan == "professional":
                base_multiplier = 2.0
            elif plan == "standard":
                base_multiplier = 1.5
        
        # Build agency limits
        limits = {}
        for name, rule in RateLimitService.DEFAULT_RULES.items():
            limits[name] = {
                "max_requests": int(rule.max_requests * base_multiplier),
                "window_seconds": rule.window_seconds,
                "burst_size": int(rule.burst_size * base_multiplier)
            }
        
        return {
            "agency_id": agency_id,
            "agency_name": agency.name,
            "plan": agency.features.get("plan", "basic") if agency.features else "basic",
            "multiplier": base_multiplier,
            "limits": limits
        }
    
    @staticmethod
    async def check_api_key_rate_limit(
        api_key: str,
        endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for API key access."""
        # API keys have stricter limits
        max_requests = 100  # 100 requests per hour for API keys
        window = 3600
        
        key = f"api_key:{api_key}:endpoint:{endpoint}"
        
        allowed, remaining = await RateLimiter.check_rate_limit(
            key=key,
            max_requests=max_requests,
            window=window
        )
        
        reset_at = datetime.utcnow() + timedelta(seconds=window)
        
        return allowed, {
            "allowed": allowed,
            "limit": max_requests,
            "remaining": remaining,
            "reset_at": reset_at.isoformat(),
            "window_seconds": window
        }
    
    @staticmethod
    def _get_rule_for_endpoint(endpoint: str) -> RateLimitRule:
        """Get rate limit rule for endpoint."""
        # Check for exact match
        if endpoint in RateLimitService.DEFAULT_RULES:
            return RateLimitService.DEFAULT_RULES[endpoint]
        
        # Check for pattern match
        for name, rule in RateLimitService.DEFAULT_RULES.items():
            if rule.endpoint.endswith("/*"):
                prefix = rule.endpoint[:-2]
                if endpoint.startswith(prefix):
                    return rule
        
        # Return default rule
        return RateLimitService.DEFAULT_RULES["default"]
    
    @staticmethod
    async def _get_custom_limit(user_id: int, endpoint: str) -> Optional[int]:
        """Get custom rate limit for user and endpoint."""
        custom_key = f"custom_limit:{user_id}:{endpoint}"
        custom_data = await redis_manager.get(custom_key)
        
        if custom_data:
            data = json.loads(custom_data) if isinstance(custom_data, str) else custom_data
            
            # Check if expired
            if "expires_at" in data:
                expires_at = datetime.fromisoformat(data["expires_at"])
                if expires_at < datetime.utcnow():
                    await redis_manager.delete(custom_key)
                    return None
            
            return data.get("max_requests")
        
        return None
    
    @staticmethod
    async def log_rate_limit_violation(
        user_id: int,
        endpoint: str,
        ip_address: Optional[str] = None
    ):
        """Log rate limit violation for monitoring."""
        violation_key = f"rate_violations:{datetime.utcnow().strftime('%Y-%m-%d')}"
        violation_data = {
            "user_id": user_id,
            "endpoint": endpoint,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add to sorted set for daily tracking
        await redis_manager.client.zadd(
            violation_key,
            {json.dumps(violation_data): datetime.utcnow().timestamp()}
        )
        
        # Expire after 7 days
        await redis_manager.expire(violation_key, 604800)