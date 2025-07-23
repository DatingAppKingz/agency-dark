"""
Unit tests for authentication module.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid

from backend.modules.auth.application.auth_service import AuthService
from backend.modules.auth.domain.schemas import UserCreate, UserLogin
from backend.modules.auth.domain.models import User, UserRole
from backend.core.security import verify_password, create_access_token, decode_token
from backend.core.exceptions import UnauthorizedException, BadRequestException


class TestAuthService:
    """Test authentication service."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession, test_agency):
        """Test user creation."""
        auth_service = AuthService()
        
        user_data = UserCreate(
            email="newuser@example.com",
            username="newuser",
            password="securepassword123",
            role=UserRole.CHATTER
        )
        
        user = await auth_service.create_user(
            user_data, 
            test_agency.id, 
            db_session
        )
        
        assert user.email == user_data.email
        assert user.username == user_data.username
        assert user.role == user_data.role
        assert user.agency_id == test_agency.id
        assert verify_password("securepassword123", user.hashed_password)
    
    @pytest.mark.asyncio
    async def test_create_duplicate_user(self, db_session: AsyncSession, test_agency, test_user):
        """Test duplicate user creation fails."""
        auth_service = AuthService()
        
        user_data = UserCreate(
            email=test_user.email,  # Duplicate email
            username="differentuser",
            password="password123",
            role=UserRole.CHATTER
        )
        
        with pytest.raises(BadRequestException) as exc:
            await auth_service.create_user(
                user_data,
                test_agency.id,
                db_session
            )
        assert "already exists" in str(exc.value.detail)
    
    @pytest.mark.asyncio
    async def test_authenticate_user(self, db_session: AsyncSession, test_user):
        """Test user authentication."""
        auth_service = AuthService()
        
        # Test successful authentication
        user = await auth_service.authenticate_user(
            test_user.username,
            "testpassword",
            db_session
        )
        
        assert user is not None
        assert user.id == test_user.id
        
        # Test failed authentication - wrong password
        user = await auth_service.authenticate_user(
            test_user.username,
            "wrongpassword",
            db_session
        )
        assert user is None
        
        # Test failed authentication - wrong username
        user = await auth_service.authenticate_user(
            "nonexistent",
            "testpassword",
            db_session
        )
        assert user is None
    
    @pytest.mark.asyncio
    async def test_login(self, db_session: AsyncSession, test_user):
        """Test login functionality."""
        auth_service = AuthService()
        
        login_data = UserLogin(
            username=test_user.username,
            password="testpassword"
        )
        
        token_response = await auth_service.login(login_data, db_session)
        
        assert token_response.access_token is not None
        assert token_response.refresh_token is not None
        assert token_response.token_type == "bearer"
        
        # Verify access token
        payload = decode_token(token_response.access_token)
        assert payload["sub"] == str(test_user.id)
        assert payload["role"] == test_user.role.value
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, db_session: AsyncSession):
        """Test login with invalid credentials."""
        auth_service = AuthService()
        
        login_data = UserLogin(
            username="nonexistent",
            password="wrongpassword"
        )
        
        with pytest.raises(UnauthorizedException):
            await auth_service.login(login_data, db_session)
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, db_session: AsyncSession, test_user):
        """Test token refresh."""
        auth_service = AuthService()
        
        # Create initial tokens
        login_data = UserLogin(
            username=test_user.username,
            password="testpassword"
        )
        initial_tokens = await auth_service.login(login_data, db_session)
        
        # Refresh tokens
        new_tokens = await auth_service.refresh_token(
            initial_tokens.refresh_token,
            db_session
        )
        
        assert new_tokens.access_token != initial_tokens.access_token
        assert new_tokens.refresh_token != initial_tokens.refresh_token
        
        # Verify new access token
        payload = decode_token(new_tokens.access_token)
        assert payload["sub"] == str(test_user.id)


class TestSecurity:
    """Test security functions."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        user_id = uuid.uuid4()
        role = UserRole.AGENCY_ADMIN
        
        token = create_access_token(
            data={"sub": str(user_id), "role": role.value}
        )
        
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == role.value
        assert "exp" in payload
    
    def test_decode_expired_token(self):
        """Test decoding expired token."""
        user_id = uuid.uuid4()
        
        # Create token that expires immediately
        token = create_access_token(
            data={"sub": str(user_id)},
            expires_delta=timedelta(seconds=-1)
        )
        
        with pytest.raises(UnauthorizedException):
            decode_token(token)
    
    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        with pytest.raises(UnauthorizedException):
            decode_token("invalid.token.here")


class TestRolePermissions:
    """Test role-based permissions."""
    
    @pytest.mark.asyncio
    async def test_role_hierarchy(self):
        """Test role hierarchy permissions."""
        # Super admin has all permissions
        assert UserRole.SUPER_ADMIN.value == "super_admin"
        
        # Role order (highest to lowest)
        roles = [
            UserRole.SUPER_ADMIN,
            UserRole.AGENCY_OWNER,
            UserRole.AGENCY_ADMIN,
            UserRole.MODEL,
            UserRole.CHATTER
        ]
        
        # Verify all roles are defined
        for role in roles:
            assert role.value is not None