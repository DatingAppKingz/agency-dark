"""
Fraud detection middleware.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import json
import logging
from typing import Optional

from core.fraud_detection.fraud_detector import fraud_detector
from core.dependencies import get_current_user_optional
from core.database import get_db

logger = logging.getLogger(__name__)


class FraudDetectionMiddleware(BaseHTTPMiddleware):
    """Middleware for fraud detection on sensitive endpoints."""
    
    # Endpoints to monitor for fraud
    MONITORED_ENDPOINTS = [
        "/api/v1/transactions",
        "/api/v1/payouts",
        "/api/v1/payments",
        "/api/v1/withdrawals",
        "/api/v1/transfers"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request with fraud detection."""
        # Only check monitored endpoints
        if not any(request.url.path.startswith(ep) for ep in self.MONITORED_ENDPOINTS):
            return await call_next(request)
        
        # Only check POST/PUT requests
        if request.method not in ["POST", "PUT"]:
            return await call_next(request)
        
        try:
            # Get user info
            user = await self._get_user(request)
            if not user:
                return await call_next(request)
            
            # Get request data
            body = await self._get_request_body(request)
            if not body:
                return await call_next(request)
            
            # Parse JSON body
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return await call_next(request)
            
            # Get IP address
            ip_address = self._get_client_ip(request)
            
            # Perform fraud check
            async for db in get_db():
                fraud_result = await fraud_detector.check_transaction(
                    transaction_data=data,
                    user_id=str(user.id),
                    ip_address=ip_address,
                    session=db
                )
                break
            
            # Handle fraud detection result
            if not fraud_result["allowed"]:
                logger.warning(
                    f"Fraud detected for user {user.id}: "
                    f"Risk level: {fraud_result['risk_level']}, "
                    f"Reasons: {fraud_result['reasons']}"
                )
                
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Transaction blocked due to security concerns",
                        "risk_level": fraud_result["risk_level"].value,
                        "action": fraud_result["action"].value
                    }
                )
            
            # Add fraud check headers
            response = await call_next(request)
            response.headers["X-Fraud-Score"] = str(fraud_result["risk_score"])
            response.headers["X-Risk-Level"] = fraud_result["risk_level"].value
            
            return response
            
        except Exception as e:
            logger.error(f"Fraud detection error: {str(e)}")
            # On error, allow request but log
            return await call_next(request)
    
    async def _get_user(self, request: Request):
        """Get current user from request."""
        try:
            # Try to get user from auth
            user = await get_current_user_optional(request)
            return user
        except:
            return None
    
    async def _get_request_body(self, request: Request) -> Optional[bytes]:
        """Get request body safely."""
        try:
            body = await request.body()
            
            # Reconstruct request for downstream
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
            return body
        except:
            return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        # Check for forwarded IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check for real IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        if request.client:
            return request.client.host
        
        return "unknown"


def fraud_check(risk_threshold: str = "medium"):
    """
    Decorator for fraud detection on specific endpoints.
    
    Args:
        risk_threshold: Minimum risk level to block ("low", "medium", "high", "critical")
    """
    from functools import wraps
    from core.fraud_detection.models import RiskLevel
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")
            
            if not request:
                # No request found, proceed without check
                return await func(*args, **kwargs)
            
            # Get current user
            try:
                from core.dependencies import get_current_user
                user = await get_current_user(request)
            except:
                # No user, proceed
                return await func(*args, **kwargs)
            
            # Get request data
            try:
                body = await request.body()
                data = json.loads(body) if body else {}
                
                # Reconstruct request
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except:
                data = {}
            
            # Perform fraud check
            ip_address = request.client.host if request.client else "unknown"
            
            async for db in get_db():
                fraud_result = await fraud_detector.check_transaction(
                    transaction_data=data,
                    user_id=str(user.id),
                    ip_address=ip_address,
                    session=db
                )
                break
            
            # Check against threshold
            threshold_map = {
                "low": RiskLevel.LOW,
                "medium": RiskLevel.MEDIUM,
                "high": RiskLevel.HIGH,
                "critical": RiskLevel.CRITICAL
            }
            
            threshold_level = threshold_map.get(risk_threshold, RiskLevel.MEDIUM)
            risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            
            if not fraud_result["allowed"] or (
                risk_levels.index(fraud_result["risk_level"]) >= 
                risk_levels.index(threshold_level)
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Transaction blocked due to security concerns"
                )
            
            # Add fraud info to request state
            request.state.fraud_check = fraud_result
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator