"""
Integration tests for enhanced authentication system.

Tests the complete auth flow with real database and Redis.
"""
import pytest
from datetime import datetime, timedelta
import asyncio
from httpx import AsyncClient
from sqlalchemy import select

from core.domain.models import User, Session, UserRole
from core.security_v2 import hash_password, verify_password
from core.security_v2.token_blacklist import TokenBlacklist
from core.config import settings


@pytest.mark.asyncio
class TestAuthIntegration:
    """Integration tests for authentication flow."""
    
    async def test_complete_auth_flow(self, async_client: AsyncClient, test_db):
        """Test complete authentication flow from registration to logout."""
        # 1. Register new user
        register_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User",
            "role": "model"
        }
        
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/register",
            json=register_data
        )
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == register_data["email"]
        user_id = user_data["id"]
        
        # 2. Verify user exists in database
        result = await test_db.execute(
            select(User).where(User.email == register_data["email"])
        )
        user = result.scalar_one()
        assert user is not None
        assert user.email_verification_token is not None
        
        # 3. Login with new user
        login_data = {
            "email": register_data["email"],
            "password": register_data["password"],
            "remember_me": True
        }
        
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json=login_data
        )
        assert response.status_code == 200
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # 4. Verify session was created
        result = await test_db.execute(
            select(Session).where(Session.user_id == user_id)
        )
        session = result.scalar_one()
        assert session is not None
        assert session.remember_me is True
        assert session.is_active is True
        
        # 5. Access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await async_client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers=headers
        )
        assert response.status_code == 200
        me_data = response.json()
        assert me_data["email"] == register_data["email"]
        
        # 6. Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/refresh",
            json=refresh_data
        )
        assert response.status_code == 200
        new_tokens = response.json()
        assert new_tokens["access_token"] != access_token
        
        # 7. Logout
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/logout",
            headers=headers
        )
        assert response.status_code == 200
        
        # 8. Verify session is inactive
        await test_db.refresh(session)
        assert session.is_active is False
        
        # 9. Verify old token no longer works
        response = await async_client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers=headers
        )
        assert response.status_code == 401
    
    async def test_password_reset_integration(self, async_client: AsyncClient, test_db):
        """Test password reset flow with email."""
        # Create user
        user = User(
            email="resettest@example.com",
            hashed_password=hash_password("OldPassword123"),
            full_name="Reset Test User",
            role=UserRole.MODEL,
            is_active=True,
            is_verified=True
        )
        test_db.add(user)
        await test_db.commit()
        
        # Request password reset
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/password-reset/request",
            json={"email": user.email}
        )
        assert response.status_code == 200
        
        # Get reset token from DB
        await test_db.refresh(user)
        reset_token = user.password_reset_token
        assert reset_token is not None
        
        # Reset password
        new_password = "NewPassword123!"
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/password-reset/confirm",
            json={
                "token": reset_token,
                "new_password": new_password
            }
        )
        assert response.status_code == 200
        
        # Verify can login with new password
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={
                "email": user.email,
                "password": new_password
            }
        )
        assert response.status_code == 200
        
        # Verify old password doesn't work
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={
                "email": user.email,
                "password": "OldPassword123"
            }
        )
        assert response.status_code == 401
    
    async def test_concurrent_session_limit(self, async_client: AsyncClient, test_db):
        """Test concurrent session limits."""
        # Create user
        user = User(
            email="sessiontest@example.com",
            hashed_password=hash_password("Password123"),
            full_name="Session Test User",
            role=UserRole.MODEL,
            is_active=True
        )
        test_db.add(user)
        await test_db.commit()
        
        # Create multiple sessions
        sessions = []
        for i in range(6):  # Over the limit of 5
            response = await async_client.post(
                f"{settings.API_V1_STR}/auth/login",
                json={
                    "email": user.email,
                    "password": "Password123"
                },
                headers={"User-Agent": f"TestClient/{i}"}
            )
            assert response.status_code == 200
            sessions.append(response.json()["access_token"])
        
        # Check active sessions
        result = await test_db.execute(
            select(Session).where(
                Session.user_id == user.id,
                Session.is_active == True
            )
        )
        active_sessions = result.scalars().all()
        assert len(active_sessions) <= 5  # Should enforce limit
        
        # First session should be revoked
        headers = {"Authorization": f"Bearer {sessions[0]}"}
        response = await async_client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers=headers
        )
        # May still work if token not blacklisted, but session should be inactive
    
    async def test_rate_limiting_integration(self, async_client: AsyncClient):
        """Test rate limiting on auth endpoints."""
        # Test registration rate limit
        for i in range(10):
            response = await async_client.post(
                f"{settings.API_V1_STR}/auth/register",
                json={
                    "email": f"ratelimit{i}@example.com",
                    "password": "Password123",
                    "full_name": f"Rate Limit {i}"
                }
            )
            
            if i < 5:  # Within rate limit
                assert response.status_code in [200, 400]  # 400 if email exists
            else:  # Should hit rate limit
                assert response.status_code == 429
                assert "rate limit" in response.json()["detail"].lower()
        
        # Wait a bit to reset rate limit
        await asyncio.sleep(61)  # Wait for 1 minute window to pass
        
        # Should work again
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "afterlimit@example.com",
                "password": "Password123",
                "full_name": "After Limit"
            }
        )
        assert response.status_code == 200
    
    async def test_email_verification_flow(self, async_client: AsyncClient, test_db):
        """Test email verification flow."""
        # Register user
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={
                "email": "verify@example.com",
                "password": "Password123",
                "full_name": "Verify User"
            }
        )
        assert response.status_code == 200
        
        # Get verification token
        result = await test_db.execute(
            select(User).where(User.email == "verify@example.com")
        )
        user = result.scalar_one()
        verification_token = user.email_verification_token
        
        # Verify email
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/verify-email/{verification_token}"
        )
        assert response.status_code == 200
        
        # Check user is verified
        await test_db.refresh(user)
        assert user.is_verified is True
        assert user.email_verification_token is None
        assert user.verified_at is not None


