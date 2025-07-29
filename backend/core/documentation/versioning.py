"""
API versioning strategy and implementation
"""
from typing import Optional, Callable, Any, Dict, Type
from datetime import datetime
from enum import Enum
from functools import wraps
import re

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.responses import Response

from core.logging import logger


class APIVersion(Enum):
    """Supported API versions"""
    V1 = "v1"
    V2 = "v2"
    V3 = "v3"
    
    @classmethod
    def from_string(cls, version: str) -> Optional["APIVersion"]:
        """Convert string to APIVersion"""
        try:
            return cls(version.lower())
        except ValueError:
            return None
    
    @property
    def deprecation_date(self) -> Optional[datetime]:
        """Get deprecation date for version"""
        deprecation_dates = {
            APIVersion.V1: datetime(2025, 12, 31),  # V1 deprecated end of 2025
            APIVersion.V2: None,  # V2 not deprecated
            APIVersion.V3: None   # V3 not deprecated
        }
        return deprecation_dates.get(self)
    
    @property
    def is_deprecated(self) -> bool:
        """Check if version is deprecated"""
        return self.deprecation_date is not None and datetime.now() > self.deprecation_date
    
    @property
    def sunset_date(self) -> Optional[datetime]:
        """Get sunset date (when version will be removed)"""
        if self.deprecation_date:
            # Sunset 6 months after deprecation
            return datetime(
                self.deprecation_date.year + (self.deprecation_date.month + 6) // 12,
                (self.deprecation_date.month + 6) % 12 or 12,
                self.deprecation_date.day
            )
        return None


class VersionedRoute(APIRoute):
    """
    Custom route class for API versioning
    """
    
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        
        async def versioned_route_handler(request: Request) -> Response:
            # Extract version from path
            version = get_api_version(request)
            
            # Add version to request state
            request.state.api_version = version
            
            # Check if version is deprecated
            if version and version.is_deprecated:
                # Add deprecation headers
                response = await original_route_handler(request)
                response.headers["X-API-Deprecation"] = "true"
                response.headers["X-API-Deprecation-Date"] = version.deprecation_date.isoformat()
                if version.sunset_date:
                    response.headers["X-API-Sunset-Date"] = version.sunset_date.isoformat()
                return response
            
            return await original_route_handler(request)
        
        return versioned_route_handler


class VersionConfig(BaseModel):
    """API version configuration"""
    min_version: APIVersion = APIVersion.V1
    max_version: APIVersion = APIVersion.V3
    default_version: APIVersion = APIVersion.V1
    header_versioning: bool = True  # Support version in headers
    url_versioning: bool = True     # Support version in URL
    query_versioning: bool = False  # Support version in query params


def get_api_version(request: Request) -> Optional[APIVersion]:
    """
    Extract API version from request
    
    Priority:
    1. URL path (/api/v1/...)
    2. Header (API-Version: v1)
    3. Query parameter (?version=v1)
    """
    # Check URL path
    path_match = re.match(r"/api/(v\d+)/", request.url.path)
    if path_match:
        version_str = path_match.group(1)
        version = APIVersion.from_string(version_str)
        if version:
            return version
    
    # Check header
    api_version_header = request.headers.get("API-Version")
    if api_version_header:
        version = APIVersion.from_string(api_version_header)
        if version:
            return version
    
    # Check query parameter
    version_param = request.query_params.get("version")
    if version_param:
        version = APIVersion.from_string(version_param)
        if version:
            return version
    
    # Return default
    return APIVersion.V1


