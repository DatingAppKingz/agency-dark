"""
Dynamic rate limiting service with cost-based throttling.
"""
import re
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import ipaddress

from models.rate_limit import (
    RateLimitConfig, RateLimitType, RateLimitTier, RateLimitAlgorithm,
    RateLimitBucket, RateLimitViolation, EndpointCost, RateLimitOverride
)
from models.user import User
from models.platform_api_key import PlatformAPIKey
from core.rate_limit.algorithms import (
    TokenBucketAlgorithm, SlidingWindowAlgorithm, 
    FixedWindowAlgorithm, AdaptiveRateLimiter, GeographicRateLimiter
)
from core.redis import redis_manager
from core.logger import get_logger
from core.audit.audit_service import audit_service
from models.audit_log import AuditAction, AuditSeverity

logger = get_logger(__name__)


class DynamicRateLimitService:
    """Service for dynamic rate limiting with multiple strategies."""
    
    def __init__(self):
        # Initialize algorithms
        self.algorithms = {
            RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketAlgorithm(),
            RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowAlgorithm(),
            RateLimitAlgorithm.FIXED_WINDOW: FixedWindowAlgorithm(),
            RateLimitAlgorithm.ADAPTIVE: AdaptiveRateLimiter()
        }
        
        self.geographic_limiter = GeographicRateLimiter()
        
        # Cache for configs and costs
        self._config_cache = {}
        self._cost_cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def check_rate_limit(
        self,
        db: AsyncSession,
        identifier: str,
        identifier_type: RateLimitType,
        endpoint: str,
        method: str = "GET",
        user: Optional[User] = None,
        api_key: Optional[PlatformAPIKey] = None,
        ip_address: Optional[str] = None,
        country_code: Optional[str] = None,
        request_size: int = 0,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed under rate limits.
        
        Returns:
            Tuple of (is_allowed, info_dict)
        """
        # Calculate request cost
        cost = await self._calculate_request_cost(
            db, endpoint, method, request_size
        )
        
        # Get applicable rate limit configs
        configs = await self._get_applicable_configs(
            db, identifier, identifier_type, user, api_key
        )
        
        # Check for overrides
        override = await self._get_active_override(
            db, identifier_type, identifier
        )
        
        # Apply each config
        results = []
        
        for config in configs:
            # Apply override if exists
            if override:
                config = self._apply_override(config, override)
            
            # Get the appropriate algorithm
            algorithm = self.algorithms.get(
                config.algorithm, 
                self.algorithms[RateLimitAlgorithm.TOKEN_BUCKET]
            )
            
            # Check each limit type (per minute, hour, day)
            for period, seconds in [
                ("per_minute", 60),
                ("per_hour", 3600),
                ("per_day", 86400)
            ]:
                # Get limit value
                if cost > 1:
                    # Use cost-based limits
                    limit_attr = f"cost_{period}"
                else:
                    # Use request-based limits
                    limit_attr = f"requests_{period}"
                
                limit_value = getattr(config, limit_attr)
                if not limit_value:
                    continue
                
                # Create unique key for this limit
                limit_key = f"{identifier_type.value}:{identifier}:{endpoint}:{period}"
                
                # Apply geographic limits if applicable
                if country_code and config.limit_type == RateLimitType.GEOGRAPHIC:
                    allowed, info = await self.geographic_limiter.check_and_update(
                        limit_key, int(limit_value), seconds, cost, country_code,
                        config.geographic_multiplier
                    )
                else:
                    # Regular rate limit check
                    allowed, info = await algorithm.check_and_update(
                        limit_key, int(limit_value), seconds, cost,
                        burst_size=config.burst_size,
                        refill_rate=config.refill_rate
                    )
                
                # Add config info
                info.update({
                    "config_id": str(config.id),
                    "config_name": config.name,
                    "limit_type": config.limit_type.value,
                    "period": period,
                    "cost": cost
                })
                
                results.append((allowed, info))
                
                # If any limit is exceeded, stop checking
                if not allowed:
                    # Log violation
                    await self._log_violation(
                        db, identifier, identifier_type, endpoint, method,
                        limit_attr, limit_value, cost, info,
                        ip_address, user_agent, country_code,
                        user, api_key, config
                    )
                    
                    return False, {
                        "allowed": False,
                        "reason": f"Rate limit exceeded for {period}",
                        "violated_limit": info,
                        "all_checks": results
                    }
        
        # All limits passed
        return True, {
            "allowed": True,
            "cost": cost,
            "checks_performed": len(results),
            "all_checks": results
        }
    
    async def get_current_usage(
        self,
        db: AsyncSession,
        identifier: str,
        identifier_type: RateLimitType,
        user: Optional[User] = None,
        api_key: Optional[PlatformAPIKey] = None
    ) -> Dict[str, Any]:
        """Get current usage statistics for an identifier."""
        configs = await self._get_applicable_configs(
            db, identifier, identifier_type, user, api_key
        )
        
        usage = {
            "identifier": identifier,
            "type": identifier_type.value,
            "configs": []
        }
        
        for config in configs:
            config_usage = {
                "name": config.name,
                "limits": {},
                "usage": {}
            }
            
            # Check each period
            for period, seconds in [
                ("per_minute", 60),
                ("per_hour", 3600),
                ("per_day", 86400)
            ]:
                limit = getattr(config, f"requests_{period}")
                if limit:
                    # Get current state
                    algorithm = self.algorithms.get(config.algorithm)
                    if algorithm:
                        state = await algorithm.get_state(
                            f"{identifier_type.value}:{identifier}:{period}"
                        )
                        config_usage["usage"][period] = state
                    
                    config_usage["limits"][period] = limit
            
            usage["configs"].append(config_usage)
        
        return usage
    
    async def create_rate_limit_config(
        self,
        db: AsyncSession,
        name: str,
        limit_type: RateLimitType,
        user: User,
        **kwargs
    ) -> RateLimitConfig:
        """Create a new rate limit configuration."""
        # Validate permissions
        if user.role.value not in ["SUPER_ADMIN", "AGENCY_ADMIN"]:
            raise PermissionError("Only admins can create rate limit configs")
        
        config = RateLimitConfig(
            name=name,
            limit_type=limit_type,
            created_by_id=user.id,
            agency_id=user.agency_id if limit_type != RateLimitType.GLOBAL else None,
            **kwargs
        )
        
        db.add(config)
        await db.commit()
        await db.refresh(config)
        
        # Clear cache
        self._config_cache.clear()
        
        # Log action
        await audit_service.log(
            db=db,
            action=AuditAction.SETTINGS_CHANGED,
            user=user,
            resource_type="rate_limit_config",
            resource_id=str(config.id),
            resource_name=name,
            description=f"Created rate limit config: {name}",
            metadata={"config_type": limit_type.value, "limits": kwargs}
        )
        
        return config
    
    async def update_endpoint_cost(
        self,
        db: AsyncSession,
        endpoint_pattern: str,
        base_cost: float,
        user: User,
        **kwargs
    ) -> EndpointCost:
        """Update or create endpoint cost configuration."""
        # Check if exists
        result = await db.execute(
            select(EndpointCost).where(
                EndpointCost.endpoint_pattern == endpoint_pattern
            )
        )
        endpoint_cost = result.scalar_one_or_none()
        
        if endpoint_cost:
            # Update existing
            endpoint_cost.base_cost = base_cost
            for key, value in kwargs.items():
                if hasattr(endpoint_cost, key):
                    setattr(endpoint_cost, key, value)
        else:
            # Create new
            endpoint_cost = EndpointCost(
                endpoint_pattern=endpoint_pattern,
                base_cost=base_cost,
                **kwargs
            )
            db.add(endpoint_cost)
        
        await db.commit()
        await db.refresh(endpoint_cost)
        
        # Clear cache
        self._cost_cache.clear()
        
        return endpoint_cost
    
    async def create_override(
        self,
        db: AsyncSession,
        target_type: RateLimitType,
        target_identifier: str,
        reason: str,
        expires_in_hours: int,
        created_by: User,
        **limits
    ) -> RateLimitOverride:
        """Create a temporary rate limit override."""
        override = RateLimitOverride(
            target_type=target_type,
            target_identifier=target_identifier,
            reason=reason,
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
            created_by_id=created_by.id,
            approved_by=created_by.email,
            **limits
        )
        
        db.add(override)
        await db.commit()
        await db.refresh(override)
        
        # Log action
        await audit_service.log(
            db=db,
            action=AuditAction.SETTINGS_CHANGED,
            user=created_by,
            resource_type="rate_limit_override",
            resource_id=str(override.id),
            description=f"Created rate limit override for {target_type.value}:{target_identifier}",
            metadata={
                "reason": reason,
                "expires_in_hours": expires_in_hours,
                "limits": limits
            },
            severity=AuditSeverity.WARNING
        )
        
        return override
    
    async def get_violations(
        self,
        db: AsyncSession,
        identifier: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[RateLimitViolation]:
        """Get rate limit violations."""
        query = select(RateLimitViolation)
        
        if identifier:
            query = query.where(RateLimitViolation.identifier == identifier)
        
        if start_date:
            query = query.where(RateLimitViolation.timestamp >= start_date)
        
        if end_date:
            query = query.where(RateLimitViolation.timestamp <= end_date)
        
        query = query.order_by(RateLimitViolation.timestamp.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def analyze_violations(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """Analyze rate limit violations for patterns."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get violation counts by identifier
        result = await db.execute(
            select(
                RateLimitViolation.identifier,
                RateLimitViolation.identifier_type,
                func.count(RateLimitViolation.id).label("violation_count"),
                func.avg(RateLimitViolation.severity_score).label("avg_severity")
            ).where(
                RateLimitViolation.timestamp >= start_date
            ).group_by(
                RateLimitViolation.identifier,
                RateLimitViolation.identifier_type
            ).order_by(
                func.count(RateLimitViolation.id).desc()
            )
        )
        
        top_violators = [
            {
                "identifier": row.identifier,
                "type": row.identifier_type.value,
                "violation_count": row.violation_count,
                "avg_severity": float(row.avg_severity or 0)
            }
            for row in result.all()
        ]
        
        # Get violations by endpoint
        result = await db.execute(
            select(
                RateLimitViolation.endpoint,
                func.count(RateLimitViolation.id).label("violation_count")
            ).where(
                RateLimitViolation.timestamp >= start_date
            ).group_by(
                RateLimitViolation.endpoint
            ).order_by(
                func.count(RateLimitViolation.id).desc()
            )
        )
        
        endpoint_violations = [
            {
                "endpoint": row.endpoint,
                "violation_count": row.violation_count
            }
            for row in result.all()
        ]
        
        # Get time-based patterns
        result = await db.execute(
            select(
                func.date_trunc('hour', RateLimitViolation.timestamp).label('hour'),
                func.count(RateLimitViolation.id).label('count')
            ).where(
                RateLimitViolation.timestamp >= start_date
            ).group_by(
                func.date_trunc('hour', RateLimitViolation.timestamp)
            )
        )
        
        hourly_violations = [
            {
                "hour": row.hour.isoformat(),
                "count": row.count
            }
            for row in result.all()
        ]
        
        return {
            "period_days": days,
            "total_violations": sum(v["violation_count"] for v in top_violators),
            "unique_violators": len(top_violators),
            "top_violators": top_violators[:10],
            "endpoint_violations": endpoint_violations[:10],
            "hourly_pattern": hourly_violations
        }
    
    # Private helper methods
    
    async def _calculate_request_cost(
        self,
        db: AsyncSession,
        endpoint: str,
        method: str,
        request_size: int
    ) -> float:
        """Calculate the cost of a request."""
        # Check cache
        cache_key = f"{method}:{endpoint}"
        if cache_key in self._cost_cache:
            cost_config = self._cost_cache[cache_key]
        else:
            # Get endpoint cost configuration
            result = await db.execute(
                select(EndpointCost).where(
                    EndpointCost.is_active == True
                ).order_by(EndpointCost.priority.desc())
            )
            endpoint_costs = result.scalars().all()
            
            # Find matching pattern
            cost_config = None
            for ec in endpoint_costs:
                if self._endpoint_matches(endpoint, ec.endpoint_pattern):
                    if not ec.method or ec.method == method:
                        cost_config = ec
                        break
            
            # Cache result
            self._cost_cache[cache_key] = cost_config
        
        if not cost_config:
            # Default cost
            return 1.0
        
        # Calculate total cost
        cost = cost_config.base_cost
        
        # Add size-based cost
        if request_size > 0:
            cost += (request_size / 1024) * cost_config.request_size_factor
        
        # Time-based multiplier
        current_hour = datetime.utcnow().hour
        if 9 <= current_hour <= 17:  # Business hours
            cost *= cost_config.peak_hours_multiplier
        else:
            cost *= cost_config.off_hours_multiplier
        
        return max(1.0, cost)
    
    async def _get_applicable_configs(
        self,
        db: AsyncSession,
        identifier: str,
        identifier_type: RateLimitType,
        user: Optional[User] = None,
        api_key: Optional[PlatformAPIKey] = None
    ) -> List[RateLimitConfig]:
        """Get all applicable rate limit configs for a request."""
        configs = []
        
        # Get global configs
        result = await db.execute(
            select(RateLimitConfig).where(
                and_(
                    RateLimitConfig.limit_type == RateLimitType.GLOBAL,
                    RateLimitConfig.is_active == True
                )
            )
        )
        configs.extend(result.scalars().all())
        
        # Get specific configs based on identifier type
        if identifier_type == RateLimitType.USER and user:
            # User-specific configs
            result = await db.execute(
                select(RateLimitConfig).where(
                    and_(
                        RateLimitConfig.limit_type == RateLimitType.USER,
                        RateLimitConfig.identifier == str(user.id),
                        RateLimitConfig.is_active == True
                    )
                )
            )
            configs.extend(result.scalars().all())
            
            # Tier-based configs
            if hasattr(user, 'tier'):
                result = await db.execute(
                    select(RateLimitConfig).where(
                        and_(
                            RateLimitConfig.limit_type == RateLimitType.TIER,
                            RateLimitConfig.tier == user.tier,
                            RateLimitConfig.is_active == True
                        )
                    )
                )
                configs.extend(result.scalars().all())
        
        elif identifier_type == RateLimitType.API_KEY and api_key:
            # API key specific configs
            result = await db.execute(
                select(RateLimitConfig).where(
                    and_(
                        RateLimitConfig.limit_type == RateLimitType.API_KEY,
                        RateLimitConfig.identifier == str(api_key.id),
                        RateLimitConfig.is_active == True
                    )
                )
            )
            configs.extend(result.scalars().all())
        
        elif identifier_type == RateLimitType.IP:
            # IP-based configs
            result = await db.execute(
                select(RateLimitConfig).where(
                    and_(
                        RateLimitConfig.limit_type == RateLimitType.IP,
                        RateLimitConfig.is_active == True
                    )
                )
            )
            configs.extend(result.scalars().all())
        
        # Sort by priority
        configs.sort(key=lambda c: c.priority, reverse=True)
        
        # Filter out expired configs
        configs = [c for c in configs if not c.expires_at or c.expires_at > datetime.utcnow()]
        
        return configs
    
    async def _get_active_override(
        self,
        db: AsyncSession,
        target_type: RateLimitType,
        target_identifier: str
    ) -> Optional[RateLimitOverride]:
        """Get active override for a target."""
        result = await db.execute(
            select(RateLimitOverride).where(
                and_(
                    RateLimitOverride.target_type == target_type,
                    RateLimitOverride.target_identifier == target_identifier,
                    RateLimitOverride.is_active == True,
                    RateLimitOverride.expires_at > datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()
    
    def _apply_override(
        self,
        config: RateLimitConfig,
        override: RateLimitOverride
    ) -> RateLimitConfig:
        """Apply override values to a config."""
        # Create a copy of the config
        overridden = RateLimitConfig()
        for key in config.__dict__:
            if not key.startswith('_'):
                setattr(overridden, key, getattr(config, key))
        
        # Apply overrides
        for field in [
            "requests_per_minute", "requests_per_hour", "requests_per_day",
            "cost_per_minute", "cost_per_hour", "cost_per_day"
        ]:
            override_value = getattr(override, field)
            if override_value is not None:
                setattr(overridden, field, override_value)
        
        return overridden
    
    def _endpoint_matches(self, endpoint: str, pattern: str) -> bool:
        """Check if endpoint matches pattern."""
        # Convert pattern to regex
        # Support wildcards: * and **
        regex_pattern = pattern.replace("**", ".*").replace("*", "[^/]*")
        regex_pattern = f"^{regex_pattern}$"
        
        return bool(re.match(regex_pattern, endpoint))
    
    async def _log_violation(
        self,
        db: AsyncSession,
        identifier: str,
        identifier_type: RateLimitType,
        endpoint: str,
        method: str,
        limit_type: str,
        limit_value: float,
        actual_value: float,
        info: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str],
        country_code: Optional[str],
        user: Optional[User],
        api_key: Optional[PlatformAPIKey],
        config: RateLimitConfig
    ):
        """Log a rate limit violation."""
        # Calculate severity
        severity = self._calculate_violation_severity(
            limit_value, actual_value, identifier_type
        )
        
        # Check if repeated violation
        recent_violations = await db.execute(
            select(func.count(RateLimitViolation.id)).where(
                and_(
                    RateLimitViolation.identifier == identifier,
                    RateLimitViolation.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                )
            )
        )
        is_repeated = recent_violations.scalar() > 0
        
        # Create violation record
        violation = RateLimitViolation(
            identifier=identifier,
            identifier_type=identifier_type,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            limit_type=limit_type,
            limit_value=limit_value,
            actual_value=actual_value,
            retry_after_seconds=info.get("retry_after_seconds", 60),
            country_code=country_code,
            is_repeated=is_repeated,
            severity_score=severity,
            user_id=user.id if user else None,
            api_key_id=api_key.id if api_key else None,
            config_id=config.id
        )
        
        db.add(violation)
        
        # Log to audit trail
        await audit_service.log(
            db=db,
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            user=user,
            resource_type="endpoint",
            resource_id=endpoint,
            description=f"Rate limit exceeded: {limit_type}",
            metadata={
                "limit": limit_value,
                "actual": actual_value,
                "identifier": identifier,
                "type": identifier_type.value
            },
            ip_address=ip_address,
            severity=AuditSeverity.WARNING if severity < 5 else AuditSeverity.ERROR
        )
        
        await db.commit()
    
    def _calculate_violation_severity(
        self,
        limit: float,
        actual: float,
        identifier_type: RateLimitType
    ) -> int:
        """Calculate severity score (1-10) for a violation."""
        # Base severity on how much limit was exceeded
        excess_ratio = actual / limit
        
        if excess_ratio < 1.5:
            severity = 2
        elif excess_ratio < 2:
            severity = 4
        elif excess_ratio < 5:
            severity = 6
        else:
            severity = 8
        
        # Adjust based on identifier type
        if identifier_type == RateLimitType.IP:
            severity += 1  # IP violations are more suspicious
        
        return min(10, severity)


# Global rate limit service instance
rate_limit_service = DynamicRateLimitService()