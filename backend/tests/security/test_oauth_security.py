"""
Security audit tests for OAuth implementation.
Tests OWASP compliance and OAuth-specific security vulnerabilities.
"""
import pytest
import asyncio
import secrets
import hashlib
import base64
import jwt
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from uuid import uuid4
import httpx
from urllib.parse import urlparse, parse_qs, quote, unquote
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend


class OAuthSecurityAudit:
    """Comprehensive OAuth security audit tests."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)
        self.security_issues = []
    
    async def setup(self):
        """Set up test environment."""
        self.test_client_id = f"security_test_{uuid4()}"
        self.test_redirect_uri = "http://localhost:3000/callback"
    
    async def teardown(self):
        """Clean up test environment."""
        await self.client.aclose()
        
        if self.security_issues:
            print("\n" + "=" * 60)
            print("SECURITY ISSUES FOUND:")
            print("=" * 60)
            for issue in self.security_issues:
                print(f"- {issue}")
            print("=" * 60)
    
    def log_security_issue(self, issue: str, severity: str = "HIGH"):
        """Log a security issue."""
        self.security_issues.append(f"[{severity}] {issue}")
    
    # ==================== OWASP Top 10 Tests ====================
    
    @pytest.mark.asyncio
    async def test_injection_attacks(self):
        """Test for injection vulnerabilities (OWASP A03:2021)."""
        print("\n[OWASP A03] Testing Injection Attacks...")
        
        injection_payloads = [
            # SQL Injection
            "'; DROP TABLE oauth_tokens; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users--",
            "admin'--",
            
            # NoSQL Injection
            '{"$ne": null}',
            '{"$gt": ""}',
            
            # LDAP Injection
            "*)(uid=*))(|(uid=*",
            
            # Command Injection
            "; cat /etc/passwd",
            "| ls -la",
            "`whoami`",
            
            # Header Injection
            "\r\nX-Injected-Header: malicious",
            
            # JSON Injection
            '{"key": "value", "injected": "data"}',
        ]
        
        for payload in injection_payloads:
            # Test authorization endpoint
            try:
                response = await self.client.get(
                    "/oauth/authorize",
                    params={
                        "response_type": "code",
                        "client_id": payload,
                        "redirect_uri": self.test_redirect_uri,
                        "scope": payload,
                        "state": payload,
                    }
                )
                
                # Check for error disclosure
                if "syntax error" in response.text.lower() or \
                   "sql" in response.text.lower() or \
                   "exception" in response.text.lower():
                    self.log_security_issue(
                        f"Possible injection vulnerability with payload: {payload[:50]}..."
                    )
            except Exception:
                pass
            
            # Test token endpoint
            try:
                response = await self.client.post(
                    "/oauth/token",
                    json={
                        "grant_type": "authorization_code",
                        "code": payload,
                        "client_id": payload,
                        "redirect_uri": payload,
                    }
                )
                
                if response.status_code == 500:
                    self.log_security_issue(
                        f"Server error with injection payload: {payload[:50]}..."
                    )
            except Exception:
                pass
        
        print(f"  Tested {len(injection_payloads)} injection payloads")
    
    @pytest.mark.asyncio
    async def test_broken_authentication(self):
        """Test for broken authentication (OWASP A07:2021)."""
        print("\n[OWASP A07] Testing Broken Authentication...")
        
        # Test 1: Brute force protection
        failed_attempts = 0
        for i in range(20):
            response = await self.client.post(
                "/oauth/token",
                json={
                    "grant_type": "password",
                    "username": "admin",
                    "password": f"wrong_password_{i}",
                }
            )
            
            if response.status_code != 429:  # Not rate limited
                failed_attempts += 1
        
        if failed_attempts >= 15:
            self.log_security_issue(
                "No brute force protection detected - unlimited login attempts allowed"
            )
        
        # Test 2: Session fixation
        # Get initial session
        response1 = await self.client.get("/oauth/authorize")
        cookies1 = response1.cookies
        
        # Authenticate
        auth_response = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": self.test_client_id,
                "client_secret": "test_secret",
            }
        )
        
        # Check if session ID changed after authentication
        response2 = await self.client.get("/oauth/authorize")
        cookies2 = response2.cookies
        
        if cookies1 == cookies2:
            self.log_security_issue(
                "Session fixation vulnerability - session ID not regenerated after authentication",
                severity="MEDIUM"
            )
        
        # Test 3: Weak password policy
        weak_passwords = ["123456", "password", "admin", "12345678", "qwerty"]
        for weak_pass in weak_passwords:
            response = await self.client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"test_user_{uuid4()}",
                    "password": weak_pass,
                    "email": f"test_{uuid4()}@example.com",
                }
            )
            
            if response.status_code == 200:
                self.log_security_issue(
                    f"Weak password accepted: {weak_pass}",
                    severity="MEDIUM"
                )
                break
        
        print("  ✓ Authentication security tests completed")
    
    @pytest.mark.asyncio
    async def test_sensitive_data_exposure(self):
        """Test for sensitive data exposure (OWASP A02:2021)."""
        print("\n[OWASP A02] Testing Sensitive Data Exposure...")
        
        # Test 1: Check if tokens are exposed in URLs
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "token",  # Implicit flow (should be disabled)
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
            }
        )
        
        if response.status_code == 302:
            redirect_url = response.headers.get("Location", "")
            if "access_token=" in redirect_url:
                self.log_security_issue(
                    "Access token exposed in URL (implicit flow should be disabled)"
                )
        
        # Test 2: Check for sensitive data in error messages
        response = await self.client.post(
            "/oauth/token",
            json={"grant_type": "invalid_grant"}
        )
        
        error_text = response.text.lower()
        sensitive_keywords = ["password", "secret", "token", "key", "database", "sql"]
        
        for keyword in sensitive_keywords:
            if keyword in error_text:
                self.log_security_issue(
                    f"Sensitive information '{keyword}' exposed in error message",
                    severity="MEDIUM"
                )
        
        # Test 3: Check response headers for information disclosure
        sensitive_headers = ["Server", "X-Powered-By", "X-AspNet-Version"]
        
        for header in sensitive_headers:
            if header in response.headers:
                self.log_security_issue(
                    f"Information disclosure via {header} header: {response.headers[header]}",
                    severity="LOW"
                )
        
        print("  ✓ Sensitive data exposure tests completed")
    
    @pytest.mark.asyncio
    async def test_security_misconfiguration(self):
        """Test for security misconfiguration (OWASP A05:2021)."""
        print("\n[OWASP A05] Testing Security Misconfiguration...")
        
        # Test 1: Check for debug mode
        response = await self.client.get("/debug")
        if response.status_code == 200:
            self.log_security_issue("Debug endpoint accessible in production")
        
        # Test 2: Check for default credentials
        default_creds = [
            ("admin", "admin"),
            ("admin", "password"),
            ("test", "test"),
            ("demo", "demo"),
        ]
        
        for username, password in default_creds:
            response = await self.client.post(
                "/oauth/token",
                json={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                }
            )
            
            if response.status_code == 200:
                self.log_security_issue(
                    f"Default credentials accepted: {username}/{password}"
                )
                break
        
        # Test 3: Check security headers
        response = await self.client.get("/")
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "Content-Security-Policy": None,  # Just check existence
            "Strict-Transport-Security": None,
            "X-XSS-Protection": "1; mode=block",
        }
        
        for header, expected_values in required_headers.items():
            if header not in response.headers:
                self.log_security_issue(
                    f"Missing security header: {header}",
                    severity="MEDIUM"
                )
            elif expected_values:
                actual_value = response.headers[header]
                if isinstance(expected_values, list):
                    if actual_value not in expected_values:
                        self.log_security_issue(
                            f"Incorrect {header} value: {actual_value}",
                            severity="LOW"
                        )
                elif actual_value != expected_values:
                    self.log_security_issue(
                        f"Incorrect {header} value: {actual_value}",
                        severity="LOW"
                    )
        
        print("  ✓ Security misconfiguration tests completed")
    
    @pytest.mark.asyncio
    async def test_vulnerable_components(self):
        """Test for vulnerable and outdated components (OWASP A06:2021)."""
        print("\n[OWASP A06] Testing Vulnerable Components...")
        
        # Test 1: Check for version disclosure
        response = await self.client.get("/api/version")
        if response.status_code == 200:
            try:
                version_info = response.json()
                if "dependencies" in version_info:
                    self.log_security_issue(
                        "Dependency versions exposed publicly",
                        severity="LOW"
                    )
            except Exception:
                pass
        
        # Test 2: Check for known vulnerable patterns
        vulnerable_patterns = [
            "/swagger-ui/",
            "/api-docs/",
            "/.git/",
            "/.env",
            "/config.json",
            "/package.json",
        ]
        
        for pattern in vulnerable_patterns:
            response = await self.client.get(pattern)
            if response.status_code == 200:
                self.log_security_issue(
                    f"Sensitive file/directory accessible: {pattern}"
                )
        
        print("  ✓ Vulnerable components tests completed")
    
    @pytest.mark.asyncio
    async def test_identification_and_authentication_failures(self):
        """Test for identification and authentication failures (OWASP A07:2021)."""
        print("\n[OWASP A07] Testing Identification & Authentication...")
        
        # Test 1: Password reset token security
        response = await self.client.post(
            "/api/v1/auth/reset-password",
            json={"email": "test@example.com"}
        )
        
        if response.status_code == 200:
            # Check if token is predictable
            tokens = []
            for _ in range(3):
                resp = await self.client.post(
                    "/api/v1/auth/reset-password",
                    json={"email": f"test_{uuid4()}@example.com"}
                )
                if "token" in resp.text:
                    tokens.append(resp.json().get("token"))
            
            if tokens and len(set(tokens)) < len(tokens):
                self.log_security_issue(
                    "Password reset tokens may be predictable"
                )
        
        # Test 2: Account enumeration
        response1 = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "password",
                "username": "nonexistent_user_12345",
                "password": "wrong_password",
            }
        )
        
        response2 = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "password",
                "username": "admin",  # Assuming this exists
                "password": "wrong_password",
            }
        )
        
        # Check if responses are different (timing or message)
        if response1.text != response2.text:
            self.log_security_issue(
                "User enumeration possible through different error messages",
                severity="MEDIUM"
            )
        
        print("  ✓ Authentication failure tests completed")
    
    @pytest.mark.asyncio
    async def test_ssrf_vulnerabilities(self):
        """Test for Server-Side Request Forgery (OWASP A10:2021)."""
        print("\n[OWASP A10] Testing SSRF Vulnerabilities...")
        
        ssrf_payloads = [
            "http://localhost:8080/admin",
            "http://127.0.0.1:22",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "file:///etc/passwd",
            "gopher://localhost:8080",
            "dict://localhost:11211",
        ]
        
        for payload in ssrf_payloads:
            # Test redirect_uri parameter
            response = await self.client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": self.test_client_id,
                    "redirect_uri": payload,
                }
            )
            
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                if payload in location:
                    self.log_security_issue(
                        f"SSRF vulnerability: redirect to {payload}"
                    )
        
        print("  ✓ SSRF tests completed")
    
    # ==================== OAuth-Specific Security Tests ====================
    
    @pytest.mark.asyncio
    async def test_authorization_code_reuse(self):
        """Test that authorization codes cannot be reused."""
        print("\n[OAuth Security] Testing Authorization Code Reuse...")
        
        # Simulate getting an authorization code
        auth_code = str(uuid4())
        
        # First use (should work or fail gracefully)
        response1 = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
            }
        )
        
        # Second use (must fail)
        response2 = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
            }
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            self.log_security_issue(
                "Authorization code can be reused - replay attack possible"
            )
        
        print("  ✓ Authorization code reuse test completed")
    
    @pytest.mark.asyncio
    async def test_redirect_uri_validation(self):
        """Test redirect URI validation."""
        print("\n[OAuth Security] Testing Redirect URI Validation...")
        
        malicious_redirects = [
            "http://evil.com/callback",
            "http://localhost:3000.evil.com/callback",
            "http://localhost:3000@evil.com/callback",
            "http://localhost:3000%2Eevil.com/callback",
            "//evil.com/callback",
            "http://localhost:3000/../evil.com",
            "data:text/html,<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
        ]
        
        for malicious_uri in malicious_redirects:
            response = await self.client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": self.test_client_id,
                    "redirect_uri": malicious_uri,
                }
            )
            
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                if malicious_uri in location or "evil.com" in location:
                    self.log_security_issue(
                        f"Open redirect vulnerability with URI: {malicious_uri}"
                    )
        
        print("  ✓ Redirect URI validation tests completed")
    
    @pytest.mark.asyncio
    async def test_state_parameter_validation(self):
        """Test state parameter validation for CSRF protection."""
        print("\n[OAuth Security] Testing State Parameter Validation...")
        
        # Test 1: Missing state parameter
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
                # No state parameter
            }
        )
        
        if response.status_code == 302:
            self.log_security_issue(
                "State parameter not required - CSRF protection missing",
                severity="HIGH"
            )
        
        # Test 2: State parameter tampering
        original_state = str(uuid4())
        tampered_state = str(uuid4())
        
        # Initial request with state
        response1 = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
                "state": original_state,
            }
        )
        
        # Callback with tampered state
        response2 = await self.client.get(
            f"/oauth/callback?code=test_code&state={tampered_state}"
        )
        
        if response2.status_code == 200:
            self.log_security_issue(
                "State parameter not validated - CSRF attack possible"
            )
        
        print("  ✓ State parameter validation tests completed")
    
    @pytest.mark.asyncio
    async def test_token_leakage(self):
        """Test for token leakage vulnerabilities."""
        print("\n[OAuth Security] Testing Token Leakage...")
        
        # Test 1: Token in referrer header
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
            },
            headers={"Referer": "http://evil.com?token=secret_token"}
        )
        
        # Check if token is logged or exposed
        if response.status_code == 200:
            if "secret_token" in response.text:
                self.log_security_issue(
                    "Token from referrer header exposed in response"
                )
        
        # Test 2: Token in URL parameters (should use POST)
        response = await self.client.get(
            "/oauth/revoke?token=test_token"
        )
        
        if response.status_code != 405:  # Should require POST
            self.log_security_issue(
                "Token revocation accepts GET request - tokens exposed in logs",
                severity="MEDIUM"
            )
        
        print("  ✓ Token leakage tests completed")
    
    @pytest.mark.asyncio
    async def test_pkce_implementation(self):
        """Test PKCE implementation security."""
        print("\n[OAuth Security] Testing PKCE Implementation...")
        
        # Test 1: Missing PKCE for public clients
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": "public_client",
                "redirect_uri": self.test_redirect_uri,
                # No code_challenge
            }
        )
        
        if response.status_code == 302:
            self.log_security_issue(
                "PKCE not required for public clients",
                severity="HIGH"
            )
        
        # Test 2: Weak code_challenge
        weak_challenge = "simple_challenge"
        
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
                "code_challenge": weak_challenge,
                "code_challenge_method": "plain",  # Should not allow plain
            }
        )
        
        if response.status_code == 302:
            self.log_security_issue(
                "PKCE accepts 'plain' method - should require S256",
                severity="MEDIUM"
            )
        
        # Test 3: Code verifier validation
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        wrong_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        
        # Authorization with challenge
        auth_response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": self.test_client_id,
                "redirect_uri": self.test_redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        
        # Token exchange with wrong verifier
        token_response = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": "test_code",
                "client_id": self.test_client_id,
                "code_verifier": wrong_verifier,
            }
        )
        
        if token_response.status_code == 200:
            self.log_security_issue(
                "PKCE verifier not properly validated"
            )
        
        print("  ✓ PKCE implementation tests completed")
    
    @pytest.mark.asyncio
    async def test_token_security(self):
        """Test token security properties."""
        print("\n[OAuth Security] Testing Token Security...")
        
        # Test 1: Token entropy
        tokens = []
        for _ in range(10):
            response = await self.client.post(
                "/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": f"test_{uuid4()}",
                    "client_secret": "secret",
                }
            )
            
            if response.status_code == 200:
                try:
                    token = response.json().get("access_token")
                    if token:
                        tokens.append(token)
                except Exception:
                    pass
        
        if tokens:
            # Check token length
            avg_length = sum(len(t) for t in tokens) / len(tokens)
            if avg_length < 32:
                self.log_security_issue(
                    f"Token length too short: {avg_length} characters",
                    severity="MEDIUM"
                )
            
            # Check for patterns
            if len(set(tokens)) < len(tokens):
                self.log_security_issue(
                    "Duplicate tokens generated - low entropy"
                )
        
        # Test 2: JWT signature validation if using JWT
        if tokens and "." in tokens[0]:  # Likely a JWT
            try:
                # Try to decode without verification
                header, payload, signature = tokens[0].split(".")
                
                # Tamper with payload
                decoded_payload = base64.urlsafe_b64decode(
                    payload + "=" * (4 - len(payload) % 4)
                )
                tampered_payload = decoded_payload.replace(b"user", b"admin")
                tampered_token = f"{header}.{base64.urlsafe_b64encode(tampered_payload).decode().rstrip('=')}.{signature}"
                
                # Try to use tampered token
                response = await self.client.get(
                    "/api/v1/me",
                    headers={"Authorization": f"Bearer {tampered_token}"}
                )
                
                if response.status_code == 200:
                    self.log_security_issue(
                        "JWT signature not properly validated"
                    )
            except Exception:
                pass
        
        print("  ✓ Token security tests completed")
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting implementation."""
        print("\n[OAuth Security] Testing Rate Limiting...")
        
        # Test token endpoint rate limiting
        request_count = 0
        rate_limited = False
        
        for i in range(100):
            response = await self.client.post(
                "/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": f"test_{i}",
                    "client_secret": "wrong_secret",
                }
            )
            
            request_count += 1
            
            if response.status_code == 429:
                rate_limited = True
                break
        
        if not rate_limited:
            self.log_security_issue(
                f"No rate limiting on token endpoint after {request_count} requests"
            )
        else:
            print(f"  Rate limited after {request_count} requests")
        
        # Test introspection endpoint rate limiting
        introspect_limited = False
        for i in range(200):
            response = await self.client.post(
                "/oauth/introspect",
                json={"token": f"test_token_{i}"}
            )
            
            if response.status_code == 429:
                introspect_limited = True
                break
        
        if not introspect_limited:
            self.log_security_issue(
                "No rate limiting on introspection endpoint",
                severity="MEDIUM"
            )
        
        print("  ✓ Rate limiting tests completed")
    
    def generate_security_report(self) -> str:
        """Generate security audit report."""
        report = ["=" * 60]
        report.append("OAuth Security Audit Report")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        if not self.security_issues:
            report.append("✅ No security issues found!")
        else:
            report.append(f"⚠️ Found {len(self.security_issues)} security issues:")
            report.append("")
            
            # Group by severity
            high = [i for i in self.security_issues if "[HIGH]" in i]
            medium = [i for i in self.security_issues if "[MEDIUM]" in i]
            low = [i for i in self.security_issues if "[LOW]" in i]
            
            if high:
                report.append("HIGH SEVERITY:")
                for issue in high:
                    report.append(f"  {issue}")
                report.append("")
            
            if medium:
                report.append("MEDIUM SEVERITY:")
                for issue in medium:
                    report.append(f"  {issue}")
                report.append("")
            
            if low:
                report.append("LOW SEVERITY:")
                for issue in low:
                    report.append(f"  {issue}")
                report.append("")
        
        report.append("=" * 60)
        return "\n".join(report)


