"""
IP whitelisting for admin endpoints
"""
import ipaddress
from typing import List, Optional, Set, Union
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text

from core.database import Base
from core.config import settings
from core.logging import logger
from core.redis import redis_client


class IPWhitelist(Base):
    """IP whitelist database model"""
    __tablename__ = "ip_whitelists"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ip_address = Column(String, nullable=False, unique=True)  # Can be single IP or CIDR
    description = Column(String)
    
    # Scope
    is_global = Column(Boolean, default=False)  # Applies to all admin endpoints
    agency_id = Column(PG_UUID(as_uuid=True), nullable=True)  # Agency-specific
    user_id = Column(PG_UUID(as_uuid=True), nullable=True)  # User-specific
    
    # Endpoints
    allowed_endpoints = Column(JSON, default=[])  # List of endpoint patterns
    
    # Temporal restrictions
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    
    # Metadata
    created_by = Column(PG_UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Rate limiting
    max_requests_per_hour = Column(Integer, default=1000)


class IPWhitelistService:
    """Service for managing IP whitelists"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache_ttl = 300  # 5 minutes
    
    async def add_ip(
        self,
        ip_address: str,
        description: str,
        is_global: bool = False,
        agency_id: Optional[str] = None,
        user_id: Optional[str] = None,
        allowed_endpoints: Optional[List[str]] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        created_by: str = None,
        max_requests_per_hour: int = 1000
    ) -> IPWhitelist:
        """Add IP to whitelist"""
        # Validate IP address or CIDR
        try:
            ipaddress.ip_network(ip_address, strict=False)
        except ValueError:
            raise ValueError(f"Invalid IP address or CIDR: {ip_address}")
        
        whitelist_entry = IPWhitelist(
            ip_address=ip_address,
            description=description,
            is_global=is_global,
            agency_id=agency_id,
            user_id=user_id,
            allowed_endpoints=allowed_endpoints or [],
            valid_from=valid_from,
            valid_until=valid_until,
            created_by=created_by,
            max_requests_per_hour=max_requests_per_hour
        )
        
        self.db.add(whitelist_entry)
        await self.db.commit()
        
        # Clear cache
        await self._clear_cache()
        
        logger.info(f"Added IP {ip_address} to whitelist")
        return whitelist_entry
    
    async def remove_ip(self, ip_address: str) -> bool:
        """Remove IP from whitelist"""
        result = await self.db.execute(
            select(IPWhitelist).where(IPWhitelist.ip_address == ip_address)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            entry.is_active = False
            await self.db.commit()
            await self._clear_cache()
            logger.info(f"Removed IP {ip_address} from whitelist")
            return True
        
        return False
    
    async def is_ip_whitelisted(
        self,
        ip_address: str,
        endpoint: str,
        agency_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if IP is whitelisted for endpoint"""
        # Check cache first
        cache_key = f"ip_whitelist:{ip_address}:{endpoint}"
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return cached == "1"
        
        # Query database
        now = datetime.utcnow()
        conditions = [
            IPWhitelist.is_active == True,
            or_(
                IPWhitelist.valid_from == None,
                IPWhitelist.valid_from <= now
            ),
            or_(
                IPWhitelist.valid_until == None,
                IPWhitelist.valid_until >= now
            )
        ]
        
        # Check global, agency, and user specific entries
        scope_conditions = [IPWhitelist.is_global == True]
        if agency_id:
            scope_conditions.append(IPWhitelist.agency_id == agency_id)
        if user_id:
            scope_conditions.append(IPWhitelist.user_id == user_id)
        
        conditions.append(or_(*scope_conditions))
        
        result = await self.db.execute(
            select(IPWhitelist).where(and_(*conditions))
        )
        entries = result.scalars().all()
        
        # Check each entry
        for entry in entries:
            if self._ip_matches(ip_address, entry.ip_address):
                # Check endpoint restrictions
                if not entry.allowed_endpoints or any(
                    endpoint.startswith(pattern) for pattern in entry.allowed_endpoints
                ):
                    # Cache the result
                    await redis_client.setex(cache_key, self._cache_ttl, "1")
                    return True
        
        # Cache negative result
        await redis_client.setex(cache_key, self._cache_ttl, "0")
        return False
    
    def _ip_matches(self, ip: str, whitelist_entry: str) -> bool:
        """Check if IP matches whitelist entry (supports CIDR)"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            network = ipaddress.ip_network(whitelist_entry, strict=False)
            return ip_obj in network
        except ValueError:
            return False
    
    async def get_whitelisted_ips(
        self,
        agency_id: Optional[str] = None,
        user_id: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[IPWhitelist]:
        """Get all whitelisted IPs"""
        conditions = []
        
        if not include_inactive:
            conditions.append(IPWhitelist.is_active == True)
        
        if agency_id:
            conditions.append(
                or_(
                    IPWhitelist.is_global == True,
                    IPWhitelist.agency_id == agency_id
                )
            )
        
        if user_id:
            conditions.append(
                or_(
                    IPWhitelist.is_global == True,
                    IPWhitelist.user_id == user_id
                )
            )
        
        query = select(IPWhitelist)
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def check_rate_limit(self, ip_address: str, entry: IPWhitelist) -> bool:
        """Check if IP has exceeded rate limit"""
        key = f"ip_rate_limit:{ip_address}"
        current = await redis_client.incr(key)
        
        if current == 1:
            await redis_client.expire(key, 3600)  # 1 hour
        
        return current <= entry.max_requests_per_hour
    
    async def _clear_cache(self):
        """Clear IP whitelist cache"""
        pattern = "ip_whitelist:*"
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern)
            if keys:
                await redis_client.delete(*keys)
            if cursor == 0:
                break


class IPWhitelistMiddleware:
    """Middleware for IP whitelisting on admin endpoints"""
    
    def __init__(self, admin_paths: List[str]):
        self.admin_paths = admin_paths
    
    async def __call__(self, request: Request, call_next):
        """Check IP whitelist for admin endpoints"""
        # Check if path requires whitelisting
        requires_whitelist = any(
            request.url.path.startswith(path)
            for path in self.admin_paths
        )
        
        if requires_whitelist:
            # Get client IP
            client_ip = request.client.host if request.client else None
            if request.headers.get("X-Forwarded-For"):
                client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
            
            if not client_ip:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Could not determine client IP"
                )
            
            # Check whitelist
            from core.database import get_db
            async for db in get_db():
                service = IPWhitelistService(db)
                
                # Get user info from request if available
                user = getattr(request.state, "user", None)
                agency_id = user.agency_id if user else None
                user_id = user.id if user else None
                
                is_whitelisted = await service.is_ip_whitelisted(
                    client_ip,
                    request.url.path,
                    agency_id=str(agency_id) if agency_id else None,
                    user_id=str(user_id) if user_id else None
                )
                
                if not is_whitelisted:
                    logger.warning(
                        f"Blocked admin access from non-whitelisted IP: {client_ip} "
                        f"to {request.url.path}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: IP not whitelisted"
                    )
                
                break
        
        # Process request
        response = await call_next(request)
        return response


# Dependency for checking IP whitelist in specific endpoints
async def check_ip_whitelist(
    request: Request,
    db: AsyncSession,
    endpoint_pattern: Optional[str] = None
):
    """
    Dependency to check IP whitelist
    
    Usage:
        @router.get("/admin/sensitive-data")
        async def get_sensitive_data(
            _: None = Depends(check_ip_whitelist),
            current_user: User = Depends(get_current_user)
        ):
            ...
    """
    # Get client IP
    client_ip = request.client.host if request.client else None
    if request.headers.get("X-Forwarded-For"):
        client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
    
    if not client_ip:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not determine client IP"
        )
    
    # Get user context
    user = getattr(request.state, "user", None)
    
    service = IPWhitelistService(db)
    is_whitelisted = await service.is_ip_whitelisted(
        client_ip,
        endpoint_pattern or request.url.path,
        agency_id=str(user.agency_id) if user and user.agency_id else None,
        user_id=str(user.id) if user else None
    )
    
    if not is_whitelisted:
        logger.warning(
            f"Blocked access from non-whitelisted IP: {client_ip} "
            f"to {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: IP not whitelisted for this endpoint"
        )


# Utility functions
def is_private_ip(ip: str) -> bool:
    """Check if IP is private/internal"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        return False


def get_ip_info(ip: str) -> Dict[str, Any]:
    """Get information about an IP address"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return {
            "ip": str(ip_obj),
            "version": ip_obj.version,
            "is_private": ip_obj.is_private,
            "is_global": ip_obj.is_global,
            "is_loopback": ip_obj.is_loopback,
            "is_multicast": ip_obj.is_multicast
        }
    except ValueError:
        return {"ip": ip, "error": "Invalid IP address"}