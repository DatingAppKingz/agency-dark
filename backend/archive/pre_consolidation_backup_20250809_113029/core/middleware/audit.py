"""
Audit logging middleware for automatic request/response tracking.
"""
import time
import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import asyncio

from core.audit.audit_service import audit_service
from models.audit_log import AuditAction, AuditSeverity
from models.user import User
from models.platform_api_key import PlatformAPIKey
from core.database import get_db
from core.logger import get_logger

logger = get_logger(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic audit logging of all requests."""
    
    # Map HTTP methods and paths to audit actions
    ACTION_MAPPING = {
        ("POST", "/api/v1/auth/login"): AuditAction.LOGIN,
        ("POST", "/api/v1/auth/logout"): AuditAction.LOGOUT,
        ("POST", "/api/v1/users"): AuditAction.USER_CREATED,
        ("PUT", "/api/v1/users"): AuditAction.USER_UPDATED,
        ("DELETE", "/api/v1/users"): AuditAction.USER_DELETED,
        ("POST", "/api/v1/models"): AuditAction.MODEL_CREATED,
        ("PUT", "/api/v1/models"): AuditAction.MODEL_UPDATED,
        ("DELETE", "/api/v1/models"): AuditAction.MODEL_DELETED,
        ("POST", "/api/v1/transactions"): AuditAction.TRANSACTION_CREATED,
        ("POST", "/api/v1/messages"): AuditAction.MESSAGE_SENT,
        ("GET", "/api/v1/analytics"): AuditAction.ANALYTICS_VIEWED,
        ("GET", "/api/v1/reports"): AuditAction.REPORT_GENERATED,
        ("POST", "/api/v1/export"): AuditAction.DATA_EXPORTED,
        ("POST", "/api/v1/platform-keys"): AuditAction.API_KEY_CREATED,
    }
    
    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {
        "/health",
        "/metrics",
        "/api/v1/audit/search",  # Don't log audit log searches
        "/favicon.ico",
        "/docs",
        "/redoc",
        "/openapi.json"
    }
    
    # Sensitive fields to exclude from logging
    SENSITIVE_FIELDS = {
        "password", "token", "secret", "api_key", "credit_card",
        "ssn", "bank_account", "private_key", "refresh_token"
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log audit trail."""
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Extract request information
        request_info = await self._extract_request_info(request)
        
        # Process request
        response = None
        error_info = None
        
        try:
            response = await call_next(request)
            
            # Extract response information
            response_info = await self._extract_response_info(response)
            
        except Exception as e:
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            raise
        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log audit trail
            await self._log_audit(
                request=request,
                request_info=request_info,
                response=response,
                response_info=response_info if response else None,
                error_info=error_info,
                duration_ms=duration_ms
            )
        
        return response
    
    async def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extract information from request."""
        # Get body if it's not a file upload
        body = None
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body_bytes = await request.body()
                # Store body for later use
                request._body = body_bytes
                if body_bytes:
                    body = json.loads(body_bytes)
                    # Remove sensitive fields
                    body = self._sanitize_data(body)
            except:
                pass
        
        return {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": self._sanitize_headers(dict(request.headers)),
            "body": body,
            "content_type": request.headers.get("content-type"),
            "client_host": request.client.host if request.client else None
        }
    
    async def _extract_response_info(self, response: Response) -> Dict[str, Any]:
        """Extract information from response."""
        response_info = {
            "status_code": response.status_code,
            "headers": dict(response.headers)
        }
        
        # Try to get response body for small responses
        if hasattr(response, "body") and len(response.body) < 10000:  # 10KB limit
            try:
                body = json.loads(response.body)
                response_info["body"] = self._sanitize_data(body)
            except:
                pass
        
        return response_info
    
    def _sanitize_data(self, data: Any) -> Any:
        """Remove sensitive fields from data."""
        if isinstance(data, dict):
            return {
                k: "***REDACTED***" if k.lower() in self.SENSITIVE_FIELDS else self._sanitize_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive headers."""
        sensitive_headers = {"authorization", "x-api-key", "cookie", "set-cookie"}
        return {
            k: "***REDACTED***" if k.lower() in sensitive_headers else v
            for k, v in headers.items()
        }
    
    async def _log_audit(
        self,
        request: Request,
        request_info: Dict[str, Any],
        response: Optional[Response],
        response_info: Optional[Dict[str, Any]],
        error_info: Optional[Dict[str, Any]],
        duration_ms: int
    ):
        """Log the audit trail."""
        try:
            # Get database session
            async for db in get_db():
                # Determine action
                action = self._determine_action(
                    method=request_info["method"],
                    path=request_info["path"],
                    status_code=response_info["status_code"] if response_info else 500
                )
                
                if not action:
                    return
                
                # Get user from request state
                user = getattr(request.state, "user", None)
                api_key = getattr(request.state, "api_key", None)
                
                # Determine severity
                severity = self._determine_severity(
                    status_code=response_info["status_code"] if response_info else 500,
                    error_info=error_info
                )
                
                # Extract resource information
                resource_info = self._extract_resource_info(request_info["path"])
                
                # Build metadata
                metadata = {
                    "request": {
                        "method": request_info["method"],
                        "path": request_info["path"],
                        "query": request_info["query_params"],
                        "body_size": len(json.dumps(request_info["body"])) if request_info["body"] else 0
                    },
                    "response": {
                        "status_code": response_info["status_code"] if response_info else None,
                        "body_size": len(json.dumps(response_info.get("body", {}))) if response_info and "body" in response_info else 0
                    } if response_info else None,
                    "error": error_info
                }
                
                # Log audit
                await audit_service.log(
                    db=db,
                    action=action,
                    user=user,
                    user_id=str(user.id) if user else None,
                    agency_id=str(user.agency_id) if user and user.agency_id else None,
                    resource_type=resource_info["type"],
                    resource_id=resource_info["id"],
                    description=f"{request_info['method']} {request_info['path']}",
                    metadata=metadata,
                    ip_address=request_info["client_host"],
                    user_agent=request_info["headers"].get("user-agent"),
                    session_id=request_info["headers"].get("x-session-id"),
                    request_id=request_info["headers"].get("x-request-id"),
                    severity=severity,
                    duration_ms=duration_ms,
                    api_key=api_key
                )
                
                break
                
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
    
    def _determine_action(self, method: str, path: str, status_code: int) -> Optional[AuditAction]:
        """Determine audit action from request."""
        # Check exact mapping
        key = (method, path)
        if key in self.ACTION_MAPPING:
            return self.ACTION_MAPPING[key]
        
        # Check pattern matching
        for pattern_key, action in self.ACTION_MAPPING.items():
            pattern_method, pattern_path = pattern_key
            if method == pattern_method and path.startswith(pattern_path):
                return action
        
        # Default actions based on method
        if status_code >= 400:
            return None  # Don't log client errors as actions
        
        return None
    
    def _determine_severity(self, status_code: int, error_info: Optional[Dict[str, Any]]) -> AuditSeverity:
        """Determine severity based on response."""
        if error_info:
            return AuditSeverity.ERROR
        elif status_code >= 500:
            return AuditSeverity.ERROR
        elif status_code >= 400:
            return AuditSeverity.WARNING
        else:
            return AuditSeverity.INFO
    
    def _extract_resource_info(self, path: str) -> Dict[str, Optional[str]]:
        """Extract resource type and ID from path."""
        parts = path.strip("/").split("/")
        
        resource_type = None
        resource_id = None
        
        # Pattern: /api/v1/{resource_type}/{resource_id}
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
            resource_type = parts[2]
            if len(parts) >= 4 and parts[3] not in ["search", "export", "import"]:
                resource_id = parts[3]
        
        return {
            "type": resource_type,
            "id": resource_id
        }


class DetailedAuditLoggingMiddleware(AuditLoggingMiddleware):
    """Enhanced audit logging with request/response body capture."""
    
    async def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extract detailed request information including body."""
        info = await super()._extract_request_info(request)
        
        # Add more details
        info["timestamp"] = datetime.utcnow().isoformat()
        info["protocol"] = request.url.scheme
        info["full_path"] = str(request.url)
        
        return info
    
    async def _extract_response_info(self, response: Response) -> Dict[str, Any]:
        """Extract detailed response information."""
        info = await super()._extract_response_info(response)
        
        # Add timing headers if available
        if "x-process-time" in response.headers:
            info["process_time"] = response.headers["x-process-time"]
        
        return info


class ComplianceAuditMiddleware(BaseHTTPMiddleware):
    """Specialized middleware for compliance-required audit logging."""
    
    # Actions that require compliance logging
    COMPLIANCE_ACTIONS = {
        "/api/v1/users/*/delete": "GDPR_USER_DELETION",
        "/api/v1/users/*/export": "GDPR_DATA_EXPORT",
        "/api/v1/financial/*": "FINANCIAL_ACCESS",
        "/api/v1/reports/compliance/*": "COMPLIANCE_REPORT"
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with compliance logging."""
        # Check if this requires compliance logging
        compliance_tag = self._get_compliance_tag(request.url.path)
        
        if not compliance_tag:
            return await call_next(request)
        
        # Process with enhanced logging
        response = await call_next(request)
        
        # Log for compliance
        await self._log_compliance_action(request, response, compliance_tag)
        
        return response
    
    def _get_compliance_tag(self, path: str) -> Optional[str]:
        """Check if path requires compliance logging."""
        for pattern, tag in self.COMPLIANCE_ACTIONS.items():
            if self._path_matches(path, pattern):
                return tag
        return None
    
    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern with wildcards."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)
    
    async def _log_compliance_action(self, request: Request, response: Response, tag: str):
        """Log action for compliance."""
        # Implementation depends on your compliance requirements
        logger.info(f"Compliance action logged: {tag} for {request.url.path}")