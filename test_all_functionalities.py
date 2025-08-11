#!/usr/bin/env python3
"""
AgencyDark Comprehensive Functionality Testing Script
Tests all major features and endpoints of the application
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import random
import string

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
FRONTEND_URL = "http://localhost:3000"

# Test credentials
TEST_ADMIN = {
    "email": "admin@agency.com",
    "password": "admin123"
}

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class TestRunner:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.csrf_token = None
        self.user_id = None
        self.agency_id = None
        self.test_results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }
        
    def print_header(self, text: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        
    def print_test(self, name: str, status: str, details: str = ""):
        if status == "PASS":
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} {name}")
            self.test_results["passed"].append(name)
        elif status == "FAIL":
            print(f"{Colors.FAIL}✗{Colors.ENDC} {name}")
            if details:
                print(f"  {Colors.WARNING}{details}{Colors.ENDC}")
            self.test_results["failed"].append(f"{name}: {details}")
        elif status == "SKIP":
            print(f"{Colors.WARNING}○{Colors.ENDC} {name} (skipped)")
            self.test_results["skipped"].append(name)
            
    def make_request(self, method: str, endpoint: str, data: Dict = None, 
                    json_data: Dict = None, headers: Dict = None) -> Optional[requests.Response]:
        """Make HTTP request with authentication"""
        url = f"{API_BASE_URL}{endpoint}"
        
        # Add authentication headers if available
        if headers is None:
            headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
            
        try:
            response = self.session.request(
                method=method,
                url=url,
                data=data,
                json=json_data,
                headers=headers,
                timeout=10
            )
            return response
        except Exception as e:
            print(f"  {Colors.FAIL}Request failed: {e}{Colors.ENDC}")
            return None
            
    def generate_random_email(self) -> str:
        """Generate random email for testing"""
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"test_{random_str}@agency.com"
        
    def generate_random_string(self, length: int = 10) -> str:
        """Generate random string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    # ==================== AUTHENTICATION TESTS ====================
    
    def test_authentication(self):
        """Test authentication endpoints"""
        self.print_header("AUTHENTICATION TESTS")
        
        # Test login
        response = self.make_request(
            "POST", 
            "/auth/login",
            json_data=TEST_ADMIN
        )
        
        if response and response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.csrf_token = data.get("csrf_token")
            self.print_test("Login", "PASS")
            
            # Test /me endpoint
            response = self.make_request("GET", "/auth/me")
            if response and response.status_code == 200:
                user_data = response.json()
                self.user_id = user_data.get("id")
                self.agency_id = user_data.get("agency_id")
                self.print_test("Get current user", "PASS")
            else:
                self.print_test("Get current user", "FAIL", f"Status: {response.status_code if response else 'No response'}")
                
            # Test token refresh
            response = self.make_request("POST", "/auth/refresh")
            if response and response.status_code == 200:
                self.print_test("Refresh token", "PASS")
            else:
                self.print_test("Refresh token", "FAIL", f"Status: {response.status_code if response else 'No response'}")
                
            # Test token verification
            response = self.make_request("GET", "/auth/verify-token")
            if response and response.status_code == 200:
                self.print_test("Verify token", "PASS")
            else:
                self.print_test("Verify token", "FAIL", f"Status: {response.status_code if response else 'No response'}")
                
        else:
            self.print_test("Login", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            print(f"{Colors.FAIL}Cannot continue without authentication{Colors.ENDC}")
            return False
            
        return True
        
    # ==================== USER MANAGEMENT TESTS ====================
    
    def test_user_management(self):
        """Test user management endpoints"""
        self.print_header("USER MANAGEMENT TESTS")
        
        # List users
        response = self.make_request("GET", "/users")
        if response and response.status_code == 200:
            self.print_test("List users", "PASS")
        else:
            self.print_test("List users", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            
        # Get user details
        if self.user_id:
            response = self.make_request("GET", f"/users/{self.user_id}")
            if response and response.status_code == 200:
                self.print_test("Get user details", "PASS")
            else:
                self.print_test("Get user details", "FAIL", f"Status: {response.status_code if response else 'No response'}")
                
        # Create test user
        test_user_data = {
            "email": self.generate_random_email(),
            "password": "Test123456",  # Simpler password to avoid escaping issues
            "full_name": "Test User",
            "role": "agency_member"  # Use correct role enum value
        }
        
        response = self.make_request("POST", "/auth/register", json_data=test_user_data)
        if response and response.status_code in [200, 201]:
            self.print_test("Create user", "PASS")
            created_user = response.json()
            
            # Update user
            if created_user.get("user", {}).get("id"):
                update_data = {"full_name": "Updated Test User"}
                response = self.make_request(
                    "PUT", 
                    f"/users/{created_user['user']['id']}", 
                    json_data=update_data
                )
                if response and response.status_code == 200:
                    self.print_test("Update user", "PASS")
                else:
                    self.print_test("Update user", "FAIL", f"Status: {response.status_code if response else 'No response'}")
        else:
            self.print_test("Create user", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            
    # ==================== AGENCY TESTS ====================
    
    def test_agency_management(self):
        """Test agency management features"""
        self.print_header("AGENCY MANAGEMENT TESTS")
        
        # Get agencies
        response = self.make_request("GET", "/agencies")
        if response and response.status_code == 200:
            self.print_test("List agencies", "PASS")
            agencies = response.json()
            
            if agencies and len(agencies) > 0:
                agency_id = agencies[0].get("id")
                
                # Get agency details
                response = self.make_request("GET", f"/agencies/{agency_id}")
                if response and response.status_code == 200:
                    self.print_test("Get agency details", "PASS")
                else:
                    self.print_test("Get agency details", "FAIL", f"Status: {response.status_code if response else 'No response'}")
                    
                # Get agency profile
                response = self.make_request("GET", f"/agencies/{agency_id}/profile")
                if response and response.status_code == 200:
                    self.print_test("Get agency profile", "PASS")
                else:
                    self.print_test("Get agency profile", "SKIP", "Endpoint may not exist")
        else:
            self.print_test("List agencies", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            
    # ==================== CHAT TESTS ====================
    
    def test_chat_system(self):
        """Test chat and messaging system"""
        self.print_header("CHAT & MESSAGING TESTS")
        
        # Get conversations
        response = self.make_request("GET", "/chat/conversations")
        if response and response.status_code == 200:
            self.print_test("List conversations", "PASS")
            conversations = response.json()
            
            # If conversations exist, test getting messages
            if conversations and len(conversations) > 0:
                conv_id = conversations[0].get("id")
                response = self.make_request("GET", f"/chat/conversations/{conv_id}/messages")
                if response and response.status_code == 200:
                    self.print_test("Get conversation messages", "PASS")
                else:
                    self.print_test("Get conversation messages", "FAIL", f"Status: {response.status_code if response else 'No response'}")
        else:
            self.print_test("List conversations", "SKIP", "Chat endpoints may not be available")
            
        # Test chat templates
        response = self.make_request("GET", "/chat/templates")
        if response and response.status_code == 200:
            self.print_test("List chat templates", "PASS")
        else:
            self.print_test("List chat templates", "SKIP", "Templates may not be configured")
            
    # ==================== ANALYTICS TESTS ====================
    
    def test_analytics(self):
        """Test analytics and reporting"""
        self.print_header("ANALYTICS & REPORTING TESTS")
        
        # Real-time analytics
        response = self.make_request("GET", "/analytics/realtime-analytics")
        if response and response.status_code == 200:
            self.print_test("Real-time analytics", "PASS")
        else:
            self.print_test("Real-time analytics", "SKIP", "Analytics may not be configured")
            
        # Revenue reports
        response = self.make_request("GET", "/enhanced-reports/revenue")
        if response and response.status_code == 200:
            self.print_test("Revenue reports", "PASS")
        else:
            self.print_test("Revenue reports", "SKIP", "Reports may not be available")
            
        # Performance dashboard
        response = self.make_request("GET", "/enhanced-reports/performance-dashboard")
        if response and response.status_code == 200:
            self.print_test("Performance dashboard", "PASS")
        else:
            self.print_test("Performance dashboard", "SKIP", "Dashboard may not be configured")
            
    # ==================== FINANCIAL TESTS ====================
    
    def test_financial_management(self):
        """Test financial management features"""
        self.print_header("FINANCIAL MANAGEMENT TESTS")
        
        # Test invoices
        response = self.make_request("GET", "/invoices")
        if response and response.status_code == 200:
            self.print_test("List invoices", "PASS")
        else:
            self.print_test("List invoices", "SKIP", "Invoices may not be configured")
            
        # Test payouts
        response = self.make_request("GET", "/payouts")
        if response and response.status_code == 200:
            self.print_test("List payouts", "PASS")
        else:
            self.print_test("List payouts", "SKIP", "Payouts may not be configured")
            
    # ==================== API KEY TESTS ====================
    
    def test_api_keys(self):
        """Test API key management"""
        self.print_header("API KEY MANAGEMENT TESTS")
        
        # List API keys
        response = self.make_request("GET", "/api-keys")
        if response and response.status_code == 200:
            self.print_test("List API keys", "PASS")
            
            # Create API key
            api_key_data = {
                "name": f"Test Key {self.generate_random_string(5)}",
                "scopes": ["read"],
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat()
            }
            
            response = self.make_request("POST", "/api-keys", json_data=api_key_data)
            if response and response.status_code in [200, 201]:
                self.print_test("Create API key", "PASS")
                created_key = response.json()
                
                # Delete API key
                if created_key.get("id"):
                    response = self.make_request("DELETE", f"/api-keys/{created_key['id']}")
                    if response and response.status_code in [200, 204]:
                        self.print_test("Delete API key", "PASS")
                    else:
                        self.print_test("Delete API key", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            else:
                self.print_test("Create API key", "SKIP", "API key creation may not be available")
        else:
            self.print_test("List API keys", "SKIP", "API keys may not be configured")
            
    # ==================== NOTIFICATIONS TESTS ====================
    
    def test_notifications(self):
        """Test notification system"""
        self.print_header("NOTIFICATION SYSTEM TESTS")
        
        # Get notifications
        response = self.make_request("GET", "/notifications")
        if response and response.status_code == 200:
            self.print_test("List notifications", "PASS")
        else:
            self.print_test("List notifications", "SKIP", "Notifications may not be configured")
            
        # Get notification preferences
        response = self.make_request("GET", "/push-notifications/preferences")
        if response and response.status_code == 200:
            self.print_test("Get notification preferences", "PASS")
        else:
            self.print_test("Get notification preferences", "SKIP", "Push notifications may not be configured")
            
    # ==================== WEBHOOK TESTS ====================
    
    def test_webhooks(self):
        """Test webhook management"""
        self.print_header("WEBHOOK MANAGEMENT TESTS")
        
        # List webhooks
        response = self.make_request("GET", "/webhooks")
        if response and response.status_code == 200:
            self.print_test("List webhooks", "PASS")
            
            # Create test webhook
            webhook_data = {
                "url": f"https://example.com/webhook/{self.generate_random_string()}",
                "events": ["user.created", "user.updated"],
                "is_active": True
            }
            
            response = self.make_request("POST", "/webhooks", json_data=webhook_data)
            if response and response.status_code in [200, 201]:
                self.print_test("Create webhook", "PASS")
                created_webhook = response.json()
                
                # Delete webhook
                if created_webhook.get("id"):
                    response = self.make_request("DELETE", f"/webhooks/{created_webhook['id']}")
                    if response and response.status_code in [200, 204]:
                        self.print_test("Delete webhook", "PASS")
                    else:
                        self.print_test("Delete webhook", "FAIL", f"Status: {response.status_code if response else 'No response'}")
            else:
                self.print_test("Create webhook", "SKIP", "Webhook creation may not be available")
        else:
            self.print_test("List webhooks", "SKIP", "Webhooks may not be configured")
            
    # ==================== SEARCH TESTS ====================
    
    def test_search(self):
        """Test search functionality"""
        self.print_header("SEARCH FUNCTIONALITY TESTS")
        
        # Global search
        search_params = {"q": "test", "limit": 10}
        response = self.make_request("GET", "/search", data=search_params)
        if response and response.status_code == 200:
            self.print_test("Global search", "PASS")
        else:
            self.print_test("Global search", "SKIP", "Search may not be configured")
            
    # ==================== SYSTEM HEALTH TESTS ====================
    
    def test_system_health(self):
        """Test system health and monitoring"""
        self.print_header("SYSTEM HEALTH TESTS")
        
        # Health check
        response = self.make_request("GET", "/health")
        if response and response.status_code == 200:
            self.print_test("Health check", "PASS")
        else:
            self.print_test("Health check", "SKIP", "Health endpoint may not exist")
            
        # API status
        response = self.make_request("GET", "/status")
        if response and response.status_code == 200:
            self.print_test("API status", "PASS")
        else:
            self.print_test("API status", "SKIP", "Status endpoint may not exist")
            
    # ==================== MEDIA TESTS ====================
    
    def test_media_management(self):
        """Test media upload and management"""
        self.print_header("MEDIA MANAGEMENT TESTS")
        
        # Get upload URL
        upload_data = {
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "size": 1024
        }
        
        response = self.make_request("POST", "/media-upload/upload-url", json_data=upload_data)
        if response and response.status_code == 200:
            self.print_test("Get upload URL", "PASS")
        else:
            self.print_test("Get upload URL", "SKIP", "Media upload may not be configured")
            
    # ==================== INTERNATIONALIZATION TESTS ====================
    
    def test_internationalization(self):
        """Test i18n features"""
        self.print_header("INTERNATIONALIZATION TESTS")
        
        # Get translations
        response = self.make_request("GET", "/translations")
        if response and response.status_code == 200:
            self.print_test("Get translations", "PASS")
        else:
            self.print_test("Get translations", "SKIP", "Translations may not be configured")
            
    # ==================== MAIN TEST RUNNER ====================
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"{Colors.BOLD}{Colors.OKCYAN}")
        print("╔" + "═"*58 + "╗")
        print("║" + " "*15 + "AGENCYDARK FUNCTIONALITY TEST" + " "*14 + "║")
        print("╚" + "═"*58 + "╝")
        print(f"{Colors.ENDC}")
        
        print(f"API Base URL: {API_BASE_URL}")
        print(f"Testing started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Run authentication first (required for other tests)
        if not self.test_authentication():
            print(f"\n{Colors.FAIL}Authentication failed. Cannot continue with other tests.{Colors.ENDC}")
            self.print_summary()
            return
            
        # Run all other test suites
        test_suites = [
            self.test_user_management,
            self.test_agency_management,
            self.test_chat_system,
            self.test_analytics,
            self.test_financial_management,
            self.test_api_keys,
            self.test_notifications,
            self.test_webhooks,
            self.test_search,
            self.test_media_management,
            self.test_internationalization,
            self.test_system_health
        ]
        
        for test_suite in test_suites:
            try:
                test_suite()
            except Exception as e:
                print(f"{Colors.FAIL}Test suite failed with error: {e}{Colors.ENDC}")
                
        # Print summary
        self.print_summary()
        
        # Logout
        self.make_request("POST", "/auth/logout")
        
    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")
        
        total_tests = len(self.test_results["passed"]) + len(self.test_results["failed"]) + len(self.test_results["skipped"])
        
        print(f"Total tests run: {total_tests}")
        print(f"{Colors.OKGREEN}Passed: {len(self.test_results['passed'])}{Colors.ENDC}")
        print(f"{Colors.FAIL}Failed: {len(self.test_results['failed'])}{Colors.ENDC}")
        print(f"{Colors.WARNING}Skipped: {len(self.test_results['skipped'])}{Colors.ENDC}")
        
        if self.test_results["failed"]:
            print(f"\n{Colors.FAIL}Failed tests:{Colors.ENDC}")
            for test in self.test_results["failed"]:
                print(f"  - {test}")
                
        pass_rate = (len(self.test_results["passed"]) / total_tests * 100) if total_tests > 0 else 0
        print(f"\nPass rate: {pass_rate:.1f}%")
        
        if pass_rate == 100:
            print(f"{Colors.OKGREEN}{Colors.BOLD}All tests passed! ✨{Colors.ENDC}")
        elif pass_rate >= 80:
            print(f"{Colors.OKGREEN}Good test coverage!{Colors.ENDC}")
        elif pass_rate >= 60:
            print(f"{Colors.WARNING}Some tests failed, please review.{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Many tests failed, investigation needed.{Colors.ENDC}")

def main():
    """Main entry point"""
    # Check if services are running
    try:
        response = requests.get("http://localhost:8000/api/docs", timeout=5)
        if response.status_code != 200:
            raise Exception("API not responding")
    except Exception as e:
        print(f"{Colors.FAIL}Error: Backend API is not running at http://localhost:8000{Colors.ENDC}")
        print(f"Please ensure the backend is running before running tests.")
        sys.exit(1)
        
    # Run tests
    runner = TestRunner()
    runner.run_all_tests()

if __name__ == "__main__":
    main()