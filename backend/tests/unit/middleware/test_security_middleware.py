"""Comprehensive tests for security middleware."""
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
import hashlib
import time

from middleware.security_middleware import (
    SecurityMiddleware,
    RateLimitMiddleware,
    CORSMiddleware,
    CSRFMiddleware,
    SecurityHeadersMiddleware,
    RequestValidationMiddleware,
    IPWhitelistMiddleware,
    DDoSProtectionMiddleware
)


class TestSecurityHeadersMiddleware:
    """Test cases for security headers middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with security headers middleware."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_security_headers_added(self, app):
        """Test that all security headers are added to responses."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/test")
            
            # Check security headers
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["X-XSS-Protection"] == "1; mode=block"
            assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
            assert "default-src 'self'" in response.headers["Content-Security-Policy"]
            assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
            assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
    
    @pytest.mark.asyncio
    async def test_custom_csp_policy(self):
        """Test custom Content Security Policy configuration."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.example.com"
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/test")
            assert "script-src 'self' 'unsafe-inline' https://cdn.example.com" in response.headers["Content-Security-Policy"]
    
    @pytest.mark.asyncio
    async def test_remove_server_header(self, app):
        """Test that server identification headers are removed."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/test")
            
            # These headers should not be present
            assert "Server" not in response.headers
            assert "X-Powered-By" not in response.headers


class TestRateLimitMiddleware:
    """Test cases for rate limiting middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with rate limit middleware."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5
        )
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/api/expensive")
        @rate_limit(requests_per_minute=2)
        async def expensive_endpoint():
            return {"message": "expensive operation"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_rate_limit_within_limits(self, app):
        """Test requests within rate limits."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Make requests within limit
            for i in range(5):
                response = await client.get("/api/test")
                assert response.status_code == 200
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, app):
        """Test rate limit exceeded scenario."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Exceed burst size
            for i in range(6):
                response = await client.get("/api/test")
            
            # Last request should be rate limited
            assert response.status_code == 429
            assert response.json()["detail"] == "Rate limit exceeded"
            assert "Retry-After" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_per_endpoint(self, app):
        """Test endpoint-specific rate limits."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Expensive endpoint has lower limit
            response = await client.get("/api/expensive")
            assert response.status_code == 200
            assert int(response.headers["X-RateLimit-Limit"]) == 2
            
            # Second request OK
            response = await client.get("/api/expensive")
            assert response.status_code == 200
            
            # Third request rate limited
            response = await client.get("/api/expensive")
            assert response.status_code == 429
    
    @pytest.mark.asyncio
    async def test_rate_limit_by_user(self):
        """Test rate limiting by authenticated user."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=10,
            by_user=True
        )
        
        @app.get("/api/test")
        async def test_endpoint(request: Request):
            return {"user": request.state.user.id if hasattr(request.state, "user") else None}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Requests without user - shared limit
            for i in range(5):
                response = await client.get("/api/test")
                assert response.status_code == 200
            
            # Different users have separate limits
            with patch("middleware.security_middleware.get_current_user") as mock_user:
                mock_user.return_value = MagicMock(id="user1")
                for i in range(5):
                    response = await client.get("/api/test", headers={"Authorization": "Bearer token1"})
                    assert response.status_code == 200
                
                mock_user.return_value = MagicMock(id="user2")
                for i in range(5):
                    response = await client.get("/api/test", headers={"Authorization": "Bearer token2"})
                    assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_whitelist(self):
        """Test rate limit whitelist for certain IPs/users."""
        app = FastAPI()
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=1,
            whitelist_ips=["192.168.1.1"],
            whitelist_user_ids=["admin123"]
        )
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Whitelisted IP - no limit
            for i in range(10):
                response = await client.get(
                    "/api/test",
                    headers={"X-Forwarded-For": "192.168.1.1"}
                )
                assert response.status_code == 200
            
            # Non-whitelisted IP - limited
            response = await client.get("/api/test")
            assert response.status_code == 200
            response = await client.get("/api/test")
            assert response.status_code == 429


class TestCORSMiddleware:
    """Test cases for CORS middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with CORS middleware."""
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allowed_origins=["https://app.example.com", "http://localhost:3000"],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
            allowed_headers=["Content-Type", "Authorization"],
            allow_credentials=True,
            max_age=3600
        )
        
        @app.get("/api/data")
        async def get_data():
            return {"data": "test"}
        
        @app.post("/api/data")
        async def post_data():
            return {"created": True}
        
        return app
    
    @pytest.mark.asyncio
    async def test_cors_preflight_request(self, app):
        """Test CORS preflight OPTIONS request."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.options(
                "/api/data",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type,Authorization"
                }
            )
            
            assert response.status_code == 204
            assert response.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
            assert "POST" in response.headers["Access-Control-Allow-Methods"]
            assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]
            assert response.headers["Access-Control-Allow-Credentials"] == "true"
            assert response.headers["Access-Control-Max-Age"] == "3600"
    
    @pytest.mark.asyncio
    async def test_cors_actual_request(self, app):
        """Test CORS headers on actual request."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/data",
                headers={"Origin": "https://app.example.com"}
            )
            
            assert response.status_code == 200
            assert response.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
            assert response.headers["Access-Control-Allow-Credentials"] == "true"
    
    @pytest.mark.asyncio
    async def test_cors_disallowed_origin(self, app):
        """Test CORS with disallowed origin."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/data",
                headers={"Origin": "https://evil.com"}
            )
            
            assert response.status_code == 200  # Request succeeds
            assert "Access-Control-Allow-Origin" not in response.headers
    
    @pytest.mark.asyncio
    async def test_cors_wildcard_origin(self):
        """Test CORS with wildcard origin (development mode)."""
        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allowed_origins=["*"],
            allow_credentials=False  # Can't use credentials with wildcard
        )
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/test",
                headers={"Origin": "https://any-origin.com"}
            )
            
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert "Access-Control-Allow-Credentials" not in response.headers


