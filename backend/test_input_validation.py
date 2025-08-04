#!/usr/bin/env python3
"""Test script to verify input validation implementation."""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/v1"

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_sql_injection_prevention():
    """Test SQL injection prevention in various inputs."""
    print_section("Testing SQL Injection Prevention")
    
    # Test cases with SQL injection attempts
    sql_injection_cases = [
        {
            "name": "SQL injection in email",
            "data": {
                "email": "test@test.com'; DROP TABLE users; --",
                "password": "ValidPass123!"
            }
        },
        {
            "name": "SQL injection in search query",
            "params": {
                "q": "search' OR '1'='1"
            }
        },
        {
            "name": "SQL injection in username",
            "data": {
                "email": "valid@test.com",
                "username": "admin'; DELETE FROM users WHERE '1'='1",
                "password": "ValidPass123!"
            }
        },
        {
            "name": "Union select in query param",
            "params": {
                "filter": "name' UNION SELECT * FROM users--"
            }
        }
    ]
    
    for test_case in sql_injection_cases:
        print(f"Testing: {test_case['name']}")
        
        if 'data' in test_case:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json=test_case['data']
            )
        else:
            response = requests.get(
                f"{BASE_URL}/search",
                params=test_case.get('params', {})
            )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 422]:
            print("  ✅ SQL injection attempt blocked")
        else:
            print("  ❌ SQL injection attempt NOT blocked!")
            print(f"  Response: {response.text[:200]}")

def test_xss_prevention():
    """Test XSS prevention in user inputs."""
    print_section("Testing XSS Prevention")
    
    xss_cases = [
        {
            "name": "Script tag in full name",
            "data": {
                "email": "test@test.com",
                "username": "testuser",
                "password": "ValidPass123!",
                "full_name": "<script>alert('XSS')</script>"
            }
        },
        {
            "name": "JavaScript URL in profile",
            "data": {
                "website": "javascript:alert('XSS')"
            }
        },
        {
            "name": "Event handler in description",
            "data": {
                "description": '<img src=x onerror="alert(\'XSS\')">'
            }
        },
        {
            "name": "Iframe injection",
            "data": {
                "content": '<iframe src="http://evil.com"></iframe>'
            }
        }
    ]
    
    for test_case in xss_cases:
        print(f"Testing: {test_case['name']}")
        
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=test_case['data']
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 422]:
            print("  ✅ XSS attempt blocked")
        else:
            print("  ❌ XSS attempt might not be blocked")
            # Check if the response contains the XSS payload
            if 'script' in response.text.lower() or 'javascript:' in response.text.lower():
                print("  ❌ XSS payload found in response!")

def test_email_validation():
    """Test email validation with various formats."""
    print_section("Testing Email Validation")
    
    email_cases = [
        ("valid@example.com", True, "Valid email"),
        ("user.name+tag@example.co.uk", True, "Email with dots and plus"),
        ("invalid.email", False, "Missing @ symbol"),
        ("@example.com", False, "Missing local part"),
        ("user@", False, "Missing domain"),
        ("user @example.com", False, "Space in email"),
        ("user@example..com", False, "Double dots"),
        ("user@gmial.com", False, "Common typo (gmial)"),
        ("a" * 255 + "@example.com", False, "Email too long"),
    ]
    
    for email, should_pass, description in email_cases:
        print(f"Testing: {description} - '{email}'")
        
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "username": "testuser",
                "password": "ValidPass123!"
            }
        )
        
        print(f"  Status: {response.status_code}")
        
        if should_pass and response.status_code != 422:
            print("  ✅ Valid email accepted")
        elif not should_pass and response.status_code == 422:
            print("  ✅ Invalid email rejected")
        else:
            print(f"  ❌ Unexpected result for {description}")

