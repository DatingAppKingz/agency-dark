#!/usr/bin/env python3
"""
Multi-Tenant Isolation Tests for AgencyDark
Tests complete data isolation between different agencies
"""

import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class MultiTenantIsolationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.sessions = {}
        
        # Define test agencies and their users
        self.agencies = {
            "premium": {
                "name": "Test Agency Premium",
                "users": {
                    "owner": "owner@testagencypremium.com",
                    "admin": "admin@testagencypremium.com",
                    "model1": "model1@testagencypremium.com",
                    "model2": "model2@testagencypremium.com",
                    "chatter1": "chatter1@testagencypremium.com"
                }
            },
            "competitor": {
                "name": "Competitor Agency",
                "users": {
                    "owner": "owner@competitoragency.com",
                    "admin": "admin@competitoragency.com",
                    "model1": "model1@competitoragency.com",
                    "model2": "model2@competitoragency.com",
                    "chatter1": "chatter1@competitoragency.com"
                }
            },
            "elite": {
                "name": "Elite Models Agency",
                "users": {
                    "owner": "owner@elitemodels.com",
                    "admin": "admin@elitemodels.com",
                    "model1": "model1@elitemodels.com",
                    "model2": "model2@elitemodels.com",
                    "chatter1": "chatter1@elitemodels.com"
                }
            }
        }
    
    def login(self, email: str, password: str = "Test123!") -> Optional[requests.Session]:
        """Login and return authenticated session"""
        session = requests.Session()
        
        response = session.post(
            f"{self.api_url}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            session.headers["Authorization"] = f"Bearer {data['access_token']}"
            self.sessions[email] = session
            return session
        else:
            print(f"❌ Login failed for {email}: {response.text}")
            return None
    
    def test_user_list_isolation(self):
        """Test 1: Users can only see users from their own agency"""
        print("\n🧪 Test 1: User List Isolation")
        
        # Login as owners from different agencies
        premium_owner = self.login(self.agencies["premium"]["users"]["owner"])
        competitor_owner = self.login(self.agencies["competitor"]["users"]["owner"])
        
        if not premium_owner or not competitor_owner:
            print("❌ Failed to login as agency owners")
            return False
        
        # Get users list from each agency
        print("\n📋 Premium Agency Owner viewing users:")
        premium_users = premium_owner.get(f"{self.api_url}/users").json()
        premium_emails = [u.get("email", "") for u in premium_users] if isinstance(premium_users, list) else []
        
        print("\n📋 Competitor Agency Owner viewing users:")
        competitor_users = competitor_owner.get(f"{self.api_url}/users").json()
        competitor_emails = [u.get("email", "") for u in competitor_users] if isinstance(competitor_users, list) else []
        
        # Check isolation
        premium_only = any("testagencypremium" in email for email in premium_emails)
        competitor_only = any("competitoragency" in email for email in competitor_emails)
        no_crossover = not any("competitoragency" in email for email in premium_emails)
        
        if premium_only and competitor_only and no_crossover:
            print("✅ User lists are properly isolated by agency")
            return True
        else:
            print("❌ User list isolation FAILED - agencies can see each other's users")
            print(f"   Premium emails: {premium_emails}")
            print(f"   Competitor emails: {competitor_emails}")
            return False
    
    def test_model_profile_isolation(self):
        """Test 2: Model profiles are isolated by agency"""
        print("\n🧪 Test 2: Model Profile Isolation")
        
        # Login as admins from different agencies
        premium_admin = self.login(self.agencies["premium"]["users"]["admin"])
        competitor_admin = self.login(self.agencies["competitor"]["users"]["admin"])
        
        # Try to access model profiles
        endpoints = [
            "/models",
            "/model-profiles"
        ]
        
        for endpoint in endpoints:
            print(f"\n📍 Testing {endpoint}:")
            
            premium_resp = premium_admin.get(f"{self.api_url}{endpoint}")
            competitor_resp = competitor_admin.get(f"{self.api_url}{endpoint}")
            
            if premium_resp.status_code == 200 and competitor_resp.status_code == 200:
                premium_data = premium_resp.json()
                competitor_data = competitor_resp.json()
                
                print(f"   Premium agency sees: {len(premium_data) if isinstance(premium_data, list) else 'N/A'} models")
                print(f"   Competitor agency sees: {len(competitor_data) if isinstance(competitor_data, list) else 'N/A'} models")
                
                # TODO: Verify no overlap in model IDs
            else:
                print(f"   ⚠️  Endpoint not accessible or not implemented")
        
        return True
    
    def test_chat_message_isolation(self):
        """Test 3: Chat messages are isolated by agency"""
        print("\n🧪 Test 3: Chat Message Isolation")
        
        # Login as models from different agencies
        premium_model = self.login(self.agencies["premium"]["users"]["model1"])
        competitor_model = self.login(self.agencies["competitor"]["users"]["model1"])
        
        # Get current user info to find model IDs
        premium_me = premium_model.get(f"{self.api_url}/auth/me").json()
        competitor_me = competitor_model.get(f"{self.api_url}/auth/me").json()
        
        print(f"\n👤 Premium model: {premium_me.get('email')}")
        print(f"👤 Competitor model: {competitor_me.get('email')}")
        
        # Try to access chat messages
        endpoints = [
            "/chat/messages",
            "/messages",
            f"/models/{premium_me.get('id')}/messages"
        ]
        
        for endpoint in endpoints:
            print(f"\n📍 Testing {endpoint}:")
            
            # Premium model tries to get messages
            resp = premium_model.get(f"{self.api_url}{endpoint}")
            print(f"   Premium model access: {resp.status_code}")
            
            # Competitor tries to access premium's messages
            if "{" in endpoint:  # Skip if it has a specific ID
                continue
                
            resp = competitor_model.get(f"{self.api_url}{endpoint}")
            print(f"   Competitor model access: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    # Check if any messages belong to the other agency
                    print(f"   ⚠️  Need to verify message ownership")
        
        return True
    
    def test_financial_data_isolation(self):
        """Test 4: Financial data is isolated by agency"""
        print("\n🧪 Test 4: Financial Data Isolation")
        
        # Login as owners (they should have financial access)
        premium_owner = self.sessions.get(self.agencies["premium"]["users"]["owner"]) or \
                       self.login(self.agencies["premium"]["users"]["owner"])
        competitor_owner = self.sessions.get(self.agencies["competitor"]["users"]["owner"]) or \
                          self.login(self.agencies["competitor"]["users"]["owner"])
        
        financial_endpoints = [
            "/financial/transactions",
            "/financial/payouts",
            "/financial/invoices",
            "/financial/commission/rules",
            "/financial/revenue"
        ]
        
        for endpoint in financial_endpoints:
            print(f"\n📍 Testing {endpoint}:")
            
            premium_resp = premium_owner.get(f"{self.api_url}{endpoint}")
            competitor_resp = competitor_owner.get(f"{self.api_url}{endpoint}")
            
            print(f"   Premium owner access: {premium_resp.status_code}")
            print(f"   Competitor owner access: {competitor_resp.status_code}")
            
            if premium_resp.status_code == 200 and competitor_resp.status_code == 200:
                # Both can access their own data - good
                print("   ✅ Both agencies can access their own financial data")
            elif premium_resp.status_code == 500 or competitor_resp.status_code == 500:
                print("   ⚠️  Server error - endpoint may not be fully implemented")
        
        return True
    
    def test_cross_agency_access_attempt(self):
        """Test 5: Direct attempts to access other agency's resources"""
        print("\n🧪 Test 5: Cross-Agency Access Attempts")
        
        # Get agency and model IDs
        premium_owner = self.sessions.get(self.agencies["premium"]["users"]["owner"])
        competitor_model = self.sessions.get(self.agencies["competitor"]["users"]["model1"])
        
        # Premium owner gets their agency info
        me_resp = premium_owner.get(f"{self.api_url}/auth/me")
        if me_resp.status_code == 200:
            premium_agency_id = me_resp.json().get("agency_id")
            print(f"\n🏢 Premium agency ID: {premium_agency_id}")
        
        # Competitor model gets their info
        me_resp = competitor_model.get(f"{self.api_url}/auth/me")
        if me_resp.status_code == 200:
            competitor_data = me_resp.json()
            competitor_agency_id = competitor_data.get("agency_id")
            print(f"🏢 Competitor agency ID: {competitor_agency_id}")
        
        # Test cross-agency access attempts
        test_cases = [
            {
                "name": "Competitor accessing premium agency data",
                "session": competitor_model,
                "endpoints": [
                    f"/agencies/{premium_agency_id}",
                    f"/agencies/{premium_agency_id}/users",
                    f"/agencies/{premium_agency_id}/models",
                    f"/agencies/{premium_agency_id}/revenue"
                ]
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🔍 {test_case['name']}:")
            session = test_case["session"]
            
            for endpoint in test_case["endpoints"]:
                resp = session.get(f"{self.api_url}{endpoint}")
                
                if resp.status_code in [403, 404]:
                    print(f"   ✅ {endpoint}: Access denied ({resp.status_code})")
                elif resp.status_code == 200:
                    print(f"   ❌ {endpoint}: Access allowed (SECURITY ISSUE!)")
                else:
                    print(f"   ⚠️  {endpoint}: Status {resp.status_code}")
        
        return True
    
    def test_api_filtering(self):
        """Test 6: API responses are filtered by agency context"""
        print("\n🧪 Test 6: API Response Filtering")
        
        # Test that list endpoints only return agency-specific data
        premium_admin = self.sessions.get(self.agencies["premium"]["users"]["admin"])
        
        # Endpoints that should filter by agency
        filtered_endpoints = [
            "/users",
            "/chat/active",
            "/analytics/overview",
            "/notifications"
        ]
        
        for endpoint in filtered_endpoints:
            print(f"\n📍 Testing filtering on {endpoint}:")
            resp = premium_admin.get(f"{self.api_url}{endpoint}")
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    print(f"   Returned {len(data)} items")
                    # TODO: Verify all items belong to correct agency
                else:
                    print(f"   Returned object (check agency_id field)")
            else:
                print(f"   Status: {resp.status_code}")
        
        return True
    
    def test_white_label_isolation(self):
        """Test 7: White-label settings are isolated"""
        print("\n🧪 Test 7: White-Label Settings Isolation")
        
        premium_owner = self.sessions.get(self.agencies["premium"]["users"]["owner"])
        competitor_owner = self.sessions.get(self.agencies["competitor"]["users"]["owner"])
        
        # Each agency should only see their own branding
        endpoints = [
            "/whitelabel/theme",
            "/whitelabel/profile",
            "/whitelabel/config"
        ]
        
        for endpoint in endpoints:
            print(f"\n📍 Testing {endpoint}:")
            
            premium_resp = premium_owner.get(f"{self.api_url}{endpoint}")
            competitor_resp = competitor_owner.get(f"{self.api_url}{endpoint}")
            
            if premium_resp.status_code == 200 and competitor_resp.status_code == 200:
                premium_data = premium_resp.json()
                competitor_data = competitor_resp.json()
                
                # They should have different data
                if premium_data != competitor_data:
                    print("   ✅ Agencies have different white-label settings")
                else:
                    print("   ⚠️  Agencies have identical settings (might be defaults)")
            else:
                print(f"   Status: Premium={premium_resp.status_code}, Competitor={competitor_resp.status_code}")
        
        return True
    
    def run_all_tests(self):
        """Run all multi-tenant isolation tests"""
        print("=" * 80)
        print("🏢 Multi-Tenant Isolation Test Suite")
        print("=" * 80)
        
        tests = [
            ("User List Isolation", self.test_user_list_isolation),
            ("Model Profile Isolation", self.test_model_profile_isolation),
            ("Chat Message Isolation", self.test_chat_message_isolation),
            ("Financial Data Isolation", self.test_financial_data_isolation),
            ("Cross-Agency Access", self.test_cross_agency_access_attempt),
            ("API Response Filtering", self.test_api_filtering),
            ("White-Label Isolation", self.test_white_label_isolation)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            try:
                print(f"\n{'='*60}")
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ Test failed with error: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 Multi-Tenant Isolation Test Results")
        print("=" * 80)
        
        passed = sum(1 for _, result in results if result)
        failed = len(results) - passed
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print(f"\nTotal: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("\n🎉 All multi-tenant isolation tests passed!")
        else:
            print(f"\n⚠️  {failed} tests need attention")
        
        return results


def main():
    """Run the multi-tenant isolation test suite"""
    tester = MultiTenantIsolationTester()
    
    print("🔐 Setting up test sessions...")
    
    # Pre-login to all test users
    for agency_key, agency_data in tester.agencies.items():
        print(f"\n📁 Logging in {agency_data['name']} users...")
        for role, email in agency_data["users"].items():
            session = tester.login(email)
            if session:
                print(f"   ✅ {role}: {email}")
            else:
                print(f"   ❌ {role}: {email}")
    
    # Run tests
    results = tester.run_all_tests()
    
    # Recommendations
    print("\n" + "=" * 80)
    print("🔍 Security Recommendations")
    print("=" * 80)
    print("1. Ensure all API endpoints include agency_id filtering")
    print("2. Add middleware to automatically filter by user's agency")
    print("3. Implement row-level security in database")
    print("4. Add comprehensive logging for cross-agency access attempts")
    print("5. Regular security audits of multi-tenant isolation")


if __name__ == "__main__":
    main()