class TestCSRFMiddleware:
    """Test cases for CSRF protection middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with CSRF middleware."""
        app = FastAPI()
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test_csrf_secret",
            token_expiry=3600
        )
        
        @app.get("/api/csrf-token")
        async def get_csrf_token(request: Request):
            return {"csrf_token": request.state.csrf_token}
        
        @app.post("/api/data")
        async def post_data(request: Request):
            return {"message": "Data created"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_csrf_token_generation(self, app):
        """Test CSRF token generation."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/csrf-token")
            assert response.status_code == 200
            assert "csrf_token" in response.json()
            
            token = response.json()["csrf_token"]
            assert len(token) >= 32
    
    @pytest.mark.asyncio
    async def test_csrf_protection_post_request(self, app):
        """Test CSRF protection on POST requests."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Get CSRF token
            token_response = await client.get("/api/csrf-token")
            csrf_token = token_response.json()["csrf_token"]
            
            # POST without CSRF token - should fail
            response = await client.post("/api/data", json={"data": "test"})
            assert response.status_code == 403
            assert "CSRF" in response.json()["detail"]
            
            # POST with CSRF token in header - should succeed
            response = await client.post(
                "/api/data",
                json={"data": "test"},
                headers={"X-CSRF-Token": csrf_token}
            )
            assert response.status_code == 200
            
            # POST with CSRF token in form data - should succeed
            response = await client.post(
                "/api/data",
                data={"data": "test", "csrf_token": csrf_token}
            )
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_csrf_safe_methods_exempt(self, app):
        """Test that safe methods are exempt from CSRF checks."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # GET requests don't need CSRF token
            response = await client.get("/api/data")
            assert response.status_code == 404  # Endpoint doesn't exist, but no CSRF error
    
    @pytest.mark.asyncio
    async def test_csrf_double_submit_cookie(self):
        """Test double-submit cookie CSRF protection."""
        app = FastAPI()
        app.add_middleware(
            CSRFMiddleware,
            secret_key="test_secret",
            use_double_submit=True
        )
        
        @app.post("/api/test")
        async def test_endpoint():
            return {"success": True}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Get CSRF cookie
            response = await client.get("/")
            csrf_cookie = response.cookies.get("csrf_token")
            
            # POST with matching cookie and header
            response = await client.post(
                "/api/test",
                headers={"X-CSRF-Token": csrf_cookie},
                cookies={"csrf_token": csrf_cookie}
            )
            assert response.status_code == 200


class TestIPWhitelistMiddleware:
    """Test cases for IP whitelist middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with IP whitelist middleware."""
        app = FastAPI()
        app.add_middleware(
            IPWhitelistMiddleware,
            whitelist=["192.168.1.0/24", "10.0.0.1"],
            blacklist=["192.168.1.100"],
            paths=["/admin/*", "/api/internal/*"]
        )
        
        @app.get("/public")
        async def public_endpoint():
            return {"message": "public"}
        
        @app.get("/admin/users")
        async def admin_endpoint():
            return {"message": "admin"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_ip_whitelist_allowed(self, app):
        """Test allowed IP addresses."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Whitelisted IP accessing protected path
            response = await client.get(
                "/admin/users",
                headers={"X-Forwarded-For": "192.168.1.50"}
            )
            assert response.status_code == 200
            
            # Any IP accessing public path
            response = await client.get(
                "/public",
                headers={"X-Forwarded-For": "1.2.3.4"}
            )
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ip_whitelist_blocked(self, app):
        """Test blocked IP addresses."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Non-whitelisted IP accessing protected path
            response = await client.get(
                "/admin/users",
                headers={"X-Forwarded-For": "1.2.3.4"}
            )
            assert response.status_code == 403
            assert "IP not allowed" in response.json()["detail"]
            
            # Blacklisted IP (even though in whitelist range)
            response = await client.get(
                "/admin/users",
                headers={"X-Forwarded-For": "192.168.1.100"}
            )
            assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_ip_extraction_methods(self):
        """Test different methods of IP extraction."""
        app = FastAPI()
        app.add_middleware(
            IPWhitelistMiddleware,
            whitelist=["192.168.1.1"],
            paths=["/*"]
        )
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # X-Forwarded-For header
            response = await client.get(
                "/test",
                headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
            )
            assert response.status_code == 200
            
            # X-Real-IP header
            response = await client.get(
                "/test",
                headers={"X-Real-IP": "192.168.1.1"}
            )
            assert response.status_code == 200


class TestDDoSProtectionMiddleware:
    """Test cases for DDoS protection middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with DDoS protection."""
        app = FastAPI()
        app.add_middleware(
            DDoSProtectionMiddleware,
            requests_per_second=10,
            burst_size=20,
            block_duration=300,
            suspicious_patterns=[
                r"/wp-admin",
                r"\.php$",
                r"/admin/.*\.sql"
            ]
        )
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_ddos_normal_traffic(self, app):
        """Test normal traffic patterns."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Normal rate requests
            for i in range(10):
                response = await client.get("/api/test")
                assert response.status_code == 200
                await asyncio.sleep(0.1)  # 100ms between requests
    
    @pytest.mark.asyncio
    async def test_ddos_burst_detection(self, app):
        """Test burst traffic detection."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Burst of requests
            responses = []
            for i in range(25):  # Exceeds burst size
                response = await client.get("/api/test")
                responses.append(response)
            
            # Some requests should be blocked
            blocked = [r for r in responses if r.status_code == 429]
            assert len(blocked) > 0
            
            # Check block duration header
            assert "Retry-After" in blocked[0].headers
            assert int(blocked[0].headers["Retry-After"]) == 300
    
    @pytest.mark.asyncio
    async def test_ddos_suspicious_patterns(self, app):
        """Test detection of suspicious URL patterns."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Suspicious patterns should be blocked immediately
            suspicious_urls = [
                "/wp-admin/admin.php",
                "/backup.sql",
                "/admin/dump.sql"
            ]
            
            for url in suspicious_urls:
                response = await client.get(url)
                assert response.status_code == 403
                assert "Suspicious request pattern" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_ddos_ip_reputation(self):
        """Test IP reputation scoring."""
        app = FastAPI()
        ddos_middleware = DDoSProtectionMiddleware(app, use_ip_reputation=True)
        
        # Test reputation calculation
        ip = "1.2.3.4"
        
        # Simulate suspicious behavior
        for _ in range(10):
            ddos_middleware.record_suspicious_activity(ip, "rapid_requests")
        
        reputation = ddos_middleware.get_ip_reputation(ip)
        assert reputation["score"] < 50  # Low score = bad reputation
        assert reputation["is_blocked"] is True
        
        # Test reputation decay over time
        with patch("time.time", return_value=time.time() + 3600):  # 1 hour later
            reputation = ddos_middleware.get_ip_reputation(ip)
            assert reputation["score"] > 0  # Score improved
    
    @pytest.mark.asyncio
    async def test_ddos_challenge_response(self):
        """Test challenge-response mechanism for suspected bots."""
        app = FastAPI()
        app.add_middleware(
            DDoSProtectionMiddleware,
            use_challenge=True,
            challenge_threshold=5
        )
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "test"}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Make requests until challenge triggered
            for i in range(6):
                response = await client.get("/api/test")
            
            # Should receive challenge
            assert response.status_code == 418  # I'm a teapot (challenge)
            assert "challenge" in response.json()
            
            challenge = response.json()["challenge"]
            solution = hashlib.sha256(challenge.encode()).hexdigest()
            
            # Submit solution
            response = await client.get(
                "/api/test",
                headers={"X-Challenge-Solution": solution}
            )
            assert response.status_code == 200


