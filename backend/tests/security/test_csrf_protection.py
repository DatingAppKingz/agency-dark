"""
CSRF protection tests for OAuth implementation.
Tests Cross-Site Request Forgery prevention mechanisms.
"""
import pytest
import asyncio
import secrets
from uuid import uuid4
import httpx
from typing import Dict, Optional
import json


class CSRFProtectionTest:
    """Test CSRF protection mechanisms."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)
        self.csrf_vulnerabilities = []
    
    async def setup(self):
        """Set up test environment."""
        # Get initial CSRF token
        response = await self.client.get("/")
        self.cookies = response.cookies
        
        # Extract CSRF token from response
        self.csrf_token = self.extract_csrf_token(response)
    
    async def teardown(self):
        """Clean up."""
        await self.client.aclose()
        
        if self.csrf_vulnerabilities:
            print("\n⚠️  CSRF Vulnerabilities Found:")
            for vuln in self.csrf_vulnerabilities:
                print(f"  - {vuln}")
    
    def extract_csrf_token(self, response: httpx.Response) -> Optional[str]:
        """Extract CSRF token from response."""
        # Check cookies
        for cookie_name in ["csrf_token", "XSRF-TOKEN", "_csrf"]:
            if cookie_name in response.cookies:
                return response.cookies[cookie_name]
        
        # Check response body for token in meta tag or hidden field
        if "csrf" in response.text.lower():
            # Simple extraction (would need proper HTML parsing in production)
            import re
            match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', response.text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @pytest.mark.asyncio
    async def test_state_parameter_csrf(self):
        """Test CSRF protection via state parameter."""
        print("\n[CSRF] Testing State Parameter Protection...")
        
        # Test 1: Authorization without state
        response = await self.client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": "test_client",
                "redirect_uri": "http://localhost:3000/callback",
                # No state parameter
            }
        )
        
        if response.status_code in [200, 302]:
            self.csrf_vulnerabilities.append(
                "Authorization endpoint accepts requests without state parameter"
            )
        
        # Test 2: Predictable state values
        states = []
        for _ in range(5):
            response = await self.client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": "test_client",
                    "redirect_uri": "http://localhost:3000/callback",
                    "state": "fixed_state",  # Same state
                }
            )
            
            if response.status_code in [200, 302]:
                states.append("fixed_state")
        
        if len(set(states)) == 1:
            self.csrf_vulnerabilities.append(
                "Server accepts predictable/reused state values"
            )
        
        print("  ✓ State parameter tests completed")
    
    @pytest.mark.asyncio
    async def test_token_endpoint_csrf(self):
        """Test CSRF protection on token endpoint."""
        print("\n[CSRF] Testing Token Endpoint Protection...")
        
        # Test 1: Cross-origin token request
        headers = {
            "Origin": "http://evil.com",
            "Referer": "http://evil.com/attack",
        }
        
        response = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": "test_code",
                "client_id": "test_client",
            },
            headers=headers
        )
        
        if response.status_code == 200:
            self.csrf_vulnerabilities.append(
                "Token endpoint accepts cross-origin requests"
            )
        
        # Test 2: Token request without proper headers
        response = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "refresh_token",
                "refresh_token": "test_token",
            }
            # No CSRF token or security headers
        )
        
        if response.status_code != 403:
            self.csrf_vulnerabilities.append(
                "Token refresh accepts requests without CSRF protection"
            )
        
        print("  ✓ Token endpoint tests completed")
    
    @pytest.mark.asyncio
    async def test_double_submit_cookie(self):
        """Test double-submit cookie CSRF protection."""
        print("\n[CSRF] Testing Double-Submit Cookie Protection...")
        
        # Get CSRF token from cookie
        csrf_cookie = None
        response = await self.client.get("/oauth/authorize")
        
        for cookie_name in ["csrf_token", "XSRF-TOKEN"]:
            if cookie_name in response.cookies:
                csrf_cookie = response.cookies[cookie_name]
                break
        
        if csrf_cookie:
            # Test 1: Request with mismatched token
            headers = {
                "X-CSRF-Token": "wrong_token",
            }
            
            response = await self.client.post(
                "/oauth/token",
                json={"grant_type": "client_credentials"},
                headers=headers,
                cookies={cookie_name: csrf_cookie}
            )
            
            if response.status_code == 200:
                self.csrf_vulnerabilities.append(
                    "Double-submit cookie validation not enforced"
                )
            
            # Test 2: Request without header token
            response = await self.client.post(
                "/oauth/token",
                json={"grant_type": "client_credentials"},
                cookies={cookie_name: csrf_cookie}
                # No X-CSRF-Token header
            )
            
            if response.status_code == 200:
                self.csrf_vulnerabilities.append(
                    "CSRF token not required in headers"
                )
        
        print("  ✓ Double-submit cookie tests completed")
    
    @pytest.mark.asyncio
    async def test_same_site_cookie(self):
        """Test SameSite cookie attribute."""
        print("\n[CSRF] Testing SameSite Cookie Attribute...")
        
        response = await self.client.get("/oauth/authorize")
        
        session_cookies = ["session", "sessionid", "auth_token", "access_token"]
        
        for cookie_name in session_cookies:
            if cookie_name in response.cookies:
                cookie = response.cookies[cookie_name]
                
                # Check SameSite attribute (would need proper cookie parsing)
                # This is a simplified check
                if not hasattr(cookie, 'same_site') or cookie.same_site not in ['Strict', 'Lax']:
                    self.csrf_vulnerabilities.append(
                        f"Cookie '{cookie_name}' missing SameSite attribute"
                    )
        
        print("  ✓ SameSite cookie tests completed")
    
    @pytest.mark.asyncio
    async def test_referrer_validation(self):
        """Test referrer header validation."""
        print("\n[CSRF] Testing Referrer Validation...")
        
        # Test 1: No referrer
        response = await self.client.post(
            "/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": "test_code",
            }
            # No Referer header
        )
        
        # Some endpoints might require referrer
        if response.status_code == 200:
            print("  Note: Token endpoint accepts requests without Referer header")
        
        # Test 2: Malicious referrer
        headers = {
            "Referer": "http://evil.com/csrf-attack",
        }
        
        response = await self.client.post(
            "/oauth/revoke",
            json={"token": "test_token"},
            headers=headers
        )
        
        if response.status_code in [200, 204]:
            self.csrf_vulnerabilities.append(
                "Token revocation accepts requests from any referrer"
            )
        
        print("  ✓ Referrer validation tests completed")
    
    @pytest.mark.asyncio
    async def test_cors_configuration(self):
        """Test CORS configuration for CSRF prevention."""
        print("\n[CSRF] Testing CORS Configuration...")
        
        # Test 1: OPTIONS preflight
        response = await self.client.options(
            "/oauth/token",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        if "Access-Control-Allow-Origin" in response.headers:
            allow_origin = response.headers["Access-Control-Allow-Origin"]
            
            if allow_origin == "*":
                self.csrf_vulnerabilities.append(
                    "CORS allows all origins (*) - CSRF possible"
                )
            elif "evil.com" in allow_origin:
                self.csrf_vulnerabilities.append(
                    "CORS allows malicious origin"
                )
        
        # Test 2: Actual cross-origin request
        response = await self.client.post(
            "/oauth/token",
            json={"grant_type": "client_credentials"},
            headers={
                "Origin": "http://evil.com",
            }
        )
        
        if response.status_code == 200:
            if "Access-Control-Allow-Origin" in response.headers:
                self.csrf_vulnerabilities.append(
                    "Cross-origin POST requests allowed to token endpoint"
                )
        
        print("  ✓ CORS configuration tests completed")
    
    @pytest.mark.asyncio
    async def test_custom_headers(self):
        """Test custom header requirements for CSRF protection."""
        print("\n[CSRF] Testing Custom Header Requirements...")
        
        # Test request without custom headers
        response = await self.client.post(
            "/oauth/token",
            json={"grant_type": "client_credentials"}
        )
        
        # Test request with custom header
        response_with_header = await self.client.post(
            "/oauth/token",
            json={"grant_type": "client_credentials"},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        
        # If custom header makes a difference, it's being used for CSRF
        if response.status_code != response_with_header.status_code:
            print("  Custom header 'X-Requested-With' is used for CSRF protection")
        
        print("  ✓ Custom header tests completed")
    
    def generate_report(self) -> str:
        """Generate CSRF test report."""
        report = ["=" * 60]
        report.append("CSRF Protection Test Report")
        report.append("=" * 60)
        
        if not self.csrf_vulnerabilities:
            report.append("✅ No CSRF vulnerabilities found!")
        else:
            report.append(f"⚠️  Found {len(self.csrf_vulnerabilities)} CSRF vulnerabilities:")
            for vuln in self.csrf_vulnerabilities:
                report.append(f"  - {vuln}")
        
        report.append("")
        report.append("Recommendations:")
        report.append("  1. Always require state parameter for authorization")
        report.append("  2. Implement double-submit cookie pattern")
        report.append("  3. Use SameSite=Strict for session cookies")
        report.append("  4. Validate Origin/Referer headers")
        report.append("  5. Configure CORS properly (no wildcards)")
        
        report.append("=" * 60)
        return "\n".join(report)


if __name__ == "__main__":
    async def run_csrf_tests():
        """Run CSRF protection tests."""
        test = CSRFProtectionTest()
        
        print("=" * 60)
        print("Starting CSRF Protection Tests")
        print("=" * 60)
        
        await test.setup()
        
        try:
            await test.test_state_parameter_csrf()
            await test.test_token_endpoint_csrf()
            await test.test_double_submit_cookie()
            await test.test_same_site_cookie()
            await test.test_referrer_validation()
            await test.test_cors_configuration()
            await test.test_custom_headers()
        finally:
            await test.teardown()
        
        # Generate report
        report = test.generate_report()
        print("\n" + report)
        
        return 0 if not test.csrf_vulnerabilities else 1
    
    exit_code = asyncio.run(run_csrf_tests())
    exit(exit_code)