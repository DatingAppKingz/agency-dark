"""
Integration tests for API endpoints
"""
import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime, timedelta
import json
from uuid import uuid4

from tests.utils.test_data import create_test_user, create_test_content
from core.redis import redis_client


class TestAuthIntegration:
    """Integration tests for authentication flow"""
    
    @pytest.mark.integration
    async def test_full_auth_flow(self, async_client: AsyncClient, db_session):
        """Test complete authentication flow"""
        # Register new user
        register_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "full_name": "New User"
        }
        
        response = await async_client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 201
        user_data = response.json()
        assert user_data["email"] == register_data["email"]
        
        # Login with new user
        login_data = {
            "username": register_data["username"],
            "password": register_data["password"]
        }
        
        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        
        # Access protected endpoint
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await async_client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        me_data = response.json()
        assert me_data["email"] == register_data["email"]
        
        # Refresh token
        refresh_data = {"refresh_token": tokens["refresh_token"]}
        response = await async_client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 200
        new_tokens = response.json()
        assert new_tokens["access_token"] != tokens["access_token"]
        
        # Logout
        response = await async_client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 200
        
        # Verify token is invalidated
        response = await async_client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
    
    @pytest.mark.integration
    async def test_oauth_flow(self, async_client: AsyncClient, mocker):
        """Test OAuth authentication flow"""
        # Mock OAuth provider response
        mock_oauth_response = {
            "id": "oauth123",
            "email": "oauth@example.com",
            "name": "OAuth User"
        }
        
        mocker.patch(
            "modules.auth.infrastructure.oauth.providers.GoogleOAuthProvider.get_user_info",
            return_value=mock_oauth_response
        )
        
        # Start OAuth flow
        response = await async_client.get("/api/v1/auth/oauth/google")
        assert response.status_code == 302  # Redirect to OAuth provider
        
        # Simulate callback with code
        callback_params = {
            "code": "mock_auth_code",
            "state": "mock_state"
        }
        
        response = await async_client.get(
            "/api/v1/auth/oauth/google/callback",
            params=callback_params
        )
        assert response.status_code == 200
        tokens = response.json()
        assert "access_token" in tokens