def test_password_validation():
    """Test password strength validation."""
    print_section("Testing Password Validation")
    
    password_cases = [
        ("ValidPass123!", True, "Valid password"),
        ("short", False, "Too short"),
        ("alllowercase123!", False, "No uppercase"),
        ("ALLUPPERCASE123!", False, "No lowercase"),
        ("NoNumbers!", False, "No numbers"),
        ("NoSpecialChar123", False, "No special characters"),
        ("password123!", False, "Common password"),
        ("testuser123!", False, "Contains username"),
        ("a" * 200, False, "Too long"),
    ]
    
    for password, should_pass, description in password_cases:
        print(f"Testing: {description}")
        
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": password
            }
        )
        
        print(f"  Status: {response.status_code}")
        
        if should_pass and response.status_code != 422:
            print("  ✅ Valid password accepted")
        elif not should_pass and response.status_code == 422:
            print("  ✅ Invalid password rejected")
            data = response.json()
            if 'detail' in data and isinstance(data['detail'], dict):
                print(f"  Reason: {data['detail'].get('error', 'N/A')}")
        else:
            print(f"  ❌ Unexpected result for {description}")

def test_username_validation():
    """Test username validation."""
    print_section("Testing Username Validation")
    
    username_cases = [
        ("validuser", True, "Valid username"),
        ("user_123", True, "Username with underscore and numbers"),
        ("ab", False, "Too short"),
        ("a" * 31, False, "Too long"),
        ("user@name", False, "Contains @ symbol"),
        ("user name", False, "Contains space"),
        ("admin", False, "Reserved username"),
        ("root", False, "Reserved username"),
        ("../../etc", False, "Path traversal attempt"),
    ]
    
    for username, should_pass, description in username_cases:
        print(f"Testing: {description} - '{username}'")
        
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": "test@example.com",
                "username": username,
                "password": "ValidPass123!"
            }
        )
        
        print(f"  Status: {response.status_code}")
        
        if should_pass and response.status_code != 422:
            print("  ✅ Valid username accepted")
        elif not should_pass and response.status_code == 422:
            print("  ✅ Invalid username rejected")
        else:
            print(f"  ❌ Unexpected result for {description}")

def test_request_size_limits():
    """Test request size validation."""
    print_section("Testing Request Size Limits")
    
    # Test large request body
    print("Testing large request body...")
    large_data = {
        "description": "x" * (11 * 1024 * 1024)  # 11MB of data
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/content",
            json=large_data,
            timeout=5
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 413:
            print("  ✅ Large request blocked (413 Payload Too Large)")
        else:
            print("  ❌ Large request not blocked properly")
    except requests.exceptions.RequestException as e:
        print(f"  ✅ Request failed as expected: {type(e).__name__}")

def test_header_injection():
    """Test header injection prevention."""
    print_section("Testing Header Injection Prevention")
    
    headers_cases = [
        {
            "name": "SQL injection in User-Agent",
            "headers": {
                "User-Agent": "Mozilla/5.0'; DROP TABLE users; --"
            }
        },
        {
            "name": "XSS in Referer",
            "headers": {
                "Referer": "<script>alert('XSS')</script>"
            }
        },
        {
            "name": "CRLF injection",
            "headers": {
                "X-Custom": "value\r\nX-Injected: malicious"
            }
        }
    ]
    
    for test_case in headers_cases:
        print(f"Testing: {test_case['name']}")
        
        response = requests.get(
            f"{BASE_URL}/health",
            headers=test_case['headers']
        )
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 422]:
            print("  ✅ Header injection blocked")
        else:
            print("  ⚠️  Header might not be validated")

def test_path_traversal():
    """Test path traversal prevention."""
    print_section("Testing Path Traversal Prevention")
    
    path_cases = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "....//....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    ]
    
    for path in path_cases:
        print(f"Testing: {path}")
        
        response = requests.get(f"{BASE_URL}/files/{path}")
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code in [400, 404]:
            print("  ✅ Path traversal blocked")
        else:
            print("  ❌ Path traversal might not be blocked!")

if __name__ == "__main__":
    print(f"\n🚀 Testing Input Validation Implementation")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test all validation categories
        test_sql_injection_prevention()
        test_xss_prevention()
        test_email_validation()
        test_password_validation()
        test_username_validation()
        test_request_size_limits()
        test_header_injection()
        test_path_traversal()
        
        print("\n✅ All validation tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the backend")
        print("   Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")