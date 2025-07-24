#!/usr/bin/env python3
"""
Test script for AgencyDark API endpoints
Tests authentication flow and all major endpoints
"""

import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.agency_id = None
        self.user_id = None
        
    def print_result(self, endpoint: str, method: str, status: int, response: Dict[str, Any], error: Optional[str] = None):
        """Print test result in a formatted way"""
        status_emoji = "✅" if 200 <= status < 300 else "❌"
        print(f"\n{status_emoji} {method} {endpoint}")
        print(f"   Status: {status}")
        if error:
            print(f"   Error: {error}")
        elif response:
            print(f"   Response: {json.dumps(response, indent=2)[:200]}...")
            
    def test_endpoint(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     use_auth: bool = True, expected_status: int = 200) -> Dict[str, Any]:
        """Test a single endpoint"""
        url = f"{BASE_URL}{endpoint}"
        headers = {}
        
        if use_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers)
            elif method == "POST":
                headers["Content-Type"] = "application/json"
                response = self.session.post(url, json=data, headers=headers)
            elif method == "PUT":
                headers["Content-Type"] = "application/json"
                response = self.session.put(url, json=data, headers=headers)
            elif method == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            try:
                response_data = response.json()
            except:
                response_data = {"text": response.text}
                
            self.print_result(endpoint, method, response.status_code, response_data)
            
            if response.status_code != expected_status:
                print(f"   ⚠️  Expected status {expected_status}, got {response.status_code}")
                
            return response_data
            
        except Exception as e:
            self.print_result(endpoint, method, 0, {}, str(e))
            return {}
            
    def run_tests(self):
        """Run all API tests"""
        print("=" * 80)
        print("🧪 AgencyDark API Endpoint Testing")
        print("=" * 80)
        
        # Test 1: Health endpoint (no auth) - this is at root level
        print("\n### 1. HEALTH CHECK ###")
        health_response = requests.get("http://localhost:8000/health")
        self.print_result("/health", "GET", health_response.status_code, health_response.json())
        
        # Test 2: Register new agency
        print("\n### 2. AUTHENTICATION - REGISTER ###")
        register_data = {
            "email": "test@agency.com",
            "password": "TestPassword123!",
            "full_name": "Test Agency Owner",
            "agency_name": "Test Agency",
            "agency_domain": "testagency.com"
        }
        register_response = self.test_endpoint("POST", "/auth/register", register_data, use_auth=False)
        
        # Test 3: Login
        print("\n### 3. AUTHENTICATION - LOGIN ###")
        login_data = {
            "email": "test@agency.com",
            "password": "TestPassword123!"
        }
        login_response = self.test_endpoint("POST", "/auth/login", login_data, use_auth=False)
        
        if "access_token" in login_response:
            self.access_token = login_response["access_token"]
            self.refresh_token = login_response.get("refresh_token")
            print(f"   🔑 Access token obtained: {self.access_token[:20]}...")
            
        # Test 4: Get current user
        print("\n### 4. AUTHENTICATION - ME ###")
        me_response = self.test_endpoint("GET", "/auth/me")
        if "id" in me_response:
            self.user_id = me_response["id"]
            self.agency_id = me_response.get("agency_id")
            
        # Test 5: Refresh token
        print("\n### 5. AUTHENTICATION - REFRESH ###")
        if self.refresh_token:
            refresh_data = {"refresh_token": self.refresh_token}
            self.test_endpoint("POST", "/auth/refresh", refresh_data, use_auth=False)
            
        # Test 6: Analytics endpoints
        print("\n### 6. ANALYTICS ###")
        if self.user_id:
            self.test_endpoint("GET", f"/analytics/dashboard/{self.user_id}")
            self.test_endpoint("GET", f"/analytics/categories/{self.user_id}")
            self.test_endpoint("POST", "/analytics/charts/subscriber-growth", {"model_id": self.user_id})
        
        # Test 7: Financial endpoints
        print("\n### 7. FINANCIAL ###")
        self.test_endpoint("GET", "/financial/payouts")
        self.test_endpoint("GET", "/financial/invoices")
        self.test_endpoint("GET", "/financial/commission/rules")
        
        # Test 8: API Orchestration (includes fan data)
        print("\n### 8. API ORCHESTRATION ###")
        if self.user_id:
            self.test_endpoint("GET", f"/orchestration/fans/{self.user_id}")
            self.test_endpoint("GET", f"/orchestration/sync/{self.user_id}/status")
            self.test_endpoint("GET", f"/orchestration/analytics/{self.user_id}")
        
        # Test 9: White-label configuration
        print("\n### 9. WHITE-LABEL ###")
        self.test_endpoint("GET", "/whitelabel/theme")
        self.test_endpoint("GET", "/whitelabel/profile")
        self.test_endpoint("GET", "/whitelabel/config")
            
        # Test 10: Integrations - Inflow
        print("\n### 10. INFLOW INTEGRATION ###")
        if self.user_id:
            self.test_endpoint("POST", f"/integrations/inflow/test-connection/{self.user_id}", {})
            self.test_endpoint("GET", f"/integrations/inflow/models/{self.user_id}/analytics")
        
        # Test 11: Integrations - OnlyFans
        print("\n### 11. ONLYFANS INTEGRATION ###")
        if self.user_id:
            self.test_endpoint("GET", f"/integrations/onlyfans/profile/{self.user_id}")
            self.test_endpoint("GET", f"/integrations/onlyfans/fans/{self.user_id}")
        
        # Test 12: Orchestration - Messages
        print("\n### 12. MESSAGES ORCHESTRATION ###")
        if self.user_id:
            self.test_endpoint("GET", f"/orchestration/messages/{self.user_id}")
            self.test_endpoint("POST", "/orchestration/messages/send", {"model_id": self.user_id, "fan_id": "test_fan", "content": "Test message"})
        
        # Test 13: Webhooks
        print("\n### 13. WEBHOOKS ###")
        if self.user_id:
            webhook_data = {"event": "test", "data": {}}
            self.test_endpoint("POST", f"/webhooks/inflow/{self.user_id}", webhook_data)
            self.test_endpoint("POST", f"/webhooks/onlyfans/{self.user_id}", webhook_data)
        
        # Test 14: White Label - Assets
        print("\n### 14. WHITE LABEL ASSETS ###")
        self.test_endpoint("GET", "/whitelabel/assets")
        self.test_endpoint("GET", "/whitelabel/theme/presets")
        self.test_endpoint("GET", "/whitelabel/emails/templates")
        
        # Test 15: API Documentation
        print("\n### 15. API DOCUMENTATION ###")
        docs_response = requests.get("http://localhost:8000/api/docs")
        self.print_result("/api/docs", "GET", docs_response.status_code, {"text": "Swagger UI available" if docs_response.status_code == 200 else "Not available"})
        
        print("\n" + "=" * 80)
        print("✅ API Testing Complete!")
        print("=" * 80)
        
if __name__ == "__main__":
    tester = APITester()
    tester.run_tests()