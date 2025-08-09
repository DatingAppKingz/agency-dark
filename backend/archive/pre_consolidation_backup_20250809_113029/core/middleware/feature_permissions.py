"""
Feature permission middleware for enforcing feature-specific access control.

This middleware checks feature permissions on incoming requests and applies
appropriate data filtering based on user permissions.
"""
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re
import json

from core.database import AsyncSessionLocal
from core.security.dependencies import get_user_from_token
from models.feature_permission import FeatureType
from core.security.feature_permissions.service import feature_permission_service
from core.logger import get_logger
from core.geo import get_country_from_ip


logger = get_logger(__name__)


class FeaturePermissionMiddleware(BaseHTTPMiddleware):
    """Middleware for checking feature permissions on requests."""
    
    # Route patterns mapped to feature types and actions
    ROUTE_PATTERNS = [
        # Reports
        (r"/api/v1/reports/templates/(\w+)/execute", FeatureType.REPORTS, "view_report"),
        (r"/api/v1/reports/templates", FeatureType.REPORTS, "create_template"),
        (r"/api/v1/reports/execute", FeatureType.REPORTS, "view_report"),
        (r"/api/v1/reports/schedule", FeatureType.REPORTS, "schedule_report"),
        
        # Exports
        (r"/api/v1/exports/data", FeatureType.EXPORTS, "export_data"),
        (r"/api/v1/exports/reports/(\w+)", FeatureType.EXPORTS, "export_data"),
        (r"/api/v1/exports/analytics", FeatureType.EXPORTS, "export_data"),
        (r"/api/v1/exports/messages", FeatureType.EXPORTS, "export_data"),
        
        # Analytics
        (r"/api/v1/analytics/dashboard", FeatureType.ANALYTICS, "view_analytics"),
        (r"/api/v1/analytics/metrics", FeatureType.ANALYTICS, "view_analytics"),
        (r"/api/v1/analytics/custom-metrics", FeatureType.ANALYTICS, "create_custom_metric"),
        
        # Messaging
        (r"/api/v1/messages/send", FeatureType.MESSAGING, "send_message"),
        (r"/api/v1/messages/bulk", FeatureType.MESSAGING, "send_bulk"),
        (r"/api/v1/messages/templates", FeatureType.MESSAGING, "edit_template"),
        (r"/api/v1/messages/schedule", FeatureType.MESSAGING, "send_message"),
        (r"/api/v1/messages/history", FeatureType.MESSAGING, "view_history"),
        (r"/api/v1/messages/export", FeatureType.MESSAGING, "export_chats"),
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check feature permissions before processing request."""
        # Skip for non-API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Skip for auth and health endpoints
        if any(request.url.path.startswith(p) for p in ["/api/v1/auth", "/api/v1/health", "/api/docs"]):
            return await call_next(request)
        
        # Match route pattern
        feature_type, action = self._match_route(request.url.path, request.method)
        
        if not feature_type:
            # No specific feature permission required
            return await call_next(request)
        
        try:
            # Get user from request
            user = await self._get_user(request)
            if not user:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"}
                )
            
            # Get request context
            context = await self._build_request_context(request, user)
            
            # Check permission
            async with get_db_context() as db:
                allowed, reason = await feature_permission_service.check_feature_permission(
                    db=db,
                    user=user,
                    feature_type=feature_type,
                    action=action,
                    resource_id=context.get("resource_id"),
                    request_context=context
                )
            
            if not allowed:
                logger.warning(
                    f"Feature permission denied for user {user.id}: {reason}",
                    extra={
                        "user_id": str(user.id),
                        "feature_type": feature_type.value,
                        "action": action,
                        "reason": reason
                    }
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"Permission denied: {reason}"}
                )
            
            # Add permission context to request state
            request.state.feature_permission_context = {
                "feature_type": feature_type,
                "action": action,
                "user_id": str(user.id)
            }
            
        except Exception as e:
            logger.error(f"Error in feature permission middleware: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Permission check failed"}
            )
        
        # Process request
        response = await call_next(request)
        
        # Add permission headers to response
        if hasattr(request.state, "feature_permission_context"):
            response.headers["X-Feature-Type"] = feature_type.value
            response.headers["X-Feature-Action"] = action
        
        return response
    
    def _match_route(self, path: str, method: str) -> tuple[Optional[FeatureType], Optional[str]]:
        """Match request path to feature type and action."""
        for pattern, feature_type, action in self.ROUTE_PATTERNS:
            if re.match(pattern, path):
                # Adjust action based on HTTP method
                if method == "DELETE" and action == "view_report":
                    action = "delete_report"
                elif method == "PUT" and action == "view_report":
                    action = "update_report"
                
                return feature_type, action
        
        return None, None
    
    async def _get_user(self, request: Request):
        """Get user from request."""
        # Try to get from request state first
        if hasattr(request.state, "user"):
            return request.state.user
        
        # Try to get from authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                async with AsyncSessionLocal() as db:
                    user = await get_user_from_token(token, db)
                    return user
            except Exception as e:
                logger.error(f"Error getting user from token: {e}")
        
        return None
    
    async def _build_request_context(
        self,
        request: Request,
        user: Any
    ) -> Dict[str, Any]:
        """Build request context for permission checking."""
        context = {
            "method": request.method,
            "path": request.url.path,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent"),
            "request_id": request.headers.get("X-Request-ID"),
            "session_id": request.headers.get("X-Session-ID")
        }
        
        # Add country code if available
        if context["ip_address"]:
            context["country_code"] = await get_country_from_ip(context["ip_address"])
        
        # Extract resource ID from path
        path_parts = request.url.path.split("/")
        if len(path_parts) > 4 and path_parts[4] not in ["send", "bulk", "templates", "schedule", "export"]:
            context["resource_id"] = path_parts[4]
        
        # Add MFA status if available
        if hasattr(user, "last_mfa_at"):
            # Check if MFA was used recently (within session timeout)
            from datetime import datetime, timedelta
            if user.last_mfa_at and (datetime.utcnow() - user.last_mfa_at) < timedelta(hours=8):
                context["mfa_verified"] = True
        
        # Try to parse request body for additional context
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Store body for later use by endpoint
                body = await request.body()
                request._body = body
                
                if body:
                    data = json.loads(body)
                    
                    # Extract relevant fields based on feature type
                    if "report_type" in data:
                        context["report_type"] = data["report_type"]
                    if "format" in data:
                        context["format"] = data["format"]
                    if "metrics" in data:
                        context["metrics"] = data["metrics"]
                    if "recipient_count" in data:
                        context["recipient_count"] = data["recipient_count"]
                    if "date_range" in data:
                        context["date_range"] = data["date_range"]
                    
            except Exception as e:
                logger.debug(f"Could not parse request body: {e}")
        
        return context


class DataFilteringMiddleware(BaseHTTPMiddleware):
    """Middleware for applying data filtering based on permissions."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply data filtering to responses based on permissions."""
        response = await call_next(request)
        
        # Only filter successful API responses
        if (
            not request.url.path.startswith("/api/") or
            response.status_code >= 400 or
            not hasattr(request.state, "user")
        ):
            return response
        
        # Check if response needs filtering
        feature_context = getattr(request.state, "feature_permission_context", None)
        if not feature_context:
            return response
        
        # Apply filtering based on feature type
        if feature_context["feature_type"] == FeatureType.ANALYTICS:
            response = await self._filter_analytics_response(request, response)
        elif feature_context["feature_type"] == FeatureType.REPORTS:
            response = await self._filter_report_response(request, response)
        
        return response
    
    async def _filter_analytics_response(self, request: Request, response: Response) -> Response:
        """Filter analytics data based on user permissions."""
        # This would parse response body and filter data
        # For now, just pass through
        return response
    
    async def _filter_report_response(self, request: Request, response: Response) -> Response:
        """Filter report data based on user permissions."""
        # This would parse response body and filter sensitive fields
        # For now, just pass through
        return response