# Run security audit
if __name__ == "__main__":
    async def run_security_audit():
        """Run complete security audit."""
        audit = OAuthSecurityAudit()
        
        print("=" * 60)
        print("Starting OAuth Security Audit")
        print("=" * 60)
        
        await audit.setup()
        
        try:
            # OWASP Top 10 Tests
            await audit.test_injection_attacks()
            await audit.test_broken_authentication()
            await audit.test_sensitive_data_exposure()
            await audit.test_security_misconfiguration()
            await audit.test_vulnerable_components()
            await audit.test_identification_and_authentication_failures()
            await audit.test_ssrf_vulnerabilities()
            
            # OAuth-Specific Tests
            await audit.test_authorization_code_reuse()
            await audit.test_redirect_uri_validation()
            await audit.test_state_parameter_validation()
            await audit.test_token_leakage()
            await audit.test_pkce_implementation()
            await audit.test_token_security()
            await audit.test_rate_limiting()
            
        finally:
            await audit.teardown()
        
        # Generate report
        report = audit.generate_security_report()
        print("\n" + report)
        
        # Save report
        with open("oauth_security_audit_report.txt", "w") as f:
            f.write(report)
        
        print(f"\nReport saved to: oauth_security_audit_report.txt")
        
        # Return exit code based on findings
        return 1 if audit.security_issues else 0
    
    # Run audit
    exit_code = asyncio.run(run_security_audit())
    exit(exit_code)