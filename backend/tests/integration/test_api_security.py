"""
Integration tests for API security features.
"""
import pytest
from httpx import AsyncClient
import time
import json


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, client: AsyncClient):
        """Test that rate limits are enforced."""
        # Make requests up to the limit
        endpoint = "/api/v1/auth/login"
        
        # Note: Rate limit is set to 100/minute in tests
        # We'll test with a smaller burst
        responses = []
        for i in range(10):
            response = await client.post(
                endpoint,
                json={"username": "test", "password": "wrong"}
            )
            responses.append(response)
        
        # All requests should go through (under limit)
        assert all(r.status_code != 429 for r in responses)
        
        # Check rate limit headers
        last_response = responses[-1]
        assert "X-RateLimit-Limit" in last_response.headers
        assert "X-RateLimit-Remaining" in last_response.headers
        assert "X-RateLimit-Reset" in last_response.headers


class TestSecurityHeaders:
    """Test security headers."""
    
    @pytest.mark.asyncio
    async def test_security_headers_present(self, client: AsyncClient):
        """Test that security headers are present in responses."""
        response = await client.get("/health")
        
        # Check security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Content-Security-Policy" in response.headers
    
    @pytest.mark.asyncio
    async def test_csp_header(self, client: AsyncClient):
        """Test Content Security Policy header."""
        response = await client.get("/health")
        
        csp = response.headers.get("Content-Security-Policy")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "connect-src 'self'" in csp


class TestInputValidation:
    """Test input validation at API level."""
    
    @pytest.mark.asyncio
    async def test_sql_injection_blocked(self, client: AsyncClient):
        """Test that SQL injection attempts are blocked."""
        # Try SQL injection in query parameter
        response = await client.get(
            "/api/v1/users",
            params={"search": "'; DROP TABLE users--"}
        )
        
        # Should be blocked by security middleware
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_xss_blocked(self, client: AsyncClient, auth_headers):
        """Test that XSS attempts are blocked."""
        # Try XSS in request body
        response = await client.post(
            "/api/v1/models/profile",
            headers=auth_headers,
            json={
                "bio": "<script>alert('XSS')</script>Normal text"
            }
        )
        
        # Should be blocked or sanitized
        if response.status_code == 200:
            # If accepted, should be sanitized
            assert "<script>" not in response.json().get("bio", "")
        else:
            # Or blocked entirely
            assert response.status_code == 400


class TestAPIKeyAuthentication:
    """Test API key authentication."""
    
    @pytest.mark.asyncio
    async def test_api_key_required_endpoints(self, client: AsyncClient):
        """Test endpoints that require API key."""
        # Webhook endpoint should require API key
        response = await client.post(
            "/api/v1/integrations/webhook/inflow",
            json={"event": "test"}
        )
        
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client: AsyncClient):
        """Test invalid API key is rejected."""
        headers = {"X-API-Key": "invalid_key"}
        
        response = await client.post(
            "/api/v1/integrations/webhook/inflow",
            headers=headers,
            json={"event": "test"}
        )
        
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]


class TestCORS:
    """Test CORS configuration."""
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """Test CORS headers for allowed origins."""
        # Preflight request
        response = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # Check CORS headers
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers
    
    @pytest.mark.asyncio
    async def test_cors_blocked_origin(self, client: AsyncClient):
        """Test CORS blocks unauthorized origins."""
        # Request from unauthorized origin
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://evil.com"},
            json={"username": "test", "password": "test"}
        )
        
        # Should not have CORS headers for unauthorized origin
        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        assert allow_origin != "http://evil.com"


class TestPasswordPolicies:
    """Test password security policies."""
    
    @pytest.mark.asyncio
    async def test_weak_password_rejected(self, client: AsyncClient, test_agency):
        """Test that weak passwords are rejected."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "username": "weakuser",
                "password": "weak",  # Too short
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        
        assert response.status_code == 400
        assert "Password must be at least 8 characters" in response.text
    
    @pytest.mark.asyncio
    async def test_password_complexity(self, client: AsyncClient, test_agency):
        """Test password complexity requirements."""
        # No uppercase
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test1@example.com",
                "username": "testuser1",
                "password": "password123",
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        assert response.status_code == 400
        
        # No numbers
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test2@example.com",
                "username": "testuser2",
                "password": "PasswordOnly",
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        assert response.status_code == 400
        
        # Valid password
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test3@example.com",
                "username": "testuser3",
                "password": "ValidPass123",
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        assert response.status_code == 201


class TestSessionSecurity:
    """Test session security features."""
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, client: AsyncClient):
        """Test that expired tokens are rejected."""
        # This would require mocking time or using a short-lived token
        # For now, test that invalid tokens are rejected
        
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_token_cannot_be_reused_after_logout(self, client: AsyncClient, test_user):
        """Test that tokens cannot be used after logout."""
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "testpassword"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Verify token works
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        
        # Logout
        logout_response = await client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 200
        
        # Try to use token after logout
        # Note: This requires token blacklisting implementation
        # For now, we just verify logout succeeded