class TestRequestValidationMiddleware:
    """Test cases for request validation middleware."""
    
    @pytest.fixture
    def app(self):
        """Create test app with request validation."""
        app = FastAPI()
        app.add_middleware(
            RequestValidationMiddleware,
            max_body_size=1024 * 1024,  # 1MB
            allowed_content_types=["application/json", "multipart/form-data"],
            validate_json=True,
            max_form_fields=100
        )
        
        @app.post("/api/data")
        async def post_data(request: Request):
            body = await request.json()
            return {"received": len(body)}
        
        return app
    
    @pytest.mark.asyncio
    async def test_request_size_limit(self, app):
        """Test request body size limits."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Small request - OK
            response = await client.post(
                "/api/data",
                json={"data": "small"}
            )
            assert response.status_code == 200
            
            # Large request - blocked
            large_data = "x" * (2 * 1024 * 1024)  # 2MB
            response = await client.post(
                "/api/data",
                json={"data": large_data}
            )
            assert response.status_code == 413
            assert "Request body too large" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_content_type_validation(self, app):
        """Test content type validation."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Allowed content type
            response = await client.post(
                "/api/data",
                json={"data": "test"}
            )
            assert response.status_code == 200
            
            # Disallowed content type
            response = await client.post(
                "/api/data",
                content="<xml>data</xml>",
                headers={"Content-Type": "application/xml"}
            )
            assert response.status_code == 415
            assert "Unsupported media type" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_json_validation(self, app):
        """Test JSON payload validation."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Valid JSON
            response = await client.post(
                "/api/data",
                json={"valid": "json"}
            )
            assert response.status_code == 200
            
            # Invalid JSON
            response = await client.post(
                "/api/data",
                content='{"invalid": json}',
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400
            assert "Invalid JSON" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        app = FastAPI()
        app.add_middleware(
            RequestValidationMiddleware,
            detect_sql_injection=True
        )
        
        @app.get("/api/search")
        async def search(q: str):
            return {"query": q}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Normal query
            response = await client.get("/api/search?q=normal search")
            assert response.status_code == 200
            
            # SQL injection attempt
            response = await client.get("/api/search?q='; DROP TABLE users; --")
            assert response.status_code == 400
            assert "Suspicious input detected" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_path_traversal_detection(self):
        """Test path traversal attack detection."""
        app = FastAPI()
        app.add_middleware(
            RequestValidationMiddleware,
            detect_path_traversal=True
        )
        
        @app.get("/api/file/{path:path}")
        async def get_file(path: str):
            return {"path": path}
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Normal path
            response = await client.get("/api/file/documents/report.pdf")
            assert response.status_code == 200
            
            # Path traversal attempt
            response = await client.get("/api/file/../../etc/passwd")
            assert response.status_code == 400
            assert "Invalid path" in response.json()["detail"]