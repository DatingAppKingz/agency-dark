#!/usr/bin/env python3
"""
Test secondary/advanced endpoints for AgencyDark API
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
    "email": "owner@elitemodels.com",
    "password": "owner123"
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


class SecondaryEndpointTester:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.api_key: Optional[str] = None
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

    async def setup_auth(self):
        """Login to get access token"""
        success, data = await self.make_request(
            "POST", "/auth/login",
            json_data={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
        )
        
        if success:
            self.access_token = data["access_token"]
            self.user_id = data["user"]["id"]
            return True
        return False

    async def test_api_key_management(self):
        """Test API key management endpoints"""
        self.print_header("Testing API Key Management")
        
        # Create API key
        key_data = {
            "name": "Test API Key",
            "scopes": ["read:models", "write:messages"],
            "expires_in_days": 30
        }
        
        success, data = await self.make_request(
            "POST", "/api-keys/",
            json_data=key_data
        )
        
        if success and "key" in data:
            self.api_key = data["key"]
            key_id = data["id"]
            self.print_test("POST /api-keys/", True)
            
            # List API keys
            success, data = await self.make_request("GET", "/api-keys/")
            self.print_test("GET /api-keys/", success, str(data) if not success else "")
            
            # Get specific API key
            success, data = await self.make_request("GET", f"/api-keys/{key_id}")
            self.print_test(f"GET /api-keys/{key_id}", success, str(data) if not success else "")
            
            # Revoke API key
            success, data = await self.make_request("DELETE", f"/api-keys/{key_id}")
            self.print_test(f"DELETE /api-keys/{key_id}", success, str(data) if not success else "")
        else:
            self.print_test("POST /api-keys/", success, str(data))

    async def test_sessions_management(self):
        """Test session management endpoints"""
        self.print_header("Testing Session Management")
        
        # Get active sessions
        success, data = await self.make_request("GET", "/sessions/")
        self.print_test("GET /sessions/", success, str(data) if not success else "")
        
        # Get current session
        success, data = await self.make_request("GET", "/sessions/current")
        self.print_test("GET /sessions/current", success, str(data) if not success else "")
        
        # Revoke all sessions
        success, data = await self.make_request("POST", "/sessions/revoke-all")
        self.print_test("POST /sessions/revoke-all", success, str(data) if not success else "")

    async def test_bulk_operations(self):
        """Test bulk operations endpoints"""
        self.print_header("Testing Bulk Operations")
        
        # Bulk message send
        bulk_data = {
            "conversation_ids": [1, 2, 3],
            "message": "Bulk test message",
            "sender_type": "CHATTER"
        }
        
        success, data = await self.make_request(
            "POST", "/bulk/messages/send",
            json_data=bulk_data
        )
        self.print_test("POST /bulk/messages/send", success, str(data) if not success else "")
        
        # Bulk tag update
        tag_data = {
            "conversation_ids": [1, 2, 3],
            "tags": ["bulk", "test"],
            "operation": "add"
        }
        
        success, data = await self.make_request(
            "POST", "/bulk/conversations/tags",
            json_data=tag_data
        )
        self.print_test("POST /bulk/conversations/tags", success, str(data) if not success else "")

    async def test_media_upload(self):
        """Test media upload endpoints"""
        self.print_header("Testing Media Upload")
        
        # Get upload URL
        upload_data = {
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "size": 1024
        }
        
        success, data = await self.make_request(
            "POST", "/media/upload-url",
            json_data=upload_data
        )
        self.print_test("POST /media/upload-url", success, str(data) if not success else "")
        
        # Confirm upload
        if success and "upload_id" in data:
            confirm_data = {
                "upload_id": data["upload_id"],
                "etag": "test-etag"
            }
            
            success, data = await self.make_request(
                "POST", "/media/confirm-upload",
                json_data=confirm_data
            )
            self.print_test("POST /media/confirm-upload", success, str(data) if not success else "")

    async def test_reports(self):
        """Test reporting endpoints"""
        self.print_header("Testing Reports")
        
        # Generate revenue report
        report_data = {
            "start_date": "2025-01-01",
            "end_date": "2025-07-30",
            "format": "csv"
        }
        
        success, data = await self.make_request(
            "POST", "/reports/revenue",
            json_data=report_data
        )
        self.print_test("POST /reports/revenue", success, str(data) if not success else "")
        
        # Generate performance report
        success, data = await self.make_request(
            "POST", "/reports/performance",
            json_data=report_data
        )
        self.print_test("POST /reports/performance", success, str(data) if not success else "")
        
        # Get report status
        if success and "report_id" in data:
            success, data = await self.make_request(
                "GET", f"/reports/status/{data['report_id']}"
            )
            self.print_test("GET /reports/status/{id}", success, str(data) if not success else "")

    async def test_ml_analytics(self):
        """Test ML analytics endpoints"""
        self.print_header("Testing ML Analytics")
        
        # Get conversation insights
        success, data = await self.make_request(
            "GET", "/ml/conversations/insights?conversation_id=1"
        )
        self.print_test("GET /ml/conversations/insights", success, str(data) if not success else "")
        
        # Get sentiment analysis
        sentiment_data = {
            "messages": ["I love this!", "This is terrible", "It's okay I guess"]
        }
        
        success, data = await self.make_request(
            "POST", "/ml/sentiment/analyze",
            json_data=sentiment_data
        )
        self.print_test("POST /ml/sentiment/analyze", success, str(data) if not success else "")
        
        # Get churn prediction
        success, data = await self.make_request(
            "GET", "/ml/fans/churn-risk?model_id=1"
        )
        self.print_test("GET /ml/fans/churn-risk", success, str(data) if not success else "")

    async def test_fraud_detection(self):
        """Test fraud detection endpoints"""
        self.print_header("Testing Fraud Detection")
        
        # Check transaction fraud
        fraud_data = {
            "transaction_id": 1,
            "amount": 999.99,
            "user_id": 1
        }
        
        success, data = await self.make_request(
            "POST", "/fraud/check-transaction",
            json_data=fraud_data
        )
        self.print_test("POST /fraud/check-transaction", success, str(data) if not success else "")
        
        # Get fraud alerts
        success, data = await self.make_request("GET", "/fraud/alerts")
        self.print_test("GET /fraud/alerts", success, str(data) if not success else "")
        
        # Mark as reviewed
        if success and isinstance(data, list) and len(data) > 0:
            alert_id = data[0].get("id", 1)
            success, data = await self.make_request(
                "POST", f"/fraud/alerts/{alert_id}/review",
                json_data={"action": "dismiss", "notes": "False positive"}
            )
            self.print_test("POST /fraud/alerts/{id}/review", success, str(data) if not success else "")

    async def test_rate_limit_management(self):
        """Test rate limit management endpoints"""
        self.print_header("Testing Rate Limit Management")
        
        # Get rate limit status
        success, data = await self.make_request("GET", "/rate-limits/status")
        self.print_test("GET /rate-limits/status", success, str(data) if not success else "")
        
        # Set custom rate limit
        limit_data = {
            "key": "api_key_test",
            "max_requests": 100,
            "window_seconds": 60
        }
        
        success, data = await self.make_request(
            "POST", "/rate-limits/custom",
            json_data=limit_data
        )
        self.print_test("POST /rate-limits/custom", success, str(data) if not success else "")
        
        # Reset rate limit
        success, data = await self.make_request(
            "POST", "/rate-limits/reset",
            json_data={"key": "api_key_test"}
        )
        self.print_test("POST /rate-limits/reset", success, str(data) if not success else "")

    async def test_push_notifications(self):
        """Test push notification endpoints"""
        self.print_header("Testing Push Notifications")
        
        # Register device
        device_data = {
            "token": "test-device-token",
            "platform": "ios",
            "device_info": {"model": "iPhone 15", "os": "iOS 17"}
        }
        
        success, data = await self.make_request(
            "POST", "/notifications/devices/register",
            json_data=device_data
        )
        self.print_test("POST /notifications/devices/register", success, str(data) if not success else "")
        
        # Send test notification
        notif_data = {
            "user_id": self.user_id,
            "title": "Test Notification",
            "body": "This is a test",
            "data": {"type": "test"}
        }
        
        success, data = await self.make_request(
            "POST", "/notifications/send",
            json_data=notif_data
        )
        self.print_test("POST /notifications/send", success, str(data) if not success else "")
        
        # Get notification preferences
        success, data = await self.make_request("GET", "/notifications/preferences")
        self.print_test("GET /notifications/preferences", success, str(data) if not success else "")

    async def test_monitoring(self):
        """Test monitoring endpoints"""
        self.print_header("Testing Monitoring Endpoints")
        
        # Get system metrics
        success, data = await self.make_request("GET", "/monitoring/metrics")
        self.print_test("GET /monitoring/metrics", success, str(data) if not success else "")
        
        # Get error logs
        success, data = await self.make_request(
            "GET", "/monitoring/errors?limit=10"
        )
        self.print_test("GET /monitoring/errors", success, str(data) if not success else "")
        
        # Get performance stats
        success, data = await self.make_request("GET", "/monitoring/performance")
        self.print_test("GET /monitoring/performance", success, str(data) if not success else "")

    async def test_sync_status(self):
        """Test sync status endpoints"""
        self.print_header("Testing Sync Status")
        
        # Get sync status
        success, data = await self.make_request("GET", "/sync/status")
        self.print_test("GET /sync/status", success, str(data) if not success else "")
        
        # Trigger sync
        sync_data = {
            "platform": "onlyfans",
            "model_id": 1,
            "sync_type": "messages"
        }
        
        success, data = await self.make_request(
            "POST", "/sync/trigger",
            json_data=sync_data
        )
        self.print_test("POST /sync/trigger", success, str(data) if not success else "")
        
        # Get sync history
        success, data = await self.make_request("GET", "/sync/history?model_id=1")
        self.print_test("GET /sync/history", success, str(data) if not success else "")

    async def test_tasks(self):
        """Test background tasks endpoints"""
        self.print_header("Testing Background Tasks")
        
        # Get task status
        success, data = await self.make_request("GET", "/tasks/")
        self.print_test("GET /tasks/", success, str(data) if not success else "")
        
        # Create export task
        task_data = {
            "task_type": "export_conversations",
            "parameters": {
                "model_id": 1,
                "format": "csv",
                "date_range": "last_30_days"
            }
        }
        
        success, data = await self.make_request(
            "POST", "/tasks/create",
            json_data=task_data
        )
        self.print_test("POST /tasks/create", success, str(data) if not success else "")
        
        # Cancel task
        if success and "task_id" in data:
            success, data = await self.make_request(
                "POST", f"/tasks/{data['task_id']}/cancel"
            )
            self.print_test("POST /tasks/{id}/cancel", success, str(data) if not success else "")

    async def test_query_performance(self):
        """Test query performance endpoints"""
        self.print_header("Testing Query Performance")
        
        # Get slow queries
        success, data = await self.make_request("GET", "/performance/queries/slow")
        self.print_test("GET /performance/queries/slow", success, str(data) if not success else "")
        
        # Get query stats
        success, data = await self.make_request("GET", "/performance/queries/stats")
        self.print_test("GET /performance/queries/stats", success, str(data) if not success else "")
        
        # Analyze query
        query_data = {
            "query": "SELECT * FROM messages WHERE created_at > NOW() - INTERVAL '7 days'"
        }
        
        success, data = await self.make_request(
            "POST", "/performance/queries/analyze",
            json_data=query_data
        )
        self.print_test("POST /performance/queries/analyze", success, str(data) if not success else "")

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
        """Run all secondary endpoint tests"""
        print(f"{Colors.BOLD}{Colors.CYAN}AgencyDark Secondary/Advanced Features Test Suite{Colors.RESET}")
        print(f"{Colors.YELLOW}Testing against: {BASE_URL}{Colors.RESET}")
        
        # Setup authentication first
        if not await self.setup_auth():
            print(f"{Colors.RED}Failed to authenticate. Cannot proceed with tests.{Colors.RESET}")
            return
        
        # Run all test suites
        await self.test_api_key_management()
        await self.test_sessions_management()
        await self.test_bulk_operations()
        await self.test_media_upload()
        await self.test_reports()
        await self.test_ml_analytics()
        await self.test_fraud_detection()
        await self.test_rate_limit_management()
        await self.test_push_notifications()
        await self.test_monitoring()
        await self.test_sync_status()
        await self.test_tasks()
        await self.test_query_performance()
        
        self.print_summary()


async def main():
    """Main test runner"""
    async with SecondaryEndpointTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())