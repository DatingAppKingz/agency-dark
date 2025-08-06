"""
Request signature validation for API security
"""
import hmac
import hashlib
import time
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from pydantic import BaseModel

from core.config import settings
from core.logging import logger


class SignatureConfig(BaseModel):
    """Configuration for request signature validation"""
    secret_key: str
    algorithm: str = "sha256"
    timestamp_tolerance: int = 300  # 5 minutes
    include_headers: list[str] = ["content-type", "content-length"]
    required_headers: list[str] = ["x-timestamp", "x-signature"]


class RequestSignatureValidator:
    """Validates request signatures for API security"""
    
    def __init__(self, config: SignatureConfig):
        self.config = config
        self.hash_func = getattr(hashlib, config.algorithm)
    
    def generate_signature(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[bytes] = None,
        timestamp: Optional[int] = None
    ) -> Tuple[str, int]:
        """
        Generate signature for a request
        
        Returns:
            Tuple of (signature, timestamp)
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        # Create canonical request
        canonical_request = self._create_canonical_request(
            method, path, headers, body, timestamp
        )
        
        # Generate signature
        signature = hmac.new(
            self.config.secret_key.encode(),
            canonical_request.encode(),
            self.hash_func
        ).hexdigest()
        
        return signature, timestamp
    
    def validate_signature(
        self,
        request: Request,
        body: Optional[bytes] = None
    ) -> bool:
        """
        Validate request signature
        
        Returns:
            True if signature is valid
        
        Raises:
            HTTPException if signature is invalid
        """
        # Check required headers
        for header in self.config.required_headers:
            if header not in request.headers:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Missing required header: {header}"
                )
        
        # Get timestamp
        try:
            timestamp = int(request.headers.get("x-timestamp", "0"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid timestamp format"
            )
        
        # Check timestamp freshness
        current_time = int(time.time())
        if abs(current_time - timestamp) > self.config.timestamp_tolerance:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Request timestamp too old or too far in future"
            )
        
        # Get provided signature
        provided_signature = request.headers.get("x-signature", "")
        
        # Generate expected signature
        expected_signature, _ = self.generate_signature(
            method=request.method,
            path=request.url.path,
            headers=dict(request.headers),
            body=body,
            timestamp=timestamp
        )
        
        # Constant-time comparison
        if not hmac.compare_digest(expected_signature, provided_signature):
            logger.warning(
                f"Invalid signature for {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature"
            )
        
        return True
    
    def _create_canonical_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[bytes],
        timestamp: int
    ) -> str:
        """Create canonical request string for signing"""
        parts = [
            method.upper(),
            path,
            str(timestamp)
        ]
        
        # Add specified headers
        for header_name in sorted(self.config.include_headers):
            header_value = headers.get(header_name, "")
            parts.append(f"{header_name}:{header_value}")
        
        # Add body hash
        if body:
            body_hash = hashlib.sha256(body).hexdigest()
        else:
            body_hash = hashlib.sha256(b"").hexdigest()
        parts.append(body_hash)
        
        return "\n".join(parts)


class APISignatureMiddleware:
    """Middleware for validating request signatures"""
    
    def __init__(self, secret_key: str, paths_to_validate: list[str]):
        self.validator = RequestSignatureValidator(
            SignatureConfig(secret_key=secret_key)
        )
        self.paths_to_validate = paths_to_validate
    
    async def __call__(self, request: Request, call_next):
        """Validate request signature for protected paths"""
        # Check if path requires signature validation
        requires_signature = any(
            request.url.path.startswith(path)
            for path in self.paths_to_validate
        )
        
        if requires_signature:
            # Read body for signature validation
            body = await request.body()
            
            # Validate signature
            self.validator.validate_signature(request, body)
            
            # Reconstruct request with body
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
        
        # Process request
        response = await call_next(request)
        return response


# Utility functions for client-side signature generation
def sign_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    secret_key: str,
    algorithm: str = "sha256"
) -> Dict[str, str]:
    """
    Sign a request (client-side utility)
    
    Returns:
        Updated headers with signature
    """
    import urllib.parse
    
    # Parse URL
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if parsed.query:
        path += f"?{parsed.query}"
    
    # Convert body to bytes
    body_bytes = None
    if body is not None:
        body_bytes = json.dumps(body, sort_keys=True).encode()
        headers["content-type"] = "application/json"
        headers["content-length"] = str(len(body_bytes))
    
    # Generate signature
    validator = RequestSignatureValidator(
        SignatureConfig(secret_key=secret_key, algorithm=algorithm)
    )
    signature, timestamp = validator.generate_signature(
        method=method,
        path=path,
        headers=headers,
        body=body_bytes
    )
    
    # Add signature headers
    headers["x-timestamp"] = str(timestamp)
    headers["x-signature"] = signature
    
    return headers


# Example usage for webhook signature validation
class WebhookSignatureValidator:
    """Validates webhook signatures from external services"""
    
    @staticmethod
    def validate_stripe_webhook(
        payload: bytes,
        signature: str,
        secret: str,
        tolerance: int = 300
    ) -> bool:
        """Validate Stripe webhook signature"""
        # Parse signature header
        elements = {}
        for element in signature.split(","):
            k, v = element.split("=", 1)
            elements[k] = v
        
        # Check timestamp
        if "t" not in elements:
            return False
        
        timestamp = int(elements["t"])
        if abs(time.time() - timestamp) > tolerance:
            return False
        
        # Verify signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Check if any signature matches
        signatures = [v for k, v in elements.items() if k.startswith("v")]
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    
    @staticmethod
    def validate_github_webhook(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """Validate GitHub webhook signature"""
        expected = "sha256=" + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def validate_generic_hmac(
        payload: bytes,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """Validate generic HMAC signature"""
        hash_func = getattr(hashlib, algorithm)
        expected = hmac.new(
            secret.encode(),
            payload,
            hash_func
        ).hexdigest()
        
        # Remove any prefix (e.g., "sha256=")
        if "=" in signature:
            signature = signature.split("=", 1)[1]
        
        return hmac.compare_digest(expected, signature)