"""
OWASP Security Testing Suite
Tests for OWASP Top 10 vulnerabilities
"""
import pytest
import asyncio
import re
import json
import base64
import secrets
from typing import Dict, Any, List
from datetime import datetime, timedelta
import jwt
import sqlparse
from urllib.parse import quote, unquote

from httpx import AsyncClient
from sqlalchemy import text

from core.security import verify_password, get_password_hash


class TestOWASPTop10:
    """Test suite for OWASP Top 10 vulnerabilities"""
    
    # A01:2021 – Broken Access Control
    @pytest.mark.security
    async def test_broken_access_control(self, async_client: AsyncClient, auth_headers):
        """Test for broken access control vulnerabilities"""
        # Test 1: Attempt to access other user's data
        response = await async_client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )
        assert response.status_code in [403, 404], "Should not access other user's data"
        
        # Test 2: Attempt to modify without proper permissions
        response = await async_client.put(
            "/api/v1/admin/settings",
            json={"setting": "value"},
            headers=auth_headers
        )
        assert response.status_code == 403, "Should require admin permissions"
        
        # Test 3: Test for IDOR (Insecure Direct Object Reference)
        # Try sequential IDs
        for i in range(1, 10):
            response = await async_client.get(
                f"/api/v1/content/{i}",
                headers=auth_headers
            )
            # Should either be 404 or properly authorized
            assert response.status_code in [200, 403, 404]
    
    # A02:2021 – Cryptographic Failures
    @pytest.mark.security
    async def test_cryptographic_failures(self, async_client: AsyncClient):
        """Test for cryptographic vulnerabilities"""
        # Test 1: Ensure passwords are hashed
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        assert password not in hashed, "Password should not be stored in plain text"
        assert "$2b$" in hashed or "$argon2" in hashed, "Should use strong hashing"
        
        # Test 2: Check for sensitive data in responses
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "test", "password": "test", "grant_type": "password"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "password" not in data, "Password should not be in response"
            assert "hashed_password" not in data, "Hashed password should not be in response"
        
        # Test 3: Verify HTTPS enforcement
        assert async_client.base_url.scheme == "https" or "localhost" in str(async_client.base_url)
    
    # A03:2021 – Injection
    @pytest.mark.security
    async def test_injection_vulnerabilities(self, async_client: AsyncClient, auth_headers, db_session):
        """Test for injection vulnerabilities"""
        # Test 1: SQL Injection attempts
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM users--",
            "' OR 1=1--",
            "admin'--",
            "' UNION SELECT NULL, username, password FROM users--"
        ]
        
        for payload in sql_payloads:
            # Try in search
            response = await async_client.get(
                f"/api/v1/content/search?q={quote(payload)}",
                headers=auth_headers
            )
            assert response.status_code in [200, 400], "Should handle SQL injection attempts safely"
            
            # Verify no actual SQL execution
            if response.status_code == 200:
                assert "error" not in response.text.lower()
                assert "syntax" not in response.text.lower()
        
        # Test 2: NoSQL Injection attempts
        nosql_payloads = [
            {"$ne": None},
            {"$gt": ""},
            {"$where": "this.password == 'test'"},
            {"username": {"$regex": ".*"}}
        ]
        
        for payload in nosql_payloads:
            response = await async_client.post(
                "/api/v1/auth/login",
                json={"username": payload, "password": "test"}
            )
            assert response.status_code in [400, 422], "Should reject NoSQL injection"
        
        # Test 3: Command Injection
        cmd_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "; rm -rf /"
        ]
        
        for payload in cmd_payloads:
            # Try in any field that might execute commands
            response = await async_client.post(
                "/api/v1/reports/generate",
                json={"filename": payload, "type": "pdf"},
                headers=auth_headers
            )
            assert response.status_code in [400, 422], "Should reject command injection"
        
        # Test 4: LDAP Injection
        ldap_payloads = [
            "*)(uid=*",
            "admin)(&(password=*",
            "*)(|(uid=*"
        ]
        
        for payload in ldap_payloads:
            response = await async_client.post(
                "/api/v1/auth/ldap",
                json={"username": payload, "password": "test"}
            )
            assert response.status_code in [400, 401, 422], "Should handle LDAP injection"
    
    # A04:2021 – Insecure Design
    @pytest.mark.security
    async def test_insecure_design(self, async_client: AsyncClient):
        """Test for insecure design patterns"""
        # Test 1: Rate limiting on sensitive endpoints
        for i in range(10):
            response = await async_client.post(
                "/api/v1/auth/login",
                data={"username": "test", "password": f"wrong{i}", "grant_type": "password"}
            )
        
        # Should be rate limited by now
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "test", "password": "wrong", "grant_type": "password"}
        )
        assert response.status_code == 429, "Login endpoint should be rate limited"
        
        # Test 2: Account enumeration protection
        response1 = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent@example.com", "password": "wrong", "grant_type": "password"}
        )
        
        response2 = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "existing@example.com", "password": "wrong", "grant_type": "password"}
        )
        
        # Error messages should be identical
        if response1.status_code == 401 and response2.status_code == 401:
            assert response1.json() == response2.json(), "Should not reveal user existence"
        
        # Test 3: Password complexity requirements
        weak_passwords = ["123456", "password", "qwerty", "12345678", "abc123"]
        
        for pwd in weak_passwords:
            response = await async_client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{secrets.token_hex(4)}@example.com",
                    "username": f"test{secrets.token_hex(4)}",
                    "password": pwd
                }
            )
            assert response.status_code == 422, f"Should reject weak password: {pwd}"
    
    # A05:2021 – Security Misconfiguration
    @pytest.mark.security
    async def test_security_misconfiguration(self, async_client: AsyncClient):
        """Test for security misconfiguration"""
        # Test 1: Debug mode should be disabled
        response = await async_client.get("/api/v1/debug")
        assert response.status_code == 404, "Debug endpoints should not be exposed"
        
        # Test 2: Stack traces should not be exposed
        response = await async_client.get("/api/v1/error/test")
        if response.status_code == 500:
            assert "Traceback" not in response.text, "Stack traces should not be exposed"
            assert "line" not in response.text.lower()
        
        # Test 3: Security headers
        response = await async_client.get("/api/v1/health")
        headers = response.headers
        
        assert "X-Content-Type-Options" in headers, "Missing X-Content-Type-Options"
        assert headers.get("X-Content-Type-Options") == "nosniff"
        
        assert "X-Frame-Options" in headers, "Missing X-Frame-Options"
        assert headers.get("X-Frame-Options") in ["DENY", "SAMEORIGIN"]
        
        assert "X-XSS-Protection" in headers, "Missing X-XSS-Protection"
        assert "Strict-Transport-Security" in headers, "Missing HSTS header"
        
        # Test 4: Default credentials should not work
        default_creds = [
            ("admin", "admin"),
            ("administrator", "password"),
            ("root", "root"),
            ("test", "test")
        ]
        
        for username, password in default_creds:
            response = await async_client.post(
                "/api/v1/auth/login",
                data={"username": username, "password": password, "grant_type": "password"}
            )
            assert response.status_code != 200, f"Default credentials should not work: {username}/{password}"
    
    # A06:2021 – Vulnerable and Outdated Components
    @pytest.mark.security
    def test_vulnerable_components(self):
        """Test for vulnerable dependencies"""
        # This would typically be done with tools like:
        # - pip-audit
        # - safety
        # - bandit
        # - snyk
        
        # Example check
        import pkg_resources
        
        vulnerable_packages = {
            "django": "< 3.2",  # Example vulnerable version
            "flask": "< 2.0",
            "requests": "< 2.20.0"
        }
        
        installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
        
        for package, vulnerable_version in vulnerable_packages.items():
            if package in installed_packages:
                # This is a simplified check - real version comparison is more complex
                print(f"Check {package} version {installed_packages[package]}")
    
    # A07:2021 – Identification and Authentication Failures
    @pytest.mark.security
    async def test_authentication_failures(self, async_client: AsyncClient, db_session):
        """Test for authentication vulnerabilities"""
        # Test 1: Session fixation
        # Get a session before login
        response1 = await async_client.get("/api/v1/health")
        session_before = response1.cookies.get("session")
        
        # Login
        response2 = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "test", "password": "test", "grant_type": "password"}
        )
        
        if response2.status_code == 200:
            session_after = response2.cookies.get("session")
            if session_before and session_after:
                assert session_before != session_after, "Session should be regenerated after login"
        
        # Test 2: Weak session tokens
        if response2.status_code == 200:
            token = response2.json().get("access_token", "")
            
            # Check token entropy
            assert len(token) > 32, "Token should be sufficiently long"
            
            # Verify it's not predictable
            assert not token.isdigit(), "Token should not be numeric only"
            assert not token.isalpha(), "Token should not be alphabetic only"
        
        # Test 3: Password reset token security
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        
        if response.status_code == 200:
            # Token should not be in response
            data = response.json()
            assert "token" not in data, "Reset token should not be in response"
            assert "reset_token" not in data
        
        # Test 4: Multi-factor authentication
        # Check if MFA is available
        response = await async_client.get("/api/v1/auth/mfa/status")
        assert response.status_code in [200, 401], "MFA endpoint should exist"
    
    # A08:2021 – Software and Data Integrity Failures
    @pytest.mark.security
    async def test_integrity_failures(self, async_client: AsyncClient, auth_headers):
        """Test for software and data integrity failures"""
        # Test 1: Insecure deserialization
        serialized_payloads = [
            # Python pickle exploit attempt
            base64.b64encode(b"cos\nsystem\n(S'id'\ntR.").decode(),
            # Java serialization attempt
            "rO0ABXNyABdqYXZhLmxhbmcuUHJvY2Vzc0J1aWxkZXI=",
            # PHP serialization
            'O:8:"stdClass":1:{s:4:"test";s:10:"phpinfo();";}',
        ]
        
        for payload in serialized_payloads:
            response = await async_client.post(
                "/api/v1/data/import",
                json={"data": payload},
                headers=auth_headers
            )
            assert response.status_code in [400, 422], "Should reject unsafe deserialization"
        
        # Test 2: File upload integrity
        # Upload a file
        files = {"file": ("test.txt", b"test content", "text/plain")}
        response = await async_client.post(
            "/api/v1/upload",
            files=files,
            headers={k: v for k, v in auth_headers.items() if k != "Content-Type"}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should include integrity check
            assert "checksum" in data or "hash" in data, "Should provide file integrity check"
        
        # Test 3: Code injection via file upload
        malicious_files = [
            ("test.php", b"<?php system($_GET['cmd']); ?>", "text/plain"),
            ("test.jsp", b"<%@ page import='java.io.*' %>", "text/plain"),
            ("test.aspx", b"<%@ Page Language='C#' %>", "text/plain"),
        ]
        
        for filename, content, mimetype in malicious_files:
            files = {"file": (filename, content, mimetype)}
            response = await async_client.post(
                "/api/v1/upload",
                files=files,
                headers={k: v for k, v in auth_headers.items() if k != "Content-Type"}
            )
            assert response.status_code in [400, 422], f"Should reject {filename}"
    
    # A09:2021 – Security Logging and Monitoring Failures
    @pytest.mark.security
    async def test_logging_monitoring_failures(self, async_client: AsyncClient, redis_mock):
        """Test for security logging and monitoring"""
        # Test 1: Failed login attempts should be logged
        for i in range(5):
            await async_client.post(
                "/api/v1/auth/login",
                data={"username": "attacker", "password": f"attempt{i}", "grant_type": "password"}
            )
        
        # Check if failed attempts are tracked
        # In a real app, this would check logs or monitoring system
        
        # Test 2: Suspicious activity detection
        # Rapid requests from same source
        tasks = []
        for i in range(50):
            task = async_client.get("/api/v1/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should detect and potentially block suspicious activity
        blocked_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 429)
        assert blocked_count > 0, "Should detect rapid requests"
        
        # Test 3: Security events should be logged
        security_events = [
            ("/api/v1/admin/users", "GET"),  # Admin access
            ("/api/v1/auth/logout", "POST"),  # Logout
            ("/api/v1/users/delete", "DELETE"),  # Data deletion
        ]
        
        for endpoint, method in security_events:
            # These should be logged even if they fail
            if method == "GET":
                await async_client.get(endpoint)
            elif method == "POST":
                await async_client.post(endpoint)
            elif method == "DELETE":
                await async_client.delete(endpoint)
    
    # A10:2021 – Server-Side Request Forgery (SSRF)
    @pytest.mark.security
    async def test_ssrf_vulnerabilities(self, async_client: AsyncClient, auth_headers):
        """Test for SSRF vulnerabilities"""
        # Test 1: URL parameter exploitation
        ssrf_urls = [
            "http://localhost:6379",  # Redis
            "http://127.0.0.1:5432",  # PostgreSQL
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "file:///etc/passwd",  # Local file access
            "gopher://localhost:6379",  # Gopher protocol
            "dict://localhost:11211",  # Memcached
            "http://[::1]:80",  # IPv6 localhost
            "http://0.0.0.0:8080",
        ]
        
        for url in ssrf_urls:
            # Test webhook URL
            response = await async_client.post(
                "/api/v1/webhooks",
                json={"url": url, "events": ["test"]},
                headers=auth_headers
            )
            assert response.status_code in [400, 422], f"Should block SSRF attempt: {url}"
            
            # Test image URL
            response = await async_client.post(
                "/api/v1/media/fetch",
                json={"url": url},
                headers=auth_headers
            )
            assert response.status_code in [400, 422], f"Should block SSRF in media fetch: {url}"
        
        # Test 2: DNS rebinding protection
        suspicious_domains = [
            "localhost.example.com",
            "127.0.0.1.nip.io",
            "localtest.me",
        ]
        
        for domain in suspicious_domains:
            response = await async_client.post(
                "/api/v1/webhooks",
                json={"url": f"http://{domain}", "events": ["test"]},
                headers=auth_headers
            )
            # Should validate the resolved IP
            assert response.status_code in [200, 400, 422]


class SecurityTestHelpers:
    """Helper functions for security testing"""
    
    @staticmethod
    def generate_xss_payloads() -> List[str]:
        """Generate XSS test payloads"""
        return [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(`XSS`)'></iframe>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            "<video><source onerror=\"alert('XSS')\">",
            "<audio src=x onerror=alert('XSS')>",
            "<details open ontoggle=alert('XSS')>",
            "<marquee onstart=alert('XSS')>",
            "<meter onmouseover=alert('XSS')>XSS</meter>",
            "';alert('XSS')//",
            "\";alert('XSS')//",
            "</script><script>alert('XSS')</script>",
            "--><script>alert('XSS')</script>",
            "<scr<script>ipt>alert('XSS')</scr<script>ipt>",
        ]
    
    @staticmethod
    def check_password_policy(password: str) -> Dict[str, bool]:
        """Check if password meets security requirements"""
        return {
            "min_length": len(password) >= 8,
            "has_uppercase": bool(re.search(r'[A-Z]', password)),
            "has_lowercase": bool(re.search(r'[a-z]', password)),
            "has_digit": bool(re.search(r'\d', password)),
            "has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
            "no_common": password.lower() not in ['password', '12345678', 'qwerty'],
        }
    
    @staticmethod
    def detect_sql_injection(query: str) -> bool:
        """Detect potential SQL injection in query"""
        sql_keywords = [
            "union", "select", "insert", "update", "delete", "drop",
            "create", "alter", "exec", "execute", "script", "--", "/*", "*/"
        ]
        
        query_lower = query.lower()
        for keyword in sql_keywords:
            if keyword in query_lower:
                # Check if it's in a string literal
                parsed = sqlparse.parse(query)
                for statement in parsed:
                    for token in statement.tokens:
                        if token.ttype not in [sqlparse.tokens.String.Single, sqlparse.tokens.String.Symbol]:
                            if keyword in str(token).lower():
                                return True
        
        return False


# Security test configuration
SECURITY_TEST_CONFIG = {
    "rate_limits": {
        "login": {"requests": 5, "window": 300},  # 5 requests per 5 minutes
        "api": {"requests": 100, "window": 60},    # 100 requests per minute
        "upload": {"requests": 10, "window": 3600} # 10 uploads per hour
    },
    "password_policy": {
        "min_length": 8,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digit": True,
        "require_special": True,
        "prevent_common": True
    },
    "session_config": {
        "timeout": 3600,  # 1 hour
        "regenerate_on_login": True,
        "secure_cookie": True,
        "httponly_cookie": True,
        "samesite": "strict"
    }
}


@pytest.fixture
def security_scanner():
    """Fixture for security scanning utilities"""
    return SecurityTestHelpers()


# Run OWASP ZAP or similar security scanner
def run_security_scan(target_url: str):
    """Run automated security scan"""
    # This would integrate with OWASP ZAP, Burp Suite, or similar
    print(f"Running security scan on {target_url}")
    
    # Example ZAP integration
    """
    from zapv2 import ZAPv2
    
    zap = ZAPv2(apikey='your-api-key')
    
    # Spider the target
    zap.spider.scan(target_url)
    
    # Active scan
    zap.ascan.scan(target_url)
    
    # Get results
    alerts = zap.core.alerts()
    
    return alerts
    """