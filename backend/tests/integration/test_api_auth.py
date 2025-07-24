"""
Integration tests for authentication API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.domain.models import User, UserRole


class TestAuthAPI:
    """Test authentication API endpoints."""
    
    @pytest.mark.asyncio
    async def test_register(self, client: AsyncClient, test_agency):
        """Test user registration endpoint."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "securepassword123",
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert data["role"] == "chatter"
        assert "id" in data
        assert "hashed_password" not in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_agency, test_user):
        """Test registration with duplicate email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,  # Duplicate
                "username": "anotheruser",
                "password": "password123",
                "role": "chatter",
                "agency_id": str(test_agency.id)
            }
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login(self, client: AsyncClient, test_user):
        """Test login endpoint."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, test_user, auth_headers):
        """Test get current user endpoint."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert "hashed_password" not in data
    
    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test get current user without authentication."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient, test_user):
        """Test token refresh endpoint."""
        # First login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "testpassword"
            }
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != login_response.json()["access_token"]
    
    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient, auth_headers):
        """Test logout endpoint."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"


class TestRoleBasedAccess:
    """Test role-based access control."""
    
    @pytest.mark.asyncio
    async def test_admin_only_endpoint(self, client: AsyncClient, test_user, model_user):
        """Test endpoint that requires admin role."""
        # Login as regular user (model)
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": model_user.username,
                "password": "modelpassword"
            }
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access admin endpoint (example: create new user)
        response = await client.post(
            "/api/v1/auth/register",
            headers=headers,
            json={
                "email": "newuser2@example.com",
                "username": "newuser2",
                "password": "password123",
                "role": "chatter",
                "agency_id": str(model_user.agency_id)
            }
        )
        
        # Models shouldn't be able to create users
        assert response.status_code in [403, 401]
    
    @pytest.mark.asyncio
    async def test_super_admin_access(self, client: AsyncClient, super_admin_user, test_agency):
        """Test super admin has full access."""
        # Login as super admin
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": super_admin_user.username,
                "password": "adminpassword"
            }
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Super admin should be able to create users
        response = await client.post(
            "/api/v1/auth/register",
            headers=headers,
            json={
                "email": "adminuser@example.com",
                "username": "adminuser",
                "password": "password123",
                "role": "agency_admin",
                "agency_id": str(test_agency.id)
            }
        )
        
        assert response.status_code == 201