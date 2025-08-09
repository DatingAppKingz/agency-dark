from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        excluded_paths = ["/", "/health", "/api/docs", "/api/redoc", "/openapi.json"]
        
        if request.url.path in excluded_paths:
            return await call_next(request)
        
        if request.url.path.startswith("/api/v1/auth"):
            return await call_next(request)
        
        tenant_id = None
        
        if hasattr(request.state, "user") and request.state.user:
            tenant_id = getattr(request.state.user, "agency_id", None)
        
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            tenant_id = tenant_header
        
        if tenant_id:
            request.state.tenant_id = tenant_id
            logger.debug(f"Processing request for tenant: {tenant_id}")
        
        response = await call_next(request)
        
        if hasattr(request.state, "tenant_id"):
            response.headers["X-Tenant-ID"] = request.state.tenant_id
        
        return response