def version_route(
    min_version: APIVersion = APIVersion.V1,
    max_version: Optional[APIVersion] = None,
    deprecated_in: Optional[APIVersion] = None
):
    """
    Decorator for versioning individual routes
    
    Args:
        min_version: Minimum API version that supports this route
        max_version: Maximum API version that supports this route
        deprecated_in: Version where this route is deprecated
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            version = get_api_version(request)
            
            # Check version constraints
            if version and version.value < min_version.value:
                raise HTTPException(
                    status_code=404,
                    detail=f"This endpoint is not available in API {version.value}. "
                           f"Minimum required version: {min_version.value}"
                )
            
            if max_version and version and version.value > max_version.value:
                raise HTTPException(
                    status_code=404,
                    detail=f"This endpoint is no longer available in API {version.value}. "
                           f"Maximum supported version: {max_version.value}"
                )
            
            # Add deprecation warning if applicable
            if deprecated_in and version and version.value >= deprecated_in.value:
                logger.warning(
                    f"Deprecated endpoint accessed: {request.url.path} "
                    f"(deprecated in {deprecated_in.value})"
                )
            
            return await func(request, *args, **kwargs)
        
        # Store version metadata
        wrapper._min_version = min_version
        wrapper._max_version = max_version
        wrapper._deprecated_in = deprecated_in
        
        return wrapper
    return decorator


class VersionedAPIRouter(APIRouter):
    """
    Router with built-in versioning support
    """
    
    def __init__(
        self,
        version: APIVersion,
        *args,
        route_class: Type[APIRoute] = VersionedRoute,
        **kwargs
    ):
        self.version = version
        
        # Add version to prefix if not already present
        prefix = kwargs.get("prefix", "")
        if not prefix.startswith(f"/api/{version.value}"):
            kwargs["prefix"] = f"/api/{version.value}{prefix}"
        
        super().__init__(*args, route_class=route_class, **kwargs)
    
    def include_router(
        self,
        router: APIRouter,
        *args,
        **kwargs
    ) -> None:
        """Include a router with version prefix"""
        # Ensure nested routers maintain version prefix
        if hasattr(router, "version") and router.version != self.version:
            raise ValueError(
                f"Cannot include router with version {router.version} "
                f"in router with version {self.version}"
            )
        
        super().include_router(router, *args, **kwargs)


def create_versioned_app(versions: Dict[APIVersion, APIRouter]) -> APIRouter:
    """
    Create a main router that includes all versioned routers
    
    Args:
        versions: Dictionary mapping API versions to their routers
        
    Returns:
        Main router with all versions included
    """
    main_router = APIRouter()
    
    for version, router in versions.items():
        # Ensure router has correct prefix
        if not hasattr(router, "version"):
            router = VersionedAPIRouter(version=version, router=router)
        
        main_router.include_router(router)
        
        # Add version discovery endpoint
        @main_router.get(f"/api/{version.value}")
        async def version_info(version: APIVersion = version):
            return {
                "version": version.value,
                "deprecated": version.is_deprecated,
                "deprecation_date": version.deprecation_date.isoformat() if version.deprecation_date else None,
                "sunset_date": version.sunset_date.isoformat() if version.sunset_date else None,
                "links": {
                    "documentation": f"https://docs.agency.com/api/{version.value}",
                    "changelog": f"https://docs.agency.com/api/{version.value}/changelog"
                }
            }
    
    # Add version discovery endpoint
    @main_router.get("/api/versions")
    async def list_versions():
        return {
            "versions": [
                {
                    "version": v.value,
                    "deprecated": v.is_deprecated,
                    "deprecation_date": v.deprecation_date.isoformat() if v.deprecation_date else None,
                    "sunset_date": v.sunset_date.isoformat() if v.sunset_date else None
                }
                for v in APIVersion
            ],
            "current": APIVersion.V1.value,
            "recommended": APIVersion.V1.value
        }
    
    return main_router


class VersionTransformer:
    """
    Transform requests/responses between API versions
    """
    
    def __init__(self):
        self.request_transformers: Dict[tuple, Callable] = {}
        self.response_transformers: Dict[tuple, Callable] = {}
    
    def register_request_transformer(
        self,
        from_version: APIVersion,
        to_version: APIVersion,
        transformer: Callable
    ):
        """Register a request transformer between versions"""
        self.request_transformers[(from_version, to_version)] = transformer
    
    def register_response_transformer(
        self,
        from_version: APIVersion,
        to_version: APIVersion,
        transformer: Callable
    ):
        """Register a response transformer between versions"""
        self.response_transformers[(from_version, to_version)] = transformer
    
    async def transform_request(
        self,
        request_data: Dict[str, Any],
        from_version: APIVersion,
        to_version: APIVersion
    ) -> Dict[str, Any]:
        """Transform request data between versions"""
        transformer = self.request_transformers.get((from_version, to_version))
        if transformer:
            return await transformer(request_data)
        return request_data
    
    async def transform_response(
        self,
        response_data: Dict[str, Any],
        from_version: APIVersion,
        to_version: APIVersion
    ) -> Dict[str, Any]:
        """Transform response data between versions"""
        transformer = self.response_transformers.get((from_version, to_version))
        if transformer:
            return await transformer(response_data)
        return response_data


# Global version transformer instance
version_transformer = VersionTransformer()


# Example transformers for common version migrations
async def transform_v1_to_v2_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Example: Transform user data from v1 to v2 format"""
    # v2 splits name into first_name and last_name
    if "name" in data:
        parts = data["name"].split(" ", 1)
        data["first_name"] = parts[0]
        data["last_name"] = parts[1] if len(parts) > 1 else ""
        del data["name"]
    return data


async def transform_v2_to_v1_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Example: Transform user data from v2 to v1 format"""
    # v1 combines first_name and last_name into name
    if "first_name" in data or "last_name" in data:
        first = data.get("first_name", "")
        last = data.get("last_name", "")
        data["name"] = f"{first} {last}".strip()
        data.pop("first_name", None)
        data.pop("last_name", None)
    return data


# Register example transformers
version_transformer.register_request_transformer(APIVersion.V1, APIVersion.V2, transform_v1_to_v2_user)
version_transformer.register_response_transformer(APIVersion.V2, APIVersion.V1, transform_v2_to_v1_user)