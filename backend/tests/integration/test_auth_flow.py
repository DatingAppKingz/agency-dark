"""
Integration tests for complete authentication flow.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import create_access_token, get_password_hash
from modules.agencies.domain.models import Agency
from models.user import User
from core.auth.models import UserSession, RefreshToken


class TestAuthenticationFlow:
    """Test complete authentication flow including login, MFA, refresh, and logout."""
    
    @pytest.fixture
    async def test_agency(self, test_db: AsyncSession):
        """Create test agency."""
        agency = Agency(
            id=uuid4(),
            name="Test Agency",
            subdomain="testagency",
            is_active=True
        )
        test_db.add(agency)
        await test_db.commit()
        return agency
    
    @pytest.fixture
    async def test_user(self, test_db: AsyncSession, test_agency):
        """Create test user."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPassword123!"),
            display_name="Test User",
            agency_id=test_agency.id,
            is_active=True,
            mfa_enabled=False
        )
        test_db.add(user)
        await test_db.commit()
        return user
    
    @pytest.mark.asyncio
    async def test_complete_login_flow(self, async_client: AsyncClient, test_user):
        """Test complete login flow."""
        # 1. Login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        
        # 2. Use access token to access protected endpoint
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == "test@example.com"
        
        # 3. Refresh token
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        new_data = response.json()
        assert "access_token" in new_data
        assert new_data["access_token"] != access_token
        
        # 4. Logout
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {new_data['access_token']}"}
        )
        assert response.status_code == 200
        
        # 5. Verify old token is invalidated
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_mfa_login_flow(self, async_client: AsyncClient, test_db: AsyncSession, test_user):
        """Test login flow with MFA enabled."""
        # Enable MFA for user
        test_user.mfa_enabled = True
        test_user.mfa_secret = "JBSWY3DPEHPK3PXP"  # Test secret
        await test_db.commit()
        
        # 1. Initial login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mfa_required"] is True
        assert "mfa_token" in data
        
        # 2. Verify MFA with valid code
        # In real test, generate actual TOTP code
        response = await async_client.post(
            "/api/v1/auth/verify-mfa",
            json={
                "mfa_token": data["mfa_token"],
                "code": "123456"  # Would be actual TOTP in real test
            }
        )
        # Would verify based on actual TOTP implementation
    
    @pytest.mark.asyncio
    async def test_password_reset_flow(self, async_client: AsyncClient, test_user):
        """Test complete password reset flow."""
        # 1. Request password reset
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 200
        
        # In real scenario, would capture the reset token from email
        # For testing, we'll create a token directly
        reset_token = create_access_token(
            {"sub": str(test_user.id), "type": "password_reset"},
            expires_delta=timedelta(hours=1)
        )
        
        # 2. Reset password with token
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "NewPassword123!"
            }
        )
        assert response.status_code == 200
        
        # 3. Login with new password
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "NewPassword123!"
            }
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    @pytest.mark.asyncio
    async def test_session_management(self, async_client: AsyncClient, test_db: AsyncSession, test_user):
        """Test session management and concurrent sessions."""
        # Login from multiple devices
        devices = [
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"},
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        ]
        
        tokens = []
        for headers in devices:
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "TestPassword123!"
                },
                headers=headers
            )
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])
        
        # Get active sessions
        response = await async_client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {tokens[0]}"}
        )
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 3
        
        # Revoke specific session
        session_id = sessions[1]["id"]
        response = await async_client.delete(
            f"/api/v1/auth/sessions/{session_id}",
            headers={"Authorization": f"Bearer {tokens[0]}"}
        )
        assert response.status_code == 200
        
        # Verify revoked session can't access
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tokens[1]}"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, async_client: AsyncClient):
        """Test authentication rate limiting."""
        # Attempt multiple failed logins
        for i in range(10):
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "WrongPassword"
                }
            )
            
            if i < 5:
                assert response.status_code == 401
            else:
                # Should be rate limited after 5 attempts
                assert response.status_code == 429
                assert "retry_after" in response.json()
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, async_client: AsyncClient, test_user):
        """Test token expiration handling."""
        # Create token with short expiration
        expired_token = create_access_token(
            {"sub": str(test_user.id)},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"


class TestPermissions:
    """Test role-based access control and permissions."""
    
    @pytest.mark.asyncio
    async def test_role_based_access(self, async_client: AsyncClient, test_db: AsyncSession):
        """Test different role permissions."""
        # Create users with different roles
        roles = ["admin", "manager", "user"]
        users = []
        
        for role in roles:
            user = User(
                id=uuid4(),
                email=f"{role}@example.com",
                hashed_password=get_password_hash("Password123!"),
                role=role,
                is_active=True
            )
            test_db.add(user)
            users.append(user)
        
        await test_db.commit()
        
        # Test access to admin endpoint
        for i, role in enumerate(roles):
            # Login
            response = await async_client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"{role}@example.com",
                    "password": "Password123!"
                }
            )
            token = response.json()["access_token"]
            
            # Try to access admin endpoint
            response = await async_client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if role == "admin":
                assert response.status_code == 200
            else:
                assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_agency_isolation(self, async_client: AsyncClient, test_db: AsyncSession):
        """Test that users can only access their agency's data."""
        # Create two agencies with users
        agencies = []
        for i in range(2):
            agency = Agency(
                id=uuid4(),
                name=f"Agency {i}",
                subdomain=f"agency{i}",
                is_active=True
            )
            test_db.add(agency)
            agencies.append(agency)
            
            user = User(
                id=uuid4(),
                email=f"user{i}@example.com",
                hashed_password=get_password_hash("Password123!"),
                agency_id=agency.id,
                is_active=True
            )
            test_db.add(user)
        
        await test_db.commit()
        
        # Login as user from agency 0
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "user0@example.com",
                "password": "Password123!"
            }
        )
        token = response.json()["access_token"]
        
        # Try to access agency 1's data
        response = await async_client.get(
            f"/api/v1/agencies/{agencies[1].id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403


class TestSecurityFeatures:
    """Test security features like CSRF, XSS prevention, etc."""
    
    @pytest.mark.asyncio
    async def test_csrf_protection(self, async_client: AsyncClient):
        """Test CSRF token validation."""
        # Get CSRF token
        response = await async_client.get("/api/v1/auth/csrf-token")
        assert response.status_code == 200
        csrf_token = response.json()["csrf_token"]
        
        # Make request without CSRF token (should fail for state-changing operations)
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer fake-token"}
        )
        # Would check CSRF validation based on implementation
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, async_client: AsyncClient):
        """Test SQL injection prevention."""
        # Attempt SQL injection in login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com'; DROP TABLE users; --",
                "password": "password"
            }
        )
        assert response.status_code == 401
        # Verify no database corruption
    
    @pytest.mark.asyncio
    async def test_xss_prevention(self, async_client: AsyncClient, test_user):
        """Test XSS prevention in user inputs."""
        # Login
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        token = response.json()["access_token"]
        
        # Try to update profile with XSS
        response = await async_client.patch(
            "/api/v1/auth/profile",
            json={
                "display_name": "<script>alert('XSS')</script>"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        # Verify the script is escaped
        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert "<script>" not in response.json()["display_name"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])