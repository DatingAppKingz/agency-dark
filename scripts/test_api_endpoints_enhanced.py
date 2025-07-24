#!/usr/bin/env python3
"""
Enhanced test script for AgencyDark API endpoints
Includes proper query parameters and role-based testing
"""

import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.users = {}
        self.current_user = None
        
    def print_result(self, endpoint: str, method: str, status: int, response: Dict[str, Any], error: Optional[str] = None):
        """Print test result in a formatted way"""
        status_emoji = "✅" if 200 <= status < 300 else "❌"
        print(f"\n{status_emoji} {method} {endpoint}")
        print(f"   Status: {status}")
        if error:
            print(f"   Error: {error}")
        elif response:
            response_str = json.dumps(response, indent=2)[:200]
            if len(json.dumps(response)) > 200:
                response_str += "..."
            print(f"   Response: {response_str}")
            
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login with email and password"""
        data = {
            "email": email,
            "password": password
        }
        response = self.session.post(f"{BASE_URL}/auth/login", json=data)
        if response.status_code == 200:
            result = response.json()
            self.session.headers["Authorization"] = f"Bearer {result['access_token']}"
            self.current_user = email
            return result
        else:
            print(f"❌ Login failed for {email}: {response.text}")
            return {}
            
    def test_endpoint(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None, expected_status: int = 200) -> Dict[str, Any]:
        """Test a single endpoint"""
        url = f"{BASE_URL}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, params=params)
            elif method == "POST":
                response = self.session.post(url, json=data, params=params)
            elif method == "PUT":
                response = self.session.put(url, json=data, params=params)
            elif method == "DELETE":
                response = self.session.delete(url, params=params)
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
        """Run all API tests with proper parameters"""
        print("=" * 80)
        print("🧪 AgencyDark API Endpoint Testing (Enhanced)")
        print("=" * 80)
        
        # Test 1: Health endpoint
        print("\n### 1. HEALTH CHECK ###")
        health_response = requests.get("http://localhost:8000/health")
        self.print_result("/health", "GET", health_response.status_code, health_response.json())
        
        # Test 2: Login with different users
        print("\n### 2. AUTHENTICATION - LOGIN MULTIPLE USERS ###")
        test_users = [
            ("owner@testagency.com", "AgencyOwner123!"),
            ("model@testagency.com", "ModelUser123!"),
        ]
        
        for email, password in test_users:
            print(f"\n--- Logging in as: {email} ---")
            login_result = self.login(email, password)
            if "access_token" in login_result:
                self.users[email] = login_result
                
        # Use model user for testing (they have access to more endpoints)
        if "model@testagency.com" in self.users:
            model_data = self.users["model@testagency.com"]
            self.session.headers["Authorization"] = f"Bearer {model_data['access_token']}"
            print(f"\n🔑 Using MODEL user for testing")
        
        # Test 3: Get current user info
        print("\n### 3. AUTHENTICATION - ME ###")
        me_response = self.test_endpoint("GET", "/auth/me")
        user_id = me_response.get("id")
        agency_id = me_response.get("agency_id")
        
        # Test 4: Analytics with proper date parameters
        print("\n### 4. ANALYTICS (with date parameters) ###")
        if user_id:
            # Dashboard endpoint
            self.test_endpoint("GET", f"/analytics/dashboard/{user_id}")
            
            # Categories with date range
            start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            end_date = datetime.utcnow().isoformat()
            self.test_endpoint("GET", f"/analytics/categories/{user_id}", 
                             params={"period_start": start_date, "period_end": end_date})
            
            # Charts with proper parameters
            chart_params = {
                "model_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
                "interval": "day"
            }
            self.test_endpoint("POST", "/analytics/charts/subscriber-growth", 
                             params={"model_id": user_id}, 
                             data={"start_date": start_date, "end_date": end_date})
            
        # Test 5: Financial endpoints
        print("\n### 5. FINANCIAL ###")
        self.test_endpoint("GET", "/financial/payouts")
        self.test_endpoint("GET", "/financial/invoices")
        self.test_endpoint("GET", "/financial/commission/rules")
        
        # Test 6: API Orchestration
        print("\n### 6. API ORCHESTRATION ###")
        if user_id:
            self.test_endpoint("GET", f"/orchestration/fans/{user_id}")
            self.test_endpoint("GET", f"/orchestration/sync/{user_id}/status")
            self.test_endpoint("GET", f"/orchestration/analytics/{user_id}", 
                             params={"start_date": start_date, "end_date": end_date})
            self.test_endpoint("GET", f"/orchestration/messages/{user_id}")
            
        # Test 7: White-label
        print("\n### 7. WHITE-LABEL ###")
        self.test_endpoint("GET", "/whitelabel/theme")
        self.test_endpoint("GET", "/whitelabel/profile")
        self.test_endpoint("GET", "/whitelabel/config")
        self.test_endpoint("GET", "/whitelabel/assets")
        self.test_endpoint("GET", "/whitelabel/theme/presets")
        self.test_endpoint("GET", "/whitelabel/emails/templates")
        
        # Test 8: Integrations (requires MODEL role)
        print("\n### 8. INTEGRATIONS ###")
        if user_id:
            # Inflow
            self.test_endpoint("POST", f"/integrations/inflow/test-connection/{user_id}", data={})
            self.test_endpoint("GET", f"/integrations/inflow/models/{user_id}/analytics",
                             params={"start_date": start_date, "end_date": end_date})
            
            # OnlyFans
            self.test_endpoint("GET", f"/integrations/onlyfans/profile/{user_id}")
            self.test_endpoint("GET", f"/integrations/onlyfans/fans/{user_id}")
            
        # Test 9: Test with Agency Owner for admin endpoints
        print("\n### 9. ADMIN ENDPOINTS (Agency Owner) ###")
        if "owner@testagency.com" in self.users:
            owner_data = self.users["owner@testagency.com"]
            self.session.headers["Authorization"] = f"Bearer {owner_data['access_token']}"
            print("🔑 Switched to AGENCY OWNER user")
            
            # Financial admin endpoints
            self.test_endpoint("POST", "/financial/commission/rules", data={
                "name": "Test Rule",
                "tier": "CUSTOM",
                "percentage": 75.0,
                "min_subscribers": 0,
                "max_subscribers": 1000
            })
            
            # Create billing cycle
            self.test_endpoint("POST", "/financial/billing-cycles", data={
                "start_date": start_date,
                "end_date": end_date
            })
            
        print("\n" + "=" * 80)
        print("✅ Enhanced API Testing Complete!")
        print("=" * 80)
        
        # Summary
        print("\n📊 Test Summary:")
        print(f"- Tested with {len(self.users)} different user roles")
        print("- All endpoints tested with proper query parameters")
        print("- Date ranges and required fields included")
        
if __name__ == "__main__":
    tester = APITester()
    tester.run_tests()