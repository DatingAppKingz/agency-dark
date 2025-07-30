#!/usr/bin/env python3
"""
Comprehensive endpoint testing script for AgencyDark API
Tests all endpoints to ensure they're working correctly
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8001"
API_V1 = f"{BASE_URL}/api/v1"

# Test user credentials
TEST_USER = {
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
}

ADMIN_USER = {
    "email": "admin@example.com", 
    "username": "adminuser",
    "password": "adminpass123",
    "first_name": "Admin",
    "last_name": "User"
}


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class EndpointTester:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.admin_token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.admin_id: Optional[int] = None
        self.agency_id: Optional[int] = None
        self.model_id: Optional[int] = None
        self.conversation_id: Optional[int] = None
        self.results = {"passed": 0, "failed": 0, "errors": []}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

    def print_test(self, name: str, passed: bool, details: str = ""):
        """Print test result"""
        if passed:
            print(f"{Colors.GREEN}✓{Colors.RESET} {name}")
            self.results["passed"] += 1
        else:
            print(f"{Colors.RED}✗{Colors.RESET} {name}")
            if details:
                print(f"  {Colors.YELLOW}→ {details}{Colors.RESET}")
            self.results["failed"] += 1
            self.results["errors"].append(f"{name}: {details}")

    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        expected_status: int = 200
    ) -> tuple[bool, Any]:
        """Make HTTP request and return success status and response data"""
        try:
            url = f"{API_V1}{endpoint}" if not endpoint.startswith("http") else endpoint
            
            # Add auth header if we have a token
            if headers is None:
                headers = {}
            if self.access_token and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            async with self.session.request(
                method, url, json=json_data, headers=headers
            ) as response:
                text = await response.text()
                
                # Try to parse JSON
                try:
                    data = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    data = {"raw": text}
                
                success = response.status == expected_status
                
                if not success:
                    error_msg = data.get("detail", f"Status {response.status}")
                    return False, {"error": error_msg, "status": response.status}
                
                return True, data
                
        except Exception as e:
            return False, {"error": str(e)}

    async def test_health_endpoints(self):
        """Test health check endpoints"""
        self.print_header("Testing Health Endpoints")
        
        # Basic health check
        success, data = await self.make_request("GET", f"{BASE_URL}/health", expected_status=200)
        self.print_test("GET /health", success, str(data) if not success else "")
        
        # Root endpoint
        success, data = await self.make_request("GET", BASE_URL, expected_status=200)
        self.print_test("GET /", success, str(data) if not success else "")

    async def test_auth_endpoints(self):
        """Test authentication endpoints"""
        self.print_header("Testing Authentication Endpoints")
        
        # Register new user
        success, data = await self.make_request(
            "POST", "/auth/register", 
            json_data=TEST_USER,
            expected_status=200
        )
        
        if success and "access_token" in data:
            self.access_token = data["access_token"]
            self.user_id = data["user"]["id"]
            self.print_test("POST /auth/register", True)
        else:
            # Try login if registration fails (user might exist)
            login_success, login_data = await self.make_request(
                "POST", "/auth/login",
                json_data={
                    "email": TEST_USER["email"],
                    "password": TEST_USER["password"]
                },
                expected_status=200
            )
            
            if login_success and "access_token" in login_data:
                self.access_token = login_data["access_token"]
                self.user_id = login_data["user"]["id"]
                self.print_test("POST /auth/register", True, "User already exists, auto-logged in")
            else:
                self.print_test("POST /auth/register", False, str(data))
        
        # Login test
        success, data = await self.make_request(
            "POST", "/auth/login",
            json_data={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            },
            expected_status=200
        )
        self.print_test("POST /auth/login", success, str(data) if not success else "")
        
        # Get current user
        success, data = await self.make_request("GET", "/auth/me", expected_status=200)
        self.print_test("GET /auth/me", success, str(data) if not success else "")
        
        # Refresh token
        if self.access_token:
            success, data = await self.make_request(
                "POST", "/auth/refresh",
                json_data={"refresh_token": self.access_token},
                expected_status=200
            )
            self.print_test("POST /auth/refresh", success, str(data) if not success else "")

    async def test_user_endpoints(self):
        """Test user management endpoints"""
        self.print_header("Testing User Management Endpoints")
        
        # Get all users
        success, data = await self.make_request("GET", "/users/", expected_status=200)
        self.print_test("GET /users/", success, str(data) if not success else "")
        
        # Get specific user
        if self.user_id:
            success, data = await self.make_request(
                "GET", f"/users/{self.user_id}", expected_status=200
            )
            self.print_test(f"GET /users/{self.user_id}", success, str(data) if not success else "")
        
        # Update user profile
        if self.user_id:
            update_data = {"bio": "Updated bio for testing"}
            success, data = await self.make_request(
                "PATCH", f"/users/{self.user_id}",
                json_data=update_data,
                expected_status=200
            )
            self.print_test(f"PATCH /users/{self.user_id}", success, str(data) if not success else "")

    async def test_agency_endpoints(self):
        """Test agency endpoints"""
        self.print_header("Testing Agency Endpoints")
        
        # Create agency
        agency_data = {
            "name": "Test Agency",
            "email": "agency@test.com",
            "country": "US",
            "timezone": "America/New_York"
        }
        
        success, data = await self.make_request(
            "POST", "/agencies/",
            json_data=agency_data,
            expected_status=200
        )
        
        if success and "id" in data:
            self.agency_id = data["id"]
        self.print_test("POST /agencies/", success, str(data) if not success else "")
        
        # Get all agencies
        success, data = await self.make_request("GET", "/agencies/", expected_status=200)
        self.print_test("GET /agencies/", success, str(data) if not success else "")
        
        # Get specific agency
        if self.agency_id:
            success, data = await self.make_request(
                "GET", f"/agencies/{self.agency_id}", expected_status=200
            )
            self.print_test(f"GET /agencies/{self.agency_id}", success, str(data) if not success else "")
            
            # Update agency
            update_data = {"name": "Updated Test Agency"}
            success, data = await self.make_request(
                "PATCH", f"/agencies/{self.agency_id}",
                json_data=update_data,
                expected_status=200
            )
            self.print_test(f"PATCH /agencies/{self.agency_id}", success, str(data) if not success else "")

    async def test_model_endpoints(self):
        """Test model management endpoints"""
        self.print_header("Testing Model Management Endpoints")
        
        # Create model
        model_data = {
            "stage_name": "Test Model",
            "platform": "onlyfans",
            "platform_username": "testmodel",
            "is_active": True
        }
        
        success, data = await self.make_request(
            "POST", "/models/",
            json_data=model_data,
            expected_status=200
        )
        
        if success and "id" in data:
            self.model_id = data["id"]
        self.print_test("POST /models/", success, str(data) if not success else "")
        
        # Get all models
        success, data = await self.make_request("GET", "/models/", expected_status=200)
        self.print_test("GET /models/", success, str(data) if not success else "")
        
        # Get specific model
        if self.model_id:
            success, data = await self.make_request(
                "GET", f"/models/{self.model_id}", expected_status=200
            )
            self.print_test(f"GET /models/{self.model_id}", success, str(data) if not success else "")
            
            # Get model analytics
            success, data = await self.make_request(
                "GET", f"/models/{self.model_id}/analytics", expected_status=200
            )
            self.print_test(f"GET /models/{self.model_id}/analytics", success, str(data) if not success else "")

    async def test_conversation_endpoints(self):
        """Test conversation/chat endpoints"""
        self.print_header("Testing Conversation/Chat Endpoints")
        
        # Create conversation
        if self.model_id:
            conv_data = {
                "model_id": self.model_id,
                "fan_username": "testfan",
                "fan_display_name": "Test Fan"
            }
            
            success, data = await self.make_request(
                "POST", "/conversations/",
                json_data=conv_data,
                expected_status=200
            )
            
            if success and "id" in data:
                self.conversation_id = data["id"]
            self.print_test("POST /conversations/", success, str(data) if not success else "")
        
        # Get all conversations
        success, data = await self.make_request("GET", "/conversations/", expected_status=200)
        self.print_test("GET /conversations/", success, str(data) if not success else "")
        
        # Get specific conversation
        if self.conversation_id:
            success, data = await self.make_request(
                "GET", f"/conversations/{self.conversation_id}", expected_status=200
            )
            self.print_test(f"GET /conversations/{self.conversation_id}", success, str(data) if not success else "")
            
            # Send message
            msg_data = {
                "conversation_id": self.conversation_id,
                "content": "Test message",
                "sender_type": "CHATTER"
            }
            
            success, data = await self.make_request(
                "POST", "/messages/",
                json_data=msg_data,
                expected_status=200
            )
            self.print_test("POST /messages/", success, str(data) if not success else "")
            
            # Get conversation messages
            success, data = await self.make_request(
                "GET", f"/conversations/{self.conversation_id}/messages", expected_status=200
            )
            self.print_test(f"GET /conversations/{self.conversation_id}/messages", success, str(data) if not success else "")

    async def test_financial_endpoints(self):
        """Test financial/transaction endpoints"""
        self.print_header("Testing Financial/Transaction Endpoints")
        
        # Create transaction
        if self.model_id:
            trans_data = {
                "model_id": self.model_id,
                "type": "SUBSCRIPTION",
                "gross_amount": 10.99,
                "net_amount": 7.69,
                "currency": "USD",
                "status": "COMPLETED"
            }
            
            success, data = await self.make_request(
                "POST", "/transactions/",
                json_data=trans_data,
                expected_status=200
            )
            self.print_test("POST /transactions/", success, str(data) if not success else "")
        
        # Get all transactions
        success, data = await self.make_request("GET", "/transactions/", expected_status=200)
        self.print_test("GET /transactions/", success, str(data) if not success else "")
        
        # Get transaction stats
        if self.model_id:
            success, data = await self.make_request(
                "GET", f"/transactions/stats/model/{self.model_id}", expected_status=200
            )
            self.print_test(f"GET /transactions/stats/model/{self.model_id}", success, str(data) if not success else "")

    async def test_analytics_endpoints(self):
        """Test analytics endpoints"""
        self.print_header("Testing Analytics Endpoints")
        
        # Dashboard stats
        success, data = await self.make_request("GET", "/analytics/dashboard", expected_status=200)
        self.print_test("GET /analytics/dashboard", success, str(data) if not success else "")
        
        # Model performance
        if self.model_id:
            success, data = await self.make_request(
                "GET", f"/analytics/models/{self.model_id}/performance", expected_status=200
            )
            self.print_test(f"GET /analytics/models/{self.model_id}/performance", success, str(data) if not success else "")
        
        # Revenue analytics
        success, data = await self.make_request("GET", "/analytics/revenue", expected_status=200)
        self.print_test("GET /analytics/revenue", success, str(data) if not success else "")

    async def test_media_endpoints(self):
        """Test media/content endpoints"""
        self.print_header("Testing Media/Content Endpoints")
        
        # Create content
        if self.model_id:
            content_data = {
                "model_id": self.model_id,
                "type": "IMAGE",
                "url": "https://example.com/image.jpg",
                "title": "Test Content"
            }
            
            success, data = await self.make_request(
                "POST", "/content/",
                json_data=content_data,
                expected_status=200
            )
            self.print_test("POST /content/", success, str(data) if not success else "")
        
        # Get all content
        success, data = await self.make_request("GET", "/content/", expected_status=200)
        self.print_test("GET /content/", success, str(data) if not success else "")
        
        # Media library
        if self.model_id:
            success, data = await self.make_request(
                "GET", f"/media/library/model/{self.model_id}", expected_status=200
            )
            self.print_test(f"GET /media/library/model/{self.model_id}", success, str(data) if not success else "")

    async def test_websocket_endpoints(self):
        """Test WebSocket connections"""
        self.print_header("Testing WebSocket Endpoints")
        
        if not self.access_token:
            self.print_test("WebSocket Chat", False, "No access token available")
            return
        
        # Test chat WebSocket
        ws_url = f"ws://localhost:8001/api/v1/ws/chat?token={self.access_token}"
        try:
            async with self.session.ws_connect(ws_url) as ws:
                # Send test message
                await ws.send_json({
                    "type": "ping",
                    "data": {"message": "test"}
                })
                
                # Wait for response
                msg = await asyncio.wait_for(ws.receive(), timeout=5)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    self.print_test("WebSocket Chat Connection", True)
                else:
                    self.print_test("WebSocket Chat Connection", False, "Unexpected message type")
                
                await ws.close()
        except Exception as e:
            self.print_test("WebSocket Chat Connection", False, str(e))
        
        # Test notifications WebSocket  
        ws_url = f"ws://localhost:8001/api/v1/ws/notifications?token={self.access_token}"
        try:
            async with self.session.ws_connect(ws_url) as ws:
                self.print_test("WebSocket Notifications Connection", True)
                await ws.close()
        except Exception as e:
            self.print_test("WebSocket Notifications Connection", False, str(e))
        
        # Test dashboard WebSocket
        ws_url = f"ws://localhost:8001/api/v1/ws/dashboard?token={self.access_token}"
        try:
            async with self.session.ws_connect(ws_url) as ws:
                # Wait for initial stats
                msg = await asyncio.wait_for(ws.receive(), timeout=5)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    self.print_test("WebSocket Dashboard Connection", True)
                else:
                    self.print_test("WebSocket Dashboard Connection", False, "No initial stats received")
                
                await ws.close()
        except Exception as e:
            self.print_test("WebSocket Dashboard Connection", False, str(e))

    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")
        
        total = self.results["passed"] + self.results["failed"]
        pass_rate = (self.results["passed"] / total * 100) if total > 0 else 0
        
        print(f"{Colors.GREEN}Passed: {self.results['passed']}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {self.results['failed']}{Colors.RESET}")
        print(f"{Colors.CYAN}Total: {total}{Colors.RESET}")
        print(f"{Colors.YELLOW}Pass Rate: {pass_rate:.1f}%{Colors.RESET}")
        
        if self.results["errors"]:
            print(f"\n{Colors.RED}Failed Tests:{Colors.RESET}")
            for error in self.results["errors"]:
                print(f"  • {error}")

    async def run_all_tests(self):
        """Run all endpoint tests"""
        print(f"{Colors.BOLD}{Colors.CYAN}AgencyDark API Endpoint Test Suite{Colors.RESET}")
        print(f"{Colors.YELLOW}Testing against: {BASE_URL}{Colors.RESET}")
        
        await self.test_health_endpoints()
        await self.test_auth_endpoints()
        await self.test_user_endpoints()
        await self.test_agency_endpoints()
        await self.test_model_endpoints()
        await self.test_conversation_endpoints()
        await self.test_financial_endpoints()
        await self.test_analytics_endpoints()
        await self.test_media_endpoints()
        await self.test_websocket_endpoints()
        
        self.print_summary()


async def main():
    """Main test runner"""
    async with EndpointTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())