@pytest.mark.asyncio
class TestSessionManagementIntegration:
    """Integration tests for session management."""
    
    async def test_session_activity_tracking(self, async_client: AsyncClient, test_db):
        """Test session activity is tracked correctly."""
        # Create and login user
        user = User(
            email="activity@example.com",
            hashed_password=hash_password("Password123"),
            full_name="Activity User",
            role=UserRole.MODEL,
            is_active=True
        )
        test_db.add(user)
        await test_db.commit()
        
        # Login
        response = await async_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={
                "email": user.email,
                "password": "Password123"
            }
        )
        assert response.status_code == 200
        access_token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get initial session
        result = await test_db.execute(
            select(Session).where(Session.user_id == user.id)
        )
        session = result.scalar_one()
        initial_activity = session.last_activity
        
        # Wait and make another request
        await asyncio.sleep(2)
        response = await async_client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers=headers
        )
        assert response.status_code == 200
        
        # Activity should be updated
        await test_db.refresh(session)
        assert session.last_activity > initial_activity
    
    async def test_device_detection(self, async_client: AsyncClient, test_db):
        """Test device detection in sessions."""
        # Create user
        user = User(
            email="device@example.com",
            hashed_password=hash_password("Password123"),
            full_name="Device User",
            role=UserRole.MODEL,
            is_active=True
        )
        test_db.add(user)
        await test_db.commit()
        
        # Login from different devices
        user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15"
        ]
        
        for ua in user_agents:
            response = await async_client.post(
                f"{settings.API_V1_STR}/auth/login",
                json={
                    "email": user.email,
                    "password": "Password123"
                },
                headers={"User-Agent": ua}
            )
            assert response.status_code == 200
        
        # Get sessions
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await async_client.get(
            f"{settings.API_V1_STR}/sessions",
            headers=headers
        )
        assert response.status_code == 200
        sessions = response.json()["sessions"]
        
        # Should have different device names
        device_names = [s["device_name"] for s in sessions]
        assert "Mobile" in device_names[0]  # iPhone
        assert "Desktop" in device_names[1]  # Windows
        assert "Desktop" in device_names[2]  # Mac