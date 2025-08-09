"""
Advanced Fraud Detection Middleware

Integrates with the advanced fraud detection system to provide:
- Real-time fraud scoring
- Multiple detection strategies
- Automatic blocking for high-risk activities
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import json
from typing import Optional, Dict, Any

from core.security.fraud_detector import fraud_detector, FraudRiskLevel
from core.logging import get_logger

logger = get_logger(__name__)


class FraudDetectionMiddleware(BaseHTTPMiddleware):
    """Advanced fraud detection middleware for sensitive operations"""
    
    # Endpoints to monitor for fraud
    MONITORED_ENDPOINTS = [
        "/api/v1/financial",
        "/api/v1/transactions",
        "/api/v1/payments",
        "/api/v1/withdrawals",
        "/api/v1/transfers",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/reset-password",
        "/api/v1/api-keys",
        "/api/v1/bulk"
    ]
    
    # Action mapping for endpoints
    ACTION_MAPPING = {
        "/login": "login",
        "/register": "register",
        "/reset-password": "password_reset",
        "/withdrawals": "withdrawal",
        "/transfers": "transfer",
        "/api-keys": "api_key_create",
        "/bulk": "bulk_operation"
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request with advanced fraud detection"""
        
        # Check if endpoint should be monitored
        if not any(request.url.path.startswith(ep) for ep in self.MONITORED_ENDPOINTS):
            return await call_next(request)
        
        # Skip GET requests (except for certain auth endpoints)
        if request.method == "GET" and "/auth/" not in request.url.path:
            return await call_next(request)
        
        try:
            # Extract context information
            user_id = None
            if hasattr(request.state, "user") and request.state.user:
                user_id = request.state.user.get("user_id")
            
            # Get IP address
            ip_address = self._get_client_ip(request)
            
            # Determine action from endpoint
            action = self._get_action_from_endpoint(request.url.path)
            
            # Extract amount if present
            amount = None
            metadata = {
                "method": request.method,
                "endpoint": request.url.path,
                "user_agent": request.headers.get("User-Agent", ""),
                "device_fingerprint": request.headers.get("X-Device-Fingerprint")
            }
            
            # Get request body for POST/PUT
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await self._get_request_body(request)
                if body:
                    try:
                        data = json.loads(body)
                        amount = data.get("amount")
                        metadata["request_data"] = data
                    except json.JSONDecodeError:
                        pass
            
            # Perform fraud check
            fraud_score = await fraud_detector.check_fraud(
                user_id=user_id,
                ip_address=ip_address,
                action=action,
                amount=amount,
                metadata=metadata
            )
            
            # Log high-risk activities
            if fraud_score.risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]:
                logger.warning(
                    f"High fraud risk detected - User: {user_id}, "
                    f"IP: {ip_address}, Action: {action}, "
                    f"Score: {fraud_score.score}, Risk: {fraud_score.risk_level}"
                )
            
            # Block if necessary
            if fraud_score.block_transaction:
                logger.error(
                    f"Transaction blocked - User: {user_id}, "
                    f"Score: {fraud_score.score}, "
                    f"Indicators: {[i['type'] for i in fraud_score.indicators]}"
                )
                
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "security_check_failed",
                        "message": "This action has been blocked for security reasons",
                        "risk_level": fraud_score.risk_level.value,
                        "recommendations": fraud_score.recommendations[:2]  # Limit exposed recommendations
                    },
                    headers={
                        "X-Fraud-Score": str(int(fraud_score.score)),
                        "X-Risk-Level": fraud_score.risk_level.value
                    }
                )
            
            # Add fraud info to request state for downstream use
            request.state.fraud_score = fraud_score
            
            # Process request
            response = await call_next(request)
            
            # Add fraud headers to response
            response.headers["X-Fraud-Score"] = str(int(fraud_score.score))
            response.headers["X-Risk-Level"] = fraud_score.risk_level.value
            
            # Add verification requirement header if needed
            if fraud_score.require_verification:
                response.headers["X-Verification-Required"] = "true"
            
            return response
            
        except Exception as e:
            logger.error(f"Fraud detection error: {e}")
            # On error, allow request but log the issue
            return await call_next(request)
    
    def _get_action_from_endpoint(self, path: str) -> str:
        """Determine action from endpoint path"""
        for pattern, action in self.ACTION_MAPPING.items():
            if pattern in path:
                return action
        
        # Default action based on path segments
        if "financial" in path:
            return "financial_operation"
        elif "auth" in path:
            return "authentication"
        else:
            return "general"
    
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