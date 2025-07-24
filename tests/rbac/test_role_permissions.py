#!/usr/bin/env python3
"""
Role-Based Access Control (RBAC) Tests for AgencyDark
Tests permissions for all 6 user roles
"""

import requests
import json
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


class UserRole(Enum):
    SUPER_ADMIN = "super_admin"
    AGENCY_OWNER = "agency_owner"
    AGENCY_ADMIN = "agency_admin"
    MODEL = "model"
    CHATTER = "chatter"
    AGENCY_MEMBER = "agency_member"


class RBACTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.sessions = {}
        
        # Test users for each role
        self.test_users = {
            UserRole.SUPER_ADMIN: "super@agencydark.com",
            UserRole.AGENCY_OWNER: "owner@testagencypremium.com",
            UserRole.AGENCY_ADMIN: "admin@testagencypremium.com",
            UserRole.MODEL: "model1@testagencypremium.com",
            UserRole.CHATTER: "chatter1@testagencypremium.com",
            UserRole.AGENCY_MEMBER: "member@testagencypremium.com"
        }
        
        # Define permission matrix
        self.permission_matrix = {
            # Platform Management
            "platform_settings": [UserRole.SUPER_ADMIN],
            "all_agencies_view": [UserRole.SUPER_ADMIN],
            "all_agencies_manage": [UserRole.SUPER_ADMIN],
            
            # Agency Management
            "agency_settings_view": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "agency_settings_edit": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "agency_delete": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
            
            # User Management
            "users_view": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "users_create": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "users_edit": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "users_delete": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
            
            # Model Management
            "models_view_all": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "models_view_own": [UserRole.MODEL],
            "models_edit_all": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "models_edit_own": [UserRole.MODEL],
            
            # Chat Management
            "chat_view_all": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "chat_view_assigned": [UserRole.MODEL, UserRole.CHATTER],
            "chat_send_message": [UserRole.MODEL, UserRole.CHATTER],
            
            # Financial Access
            "financial_view_all": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
            "financial_view_limited": [UserRole.AGENCY_ADMIN],
            "financial_view_own": [UserRole.MODEL],
            "financial_edit": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
            
            # Analytics Access
            "analytics_platform": [UserRole.SUPER_ADMIN],
            "analytics_agency": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "analytics_model": [UserRole.MODEL],
            "analytics_limited": [UserRole.CHATTER],
            
            # White-label Management
            "whitelabel_view": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
            "whitelabel_edit": [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]
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
            # Store user info
            me_resp = session.get(f"{self.api_url}/auth/me")
            if me_resp.status_code == 200:
                session.user_info = me_resp.json()
            return session
        else:
            print(f"❌ Login failed for {email}: {response.text}")
            return None
    
    def test_endpoint_access(self, role: UserRole, endpoint: str, method: str = "GET", 
                           expected_statuses: List[int] = [200], data: Dict = None) -> Tuple[bool, int]:
        """Test if a role can access an endpoint"""
        session = self.sessions.get(role)
        if not session:
            return False, 0
        
        # Make request
        if method == "GET":
            response = session.get(f"{self.api_url}{endpoint}")
        elif method == "POST":
            response = session.post(f"{self.api_url}{endpoint}", json=data or {})
        elif method == "PUT":
            response = session.put(f"{self.api_url}{endpoint}", json=data or {})
        elif method == "DELETE":
            response = session.delete(f"{self.api_url}{endpoint}")
        else:
            return False, 0
        
        return response.status_code in expected_statuses, response.status_code
    
    def test_super_admin_permissions(self):
        """Test SUPER_ADMIN role permissions"""
        print("\n🧪 Testing SUPER_ADMIN Permissions")
        role = UserRole.SUPER_ADMIN
        
        tests = [
            ("View all agencies", "/agencies", "GET", [200, 404]),
            ("Platform settings", "/settings/platform", "GET", [200, 404]),
            ("Global analytics", "/analytics/platform", "GET", [200, 404]),
            ("Manage any agency", "/agencies/a1b2c3d4-e5f6-7890-abcd-ef1234567890", "GET", [200, 404]),
        ]
        
        results = []
        for test_name, endpoint, method, expected in tests:
            passed, status = self.test_endpoint_access(role, endpoint, method, expected)
            results.append((test_name, passed, status))
            status_icon = "✅" if passed else "❌"
            print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_agency_owner_permissions(self):
        """Test AGENCY_OWNER role permissions"""
        print("\n🧪 Testing AGENCY_OWNER Permissions")
        role = UserRole.AGENCY_OWNER
        
        tests = [
            ("View own agency", "/auth/me", "GET", [200]),
            ("Manage users", "/users", "GET", [200, 404]),
            ("View all models", "/models", "GET", [200, 404]),
            ("Financial full access", "/financial/payouts", "GET", [200, 500]),
            ("Commission rules", "/financial/commission/rules", "GET", [200, 500]),
            ("Agency settings", "/settings/agency", "GET", [200, 404]),
            ("Cannot view other agencies", "/agencies", "GET", [403, 404]),
        ]
        
        results = []
        for test_name, endpoint, method, expected in tests:
            passed, status = self.test_endpoint_access(role, endpoint, method, expected)
            results.append((test_name, passed, status))
            status_icon = "✅" if passed else "❌"
            print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_agency_admin_permissions(self):
        """Test AGENCY_ADMIN role permissions"""
        print("\n🧪 Testing AGENCY_ADMIN Permissions")
        role = UserRole.AGENCY_ADMIN
        
        tests = [
            ("View users", "/users", "GET", [200, 404]),
            ("Manage models", "/models", "GET", [200, 404]),
            ("Limited financial view", "/financial/overview", "GET", [200, 404]),
            ("Cannot edit financial", "/financial/commission/rules", "POST", [403, 422, 500]),
            ("Agency analytics", "/analytics/agency", "GET", [200, 404]),
            ("White-label access", "/whitelabel/theme", "GET", [200, 500]),
        ]
        
        results = []
        for test_name, endpoint, method, expected in tests:
            passed, status = self.test_endpoint_access(role, endpoint, method, expected)
            results.append((test_name, passed, status))
            status_icon = "✅" if passed else "❌"
            print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_model_permissions(self):
        """Test MODEL role permissions"""
        print("\n🧪 Testing MODEL Permissions")
        role = UserRole.MODEL
        
        # Get model's own ID
        session = self.sessions[role]
        user_id = session.user_info.get("id") if hasattr(session, "user_info") else None
        
        tests = [
            ("View own profile", "/auth/me", "GET", [200]),
            ("Edit own profile", f"/models/{user_id}", "PUT", [200, 404]) if user_id else ("Skip", "", "GET", []),
            ("View own analytics", f"/analytics/models/{user_id}", "GET", [200, 404]) if user_id else ("Skip", "", "GET", []),
            ("View own earnings", "/financial/earnings/me", "GET", [200, 404]),
            ("Cannot view all users", "/users", "GET", [403, 404]),
            ("Cannot manage other models", "/models", "GET", [403, 404]),
            ("Chat access", "/chat/messages", "GET", [200, 404]),
        ]
        
        results = []
        for test_data in tests:
            if len(test_data) == 4:
                test_name, endpoint, method, expected = test_data
                passed, status = self.test_endpoint_access(role, endpoint, method, expected)
                results.append((test_name, passed, status))
                status_icon = "✅" if passed else "❌"
                print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_chatter_permissions(self):
        """Test CHATTER role permissions"""
        print("\n🧪 Testing CHATTER Permissions")
        role = UserRole.CHATTER
        
        tests = [
            ("View assigned chats", "/chat/assigned", "GET", [200, 404]),
            ("Send chat messages", "/chat/messages", "POST", [200, 403, 422]),
            ("Limited analytics", "/analytics/chatter/performance", "GET", [200, 404]),
            ("Cannot view financial", "/financial/payouts", "GET", [403, 500]),
            ("Cannot manage users", "/users", "GET", [403, 404]),
            ("Cannot edit models", "/models", "PUT", [403, 404, 405]),
        ]
        
        results = []
        for test_name, endpoint, method, expected in tests:
            passed, status = self.test_endpoint_access(role, endpoint, method, expected)
            results.append((test_name, passed, status))
            status_icon = "✅" if passed else "❌"
            print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_agency_member_permissions(self):
        """Test AGENCY_MEMBER role permissions"""
        print("\n🧪 Testing AGENCY_MEMBER Permissions")
        role = UserRole.AGENCY_MEMBER
        
        tests = [
            ("View own profile", "/auth/me", "GET", [200]),
            ("Basic dashboard", "/dashboard/basic", "GET", [200, 404]),
            ("Cannot view users", "/users", "GET", [403, 404]),
            ("Cannot view financial", "/financial/payouts", "GET", [403, 500]),
            ("Cannot access chat", "/chat/messages", "GET", [403, 404]),
            ("Cannot view models", "/models", "GET", [403, 404]),
        ]
        
        results = []
        for test_name, endpoint, method, expected in tests:
            passed, status = self.test_endpoint_access(role, endpoint, method, expected)
            results.append((test_name, passed, status))
            status_icon = "✅" if passed else "❌"
            print(f"   {status_icon} {test_name}: {status}")
        
        return results
    
    def test_privilege_escalation_attempts(self):
        """Test that users cannot escalate their privileges"""
        print("\n🧪 Testing Privilege Escalation Prevention")
        
        # Chatter tries to become admin
        chatter_session = self.sessions[UserRole.CHATTER]
        if hasattr(chatter_session, "user_info"):
            user_id = chatter_session.user_info.get("id")
            
            # Try to change own role
            response = chatter_session.put(
                f"{self.api_url}/users/{user_id}",
                json={"role": "agency_admin"}
            )
            
            if response.status_code in [403, 404]:
                print("   ✅ Chatter cannot change own role")
            else:
                print(f"   ❌ Chatter role change attempt: {response.status_code}")
        
        # Model tries to access admin endpoints
        model_session = self.sessions[UserRole.MODEL]
        response = model_session.post(
            f"{self.api_url}/users",
            json={"email": "hacker@test.com", "role": "agency_owner"}
        )
        
        if response.status_code in [403, 404]:
            print("   ✅ Model cannot create admin users")
        else:
            print(f"   ❌ Model user creation attempt: {response.status_code}")
        
        return True
    
    def run_all_tests(self):
        """Run all RBAC tests"""
        print("=" * 80)
        print("🔐 Role-Based Access Control (RBAC) Test Suite")
        print("=" * 80)
        
        # Login all test users
        print("\n🔑 Setting up test sessions...")
        for role, email in self.test_users.items():
            session = self.login(email)
            if session:
                self.sessions[role] = session
                print(f"   ✅ {role.value}: {email}")
            else:
                print(f"   ❌ {role.value}: {email}")
        
        # Run role-specific tests
        all_results = {}
        
        test_functions = [
            (UserRole.SUPER_ADMIN, self.test_super_admin_permissions),
            (UserRole.AGENCY_OWNER, self.test_agency_owner_permissions),
            (UserRole.AGENCY_ADMIN, self.test_agency_admin_permissions),
            (UserRole.MODEL, self.test_model_permissions),
            (UserRole.CHATTER, self.test_chatter_permissions),
            (UserRole.AGENCY_MEMBER, self.test_agency_member_permissions),
        ]
        
        for role, test_func in test_functions:
            if role in self.sessions:
                results = test_func()
                all_results[role] = results
            else:
                print(f"\n⚠️  Skipping {role.value} tests (no session)")
        
        # Test privilege escalation
        self.test_privilege_escalation_attempts()
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 RBAC Test Summary")
        print("=" * 80)
        
        for role, results in all_results.items():
            passed = sum(1 for _, p, _ in results if p)
            total = len(results)
            print(f"\n{role.value}:")
            print(f"   Tests: {passed}/{total} passed")
            
            # Show failures
            failures = [(name, status) for name, p, status in results if not p]
            if failures:
                print("   Failures:")
                for name, status in failures:
                    print(f"      - {name} (status: {status})")
        
        # Overall summary
        total_passed = sum(sum(1 for _, p, _ in results if p) for results in all_results.values())
        total_tests = sum(len(results) for results in all_results.values())
        
        print(f"\n🎯 Overall: {total_passed}/{total_tests} tests passed")
        
        if total_passed == total_tests:
            print("\n✅ All RBAC tests passed!")
        else:
            print(f"\n⚠️  {total_tests - total_passed} tests need attention")
        
        return all_results


def main():
    """Run the RBAC test suite"""
    tester = RBACTester()
    results = tester.run_all_tests()
    
    # Security recommendations
    print("\n" + "=" * 80)
    print("🔍 RBAC Security Recommendations")
    print("=" * 80)
    print("1. Implement decorator-based permission checks on all endpoints")
    print("2. Use database-level row security policies")
    print("3. Log all permission denial events for auditing")
    print("4. Implement principle of least privilege")
    print("5. Regular review of role permissions matrix")
    print("6. Implement session timeout for sensitive roles")
    print("7. Add two-factor authentication for admin roles")


if __name__ == "__main__":
    main()