class TestContentIntegration:
    """Integration tests for content management"""
    
    @pytest.mark.integration
    async def test_content_crud_lifecycle(self, async_client: AsyncClient, auth_headers):
        """Test complete content CRUD lifecycle"""
        # Create content
        content_data = {
            "title": "Integration Test Content",
            "body": "This is test content for integration testing",
            "status": "draft",
            "tags": ["test", "integration"]
        }
        
        response = await async_client.post(
            "/api/v1/content",
            json=content_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_content = response.json()
        content_id = created_content["id"]
        
        # Read content
        response = await async_client.get(
            f"/api/v1/content/{content_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["title"] == content_data["title"]
        
        # Update content
        update_data = {
            "title": "Updated Integration Test",
            "status": "published"
        }
        
        response = await async_client.put(
            f"/api/v1/content/{content_id}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        updated_content = response.json()
        assert updated_content["title"] == update_data["title"]
        assert updated_content["status"] == "published"
        
        # List content with filters
        response = await async_client.get(
            "/api/v1/content",
            params={"status": "published", "limit": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        content_list = response.json()
        assert len(content_list["items"]) > 0
        assert any(c["id"] == content_id for c in content_list["items"])
        
        # Delete content
        response = await async_client.delete(
            f"/api/v1/content/{content_id}",
            headers=auth_headers
        )
        assert response.status_code == 204
        
        # Verify deletion
        response = await async_client.get(
            f"/api/v1/content/{content_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    @pytest.mark.integration
    async def test_content_versioning(self, async_client: AsyncClient, auth_headers):
        """Test content versioning functionality"""
        # Create content
        content_data = {
            "title": "Versioned Content",
            "body": "Version 1"
        }
        
        response = await async_client.post(
            "/api/v1/content",
            json=content_data,
            headers=auth_headers
        )
        content_id = response.json()["id"]
        
        # Update multiple times to create versions
        for i in range(2, 5):
            update_data = {"body": f"Version {i}"}
            await async_client.put(
                f"/api/v1/content/{content_id}",
                json=update_data,
                headers=auth_headers
            )
        
        # Get version history
        response = await async_client.get(
            f"/api/v1/content/{content_id}/versions",
            headers=auth_headers
        )
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 4
        
        # Restore previous version
        version_id = versions[1]["id"]  # Version 2
        response = await async_client.post(
            f"/api/v1/content/{content_id}/versions/{version_id}/restore",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify restoration
        response = await async_client.get(
            f"/api/v1/content/{content_id}",
            headers=auth_headers
        )
        assert response.json()["body"] == "Version 2"


class TestAnalyticsIntegration:
    """Integration tests for analytics endpoints"""
    
    @pytest.mark.integration
    async def test_real_time_analytics(self, async_client: AsyncClient, auth_headers):
        """Test real-time analytics data flow"""
        # Send analytics events
        events = [
            {
                "event_type": "page_view",
                "page": "/home",
                "user_id": str(uuid4()),
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "event_type": "button_click",
                "button_id": "cta_subscribe",
                "user_id": str(uuid4()),
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        
        for event in events:
            response = await async_client.post(
                "/api/v1/analytics/events",
                json=event,
                headers=auth_headers
            )
            assert response.status_code == 201
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Get real-time metrics
        response = await async_client.get(
            "/api/v1/analytics/realtime",
            headers=auth_headers
        )
        assert response.status_code == 200
        realtime_data = response.json()
        assert realtime_data["active_users"] > 0
        assert "events_per_minute" in realtime_data
    
    @pytest.mark.integration
    async def test_analytics_aggregation(self, async_client: AsyncClient, auth_headers):
        """Test analytics aggregation pipeline"""
        # Generate test data
        base_time = datetime.utcnow()
        
        for i in range(50):
            event = {
                "event_type": "purchase",
                "amount": 10 + (i % 5) * 5,
                "user_id": str(uuid4()),
                "timestamp": (base_time - timedelta(minutes=i)).isoformat()
            }
            
            await async_client.post(
                "/api/v1/analytics/events",
                json=event,
                headers=auth_headers
            )
        
        # Get aggregated metrics
        params = {
            "metric": "revenue",
            "start_date": (base_time - timedelta(hours=1)).isoformat(),
            "end_date": base_time.isoformat(),
            "granularity": "5m"
        }
        
        response = await async_client.get(
            "/api/v1/analytics/metrics",
            params=params,
            headers=auth_headers
        )
        assert response.status_code == 200
        metrics = response.json()
        assert len(metrics["data"]) > 0
        assert metrics["total"] > 0


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality"""
    
    @pytest.mark.integration
    async def test_websocket_connection(self, async_client: AsyncClient, auth_token):
        """Test WebSocket connection and messaging"""
        # Note: This is a simplified test. Real WebSocket testing requires
        # a WebSocket client library like websockets
        
        # Test Socket.IO endpoint availability
        response = await async_client.get("/socket.io/")
        assert response.status_code in [200, 400]  # 400 is expected without proper WebSocket headers


class TestCachingIntegration:
    """Integration tests for caching functionality"""
    
    @pytest.mark.integration
    async def test_api_response_caching(self, async_client: AsyncClient, auth_headers):
        """Test API response caching"""
        # Make first request (cache miss)
        start_time = asyncio.get_event_loop().time()
        response1 = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        duration1 = asyncio.get_event_loop().time() - start_time
        assert response1.status_code == 200
        
        # Make second request (cache hit)
        start_time = asyncio.get_event_loop().time()
        response2 = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        duration2 = asyncio.get_event_loop().time() - start_time
        assert response2.status_code == 200
        
        # Cached response should be faster
        assert duration2 < duration1 * 0.5
        
        # Verify cache headers
        assert "X-Cache" in response2.headers
        assert response2.headers["X-Cache"] == "HIT"
        
        # Verify data consistency
        assert response1.json() == response2.json()
    
    @pytest.mark.integration
    async def test_cache_invalidation(self, async_client: AsyncClient, auth_headers):
        """Test cache invalidation on updates"""
        # Get user data (populate cache)
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        original_data = response.json()
        
        # Update user data
        update_data = {"full_name": "Updated Name"}
        response = await async_client.put(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Get user data again (should be fresh, not cached)
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        new_data = response.json()
        
        assert new_data["full_name"] == update_data["full_name"]
        assert new_data["full_name"] != original_data.get("full_name")


class TestRateLimitingIntegration:
    """Integration tests for rate limiting"""
    
    @pytest.mark.integration
    async def test_rate_limit_enforcement(self, async_client: AsyncClient, auth_headers):
        """Test rate limit enforcement"""
        # Make requests up to the limit
        responses = []
        for _ in range(100):  # Assuming 100 req/min limit
            response = await async_client.get(
                "/api/v1/health",
                headers=auth_headers
            )
            responses.append(response)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Next request should be rate limited
        response = await async_client.get(
            "/api/v1/health",
            headers=auth_headers
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
    
    @pytest.mark.integration
    async def test_rate_limit_headers(self, async_client: AsyncClient, auth_headers):
        """Test rate limit headers"""
        response = await async_client.get(
            "/api/v1/health",
            headers=auth_headers
        )
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        
        limit = int(response.headers["X-RateLimit-Limit"])
        remaining = int(response.headers["X-RateLimit-Remaining"])
        assert remaining < limit


class TestErrorHandlingIntegration:
    """Integration tests for error handling"""
    
    @pytest.mark.integration
    async def test_validation_errors(self, async_client: AsyncClient, auth_headers):
        """Test validation error responses"""
        # Invalid email format
        invalid_data = {
            "email": "not-an-email",
            "username": "user",
            "password": "pass"
        }
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=invalid_data
        )
        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail
        assert any("email" in str(err) for err in error_detail["detail"])
    
    @pytest.mark.integration
    async def test_not_found_errors(self, async_client: AsyncClient, auth_headers):
        """Test 404 error handling"""
        # Non-existent resource
        response = await async_client.get(
            f"/api/v1/users/{uuid4()}",
            headers=auth_headers
        )
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
    
    @pytest.mark.integration
    async def test_internal_error_handling(self, async_client: AsyncClient, auth_headers, mocker):
        """Test 500 error handling"""
        # Mock database error
        mocker.patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            side_effect=Exception("Database connection failed")
        )
        
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        assert response.status_code == 500
        error = response.json()
        assert "detail" in error
        assert "request_id" in error  # Should include request ID for debugging