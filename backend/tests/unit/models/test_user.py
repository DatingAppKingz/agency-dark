"""Comprehensive tests for User model and authentication."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
from uuid import uuid4

from models.user import User, UserRole, UserStatus
from models.agency import Agency
from tests.factories import create_test_user, create_test_agency


class TestUserModel:
    """Test cases for User model."""
    
    @pytest.mark.asyncio
    async def test_create_user_with_valid_data(self, db_session: AsyncSession):
        """Test creating a user with all valid data."""
        agency = await create_test_agency()
        
        user = User(
            email="test@example.com",
            username="testuser",
            password_hash=bcrypt.hashpw("password123".encode(), bcrypt.gensalt()).decode(),
            role=UserRole.ADMIN,
            agency_id=agency.id,
            status=UserStatus.ACTIVE
        )
        
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.role == UserRole.ADMIN
        assert user.status == UserStatus.ACTIVE
        assert user.created_at is not None
    
    @pytest.mark.asyncio
    async def test_email_uniqueness_constraint(self, db_session: AsyncSession):
        """Test that email must be unique."""
        user1 = await create_test_user(email="duplicate@example.com")
        
        # Try to create another user with same email
        user2 = User(
            email="duplicate@example.com",
            username="different",
            password_hash="hash"
        )
        db_session.add(user2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_username_uniqueness_constraint(self, db_session: AsyncSession):
        """Test that username must be unique."""
        user1 = await create_test_user(username="duplicate")
        
        # Try to create another user with same username
        user2 = User(
            email="different@example.com",
            username="duplicate",
            password_hash="hash"
        )
        db_session.add(user2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_password_hashing(self, db_session: AsyncSession):
        """Test password hashing and verification."""
        password = "SecurePassword123!"
        user = User(
            email="hash@example.com",
            username="hashtest",
            password_hash=""
        )
        
        # Hash password
        user.set_password(password)
        assert user.password_hash != password
        assert user.password_hash.startswith("$2b$")
        
        # Verify password
        assert user.verify_password(password) is True
        assert user.verify_password("WrongPassword") is False
        assert user.verify_password("") is False
    
    @pytest.mark.asyncio
    async def test_user_roles_and_permissions(self, db_session: AsyncSession):
        """Test different user roles and their permissions."""
        agency = await create_test_agency()
        
        # Create users with different roles
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency.id)
        manager = await create_test_user(role=UserRole.MANAGER, agency_id=agency.id)
        chatter = await create_test_user(role=UserRole.CHATTER, agency_id=agency.id)
        model = await create_test_user(role=UserRole.MODEL, agency_id=agency.id)
        
        # Test role-based permissions
        assert admin.can_manage_users() is True
        assert admin.can_manage_agency() is True
        assert admin.can_view_all_models() is True
        assert admin.can_manage_finances() is True
        
        assert manager.can_manage_users() is True
        assert manager.can_manage_agency() is False
        assert manager.can_view_all_models() is True
        assert manager.can_manage_finances() is True
        
        assert chatter.can_manage_users() is False
        assert chatter.can_manage_agency() is False
        assert chatter.can_view_all_models() is False
        assert chatter.can_manage_finances() is False
        
        assert model.can_manage_users() is False
        assert model.can_manage_agency() is False
        assert model.can_view_all_models() is False
        assert model.can_view_own_finances() is True
    
    @pytest.mark.asyncio
    async def test_user_status_transitions(self, db_session: AsyncSession):
        """Test valid user status transitions."""
        user = await create_test_user(status=UserStatus.ACTIVE)
        
        # Active -> Inactive
        user.deactivate(reason="Vacation")
        assert user.status == UserStatus.INACTIVE
        assert user.deactivated_at is not None
        assert user.deactivation_reason == "Vacation"
        
        # Inactive -> Active
        user.activate()
        assert user.status == UserStatus.ACTIVE
        assert user.deactivated_at is None
        assert user.deactivation_reason is None
        
        # Active -> Suspended
        user.suspend(reason="Policy violation", duration_hours=24)
        assert user.status == UserStatus.SUSPENDED
        assert user.suspended_at is not None
        assert user.suspension_reason == "Policy violation"
        assert user.suspension_ends_at is not None
        assert user.suspension_ends_at > datetime.utcnow()
        
        # Check if suspension expired
        user.suspended_at = datetime.utcnow() - timedelta(hours=25)
        user.suspension_ends_at = datetime.utcnow() - timedelta(hours=1)
        assert user.is_suspension_expired() is True
        
        # Auto-reactivate after suspension
        user.check_suspension_status()
        assert user.status == UserStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_user_last_login_tracking(self, db_session: AsyncSession):
        """Test last login timestamp tracking."""
        user = await create_test_user()
        
        assert user.last_login_at is None
        
        # Record login
        user.record_login()
        await db_session.commit()
        
        assert user.last_login_at is not None
        first_login = user.last_login_at
        
        # Record another login
        await asyncio.sleep(0.1)  # Small delay to ensure different timestamp
        user.record_login()
        await db_session.commit()
        
        assert user.last_login_at > first_login
    
    @pytest.mark.asyncio
    async def test_user_session_management(self, db_session: AsyncSession):
        """Test user session token management."""
        user = await create_test_user()
        
        # Generate session token
        token = user.generate_session_token()
        assert token is not None
        assert len(token) >= 32
        
        # Verify token
        assert user.verify_session_token(token) is True
        assert user.verify_session_token("invalid_token") is False
        
        # Invalidate token
        user.invalidate_session_token(token)
        assert user.verify_session_token(token) is False
        
        # Test token expiration
        expired_token = user.generate_session_token(expires_in_hours=0)
        assert user.verify_session_token(expired_token) is False
    
    @pytest.mark.asyncio
    async def test_user_two_factor_auth(self, db_session: AsyncSession):
        """Test two-factor authentication setup and verification."""
        user = await create_test_user()
        
        assert user.two_factor_enabled is False
        assert user.two_factor_secret is None
        
        # Enable 2FA
        secret = user.enable_two_factor()
        assert user.two_factor_enabled is True
        assert user.two_factor_secret is not None
        assert len(secret) == 32  # Base32 encoded secret
        
        # Generate OTP
        otp = user.generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()
        
        # Verify OTP
        assert user.verify_otp(otp) is True
        assert user.verify_otp("000000") is False
        
        # Disable 2FA
        user.disable_two_factor()
        assert user.two_factor_enabled is False
        assert user.two_factor_secret is None
    
    @pytest.mark.asyncio
    async def test_user_password_reset(self, db_session: AsyncSession):
        """Test password reset functionality."""
        user = await create_test_user()
        old_password_hash = user.password_hash
        
        # Generate reset token
        reset_token = user.generate_password_reset_token()
        assert reset_token is not None
        assert user.password_reset_token is not None
        assert user.password_reset_expires_at is not None
        assert user.password_reset_expires_at > datetime.utcnow()
        
        # Verify reset token
        assert user.verify_password_reset_token(reset_token) is True
        assert user.verify_password_reset_token("invalid_token") is False
        
        # Reset password
        new_password = "NewSecurePassword123!"
        user.reset_password(reset_token, new_password)
        
        assert user.password_hash != old_password_hash
        assert user.verify_password(new_password) is True
        assert user.password_reset_token is None
        assert user.password_reset_expires_at is None
        
        # Token should be invalid after use
        assert user.verify_password_reset_token(reset_token) is False
    
    @pytest.mark.asyncio
    async def test_user_email_verification(self, db_session: AsyncSession):
        """Test email verification process."""
        user = await create_test_user()
        
        assert user.email_verified is False
        assert user.email_verification_token is None
        
        # Generate verification token
        token = user.generate_email_verification_token()
        assert token is not None
        assert user.email_verification_token is not None
        
        # Verify email
        assert user.verify_email(token) is True
        assert user.email_verified is True
        assert user.email_verified_at is not None
        assert user.email_verification_token is None
        
        # Token should be invalid after use
        assert user.verify_email(token) is False
    
    @pytest.mark.asyncio
    async def test_user_failed_login_attempts(self, db_session: AsyncSession):
        """Test failed login attempt tracking and account locking."""
        user = await create_test_user()
        
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        
        # Record failed attempts
        for i in range(4):
            user.record_failed_login()
            assert user.failed_login_attempts == i + 1
        
        # 5th attempt should lock account
        user.record_failed_login()
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.locked_until > datetime.utcnow()
        assert user.is_locked() is True
        
        # Successful login should reset counter
        user.record_login()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.is_locked() is False
    
    @pytest.mark.asyncio
    async def test_user_agency_relationship(self, db_session: AsyncSession):
        """Test user-agency relationships and constraints."""
        agency1 = await create_test_agency(name="Agency 1")
        agency2 = await create_test_agency(name="Agency 2")
        
        # User must belong to an agency
        user = await create_test_user(agency_id=agency1.id)
        assert user.agency_id == agency1.id
        
        # Test cross-agency access
        assert user.can_access_agency(agency1.id) is True
        assert user.can_access_agency(agency2.id) is False
        
        # Admin can switch agencies (if multi-agency enabled)
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency1.id)
        admin.enable_multi_agency_access([agency1.id, agency2.id])
        assert admin.can_access_agency(agency1.id) is True
        assert admin.can_access_agency(agency2.id) is True
    
    @pytest.mark.asyncio
    async def test_user_soft_delete(self, db_session: AsyncSession):
        """Test soft delete functionality."""
        user = await create_test_user()
        user_id = user.id
        
        # Soft delete
        user.soft_delete()
        assert user.deleted_at is not None
        assert user.status == UserStatus.DELETED
        
        # User should not appear in active queries
        active_users = await db_session.query(User).filter(
            User.deleted_at.is_(None)
        ).all()
        assert user not in active_users
        
        # But should still exist in database
        deleted_user = await db_session.get(User, user_id)
        assert deleted_user is not None
        assert deleted_user.deleted_at is not None
    
    @pytest.mark.asyncio
    async def test_user_activity_logging(self, db_session: AsyncSession):
        """Test user activity logging."""
        user = await create_test_user()
        
        # Log various activities
        user.log_activity("login", {"ip": "192.168.1.1"})
        user.log_activity("password_change", {"old_hash": "xxx"})
        user.log_activity("profile_update", {"fields": ["email", "name"]})
        
        # Verify activity log
        activities = user.get_recent_activities(limit=10)
        assert len(activities) == 3
        assert activities[0]["action"] == "profile_update"
        assert activities[1]["action"] == "password_change"
        assert activities[2]["action"] == "login"
        
        # Test activity filtering
        login_activities = user.get_activities_by_type("login")
        assert len(login_activities) == 1
        assert login_activities[0]["metadata"]["ip"] == "192.168.1.1"


class TestUserAuthentication:
    """Test cases for user authentication flows."""
    
    @pytest.mark.asyncio
    async def test_complete_login_flow(self, db_session: AsyncSession):
        """Test complete login flow with all checks."""
        password = "SecurePassword123!"
        user = await create_test_user()
        user.set_password(password)
        user.email_verified = True
        await db_session.commit()
        
        # Successful login
        login_result = await user.authenticate(
            password=password,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        assert login_result["success"] is True
        assert "session_token" in login_result
        assert "requires_2fa" in login_result
        assert user.last_login_at is not None
        assert user.failed_login_attempts == 0
        
        # Failed login
        login_result = await user.authenticate(
            password="WrongPassword",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        
        assert login_result["success"] is False
        assert login_result["error"] == "Invalid credentials"
        assert user.failed_login_attempts == 1
    
    @pytest.mark.asyncio
    async def test_login_with_2fa(self, db_session: AsyncSession):
        """Test login flow with two-factor authentication."""
        password = "SecurePassword123!"
        user = await create_test_user()
        user.set_password(password)
        user.email_verified = True
        user.enable_two_factor()
        await db_session.commit()
        
        # First step: password
        login_result = await user.authenticate(
            password=password,
            ip_address="192.168.1.1"
        )
        
        assert login_result["success"] is True
        assert login_result["requires_2fa"] is True
        assert "partial_token" in login_result
        
        # Second step: OTP
        otp = user.generate_otp()
        otp_result = await user.verify_2fa_login(
            partial_token=login_result["partial_token"],
            otp=otp
        )
        
        assert otp_result["success"] is True
        assert "session_token" in otp_result
        assert user.last_login_at is not None
    
    @pytest.mark.asyncio
    async def test_login_security_checks(self, db_session: AsyncSession):
        """Test various security checks during login."""
        password = "SecurePassword123!"
        
        # Unverified email
        user = await create_test_user()
        user.set_password(password)
        user.email_verified = False
        
        login_result = await user.authenticate(password=password)
        assert login_result["success"] is False
        assert login_result["error"] == "Email not verified"
        
        # Suspended account
        user.email_verified = True
        user.suspend(reason="Security check", duration_hours=24)
        
        login_result = await user.authenticate(password=password)
        assert login_result["success"] is False
        assert login_result["error"] == "Account suspended"
        
        # Deleted account
        user.status = UserStatus.ACTIVE
        user.soft_delete()
        
        login_result = await user.authenticate(password=password)
        assert login_result["success"] is False
        assert login_result["error"] == "Account not found"
    
    @pytest.mark.asyncio
    async def test_password_complexity_requirements(self, db_session: AsyncSession):
        """Test password complexity validation."""
        user = await create_test_user()
        
        # Too short
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            user.set_password("Short1!")
        
        # No uppercase
        with pytest.raises(ValueError, match="Password must contain uppercase letter"):
            user.set_password("lowercase123!")
        
        # No lowercase
        with pytest.raises(ValueError, match="Password must contain lowercase letter"):
            user.set_password("UPPERCASE123!")
        
        # No number
        with pytest.raises(ValueError, match="Password must contain number"):
            user.set_password("NoNumbers!")
        
        # No special character
        with pytest.raises(ValueError, match="Password must contain special character"):
            user.set_password("NoSpecial123")
        
        # Valid password
        user.set_password("ValidPass123!")
        assert user.password_hash is not None


class TestUserPermissions:
    """Test cases for user permissions and authorization."""
    
    @pytest.mark.asyncio
    async def test_role_based_permissions(self, db_session: AsyncSession):
        """Test role-based permission checks."""
        admin = await create_test_user(role=UserRole.ADMIN)
        manager = await create_test_user(role=UserRole.MANAGER)
        chatter = await create_test_user(role=UserRole.CHATTER)
        model = await create_test_user(role=UserRole.MODEL)
        
        # Permission matrix
        permissions = {
            "manage_users": [UserRole.ADMIN, UserRole.MANAGER],
            "manage_agency": [UserRole.ADMIN],
            "view_all_models": [UserRole.ADMIN, UserRole.MANAGER],
            "chat_as_model": [UserRole.CHATTER, UserRole.MANAGER, UserRole.ADMIN],
            "view_own_earnings": [UserRole.MODEL],
            "manage_finances": [UserRole.ADMIN, UserRole.MANAGER],
            "view_analytics": [UserRole.ADMIN, UserRole.MANAGER, UserRole.MODEL],
            "manage_content": [UserRole.ADMIN, UserRole.MANAGER, UserRole.MODEL],
            "manage_subscriptions": [UserRole.ADMIN, UserRole.MANAGER]
        }
        
        # Test each permission
        for permission, allowed_roles in permissions.items():
            assert admin.has_permission(permission) == (UserRole.ADMIN in allowed_roles)
            assert manager.has_permission(permission) == (UserRole.MANAGER in allowed_roles)
            assert chatter.has_permission(permission) == (UserRole.CHATTER in allowed_roles)
            assert model.has_permission(permission) == (UserRole.MODEL in allowed_roles)
    
    @pytest.mark.asyncio
    async def test_resource_access_control(self, db_session: AsyncSession):
        """Test resource-level access control."""
        agency1 = await create_test_agency()
        agency2 = await create_test_agency()
        
        # Users from different agencies
        user1 = await create_test_user(role=UserRole.MANAGER, agency_id=agency1.id)
        user2 = await create_test_user(role=UserRole.MANAGER, agency_id=agency2.id)
        
        # Model from agency1
        from models.model import Model
        model = Model(
            user_id=str(uuid4()),
            agency_id=agency1.id,
            name="Test Model"
        )
        db_session.add(model)
        await db_session.commit()
        
        # User1 can access their agency's model
        assert user1.can_access_model(model.id) is True
        
        # User2 cannot access another agency's model
        assert user2.can_access_model(model.id) is False
        
        # Admin from agency1 can access
        admin1 = await create_test_user(role=UserRole.ADMIN, agency_id=agency1.id)
        assert admin1.can_access_model(model.id) is True
    
    @pytest.mark.asyncio
    async def test_custom_permissions(self, db_session: AsyncSession):
        """Test custom permission assignments."""
        user = await create_test_user(role=UserRole.CHATTER)
        
        # Default chatter cannot manage content
        assert user.has_permission("manage_content") is False
        
        # Grant custom permission
        user.grant_permission("manage_content", granted_by="admin_123")
        assert user.has_permission("manage_content") is True
        
        # Revoke custom permission
        user.revoke_permission("manage_content", revoked_by="admin_123")
        assert user.has_permission("manage_content") is False
        
        # Test permission history
        history = user.get_permission_history("manage_content")
        assert len(history) == 2
        assert history[0]["action"] == "revoked"
        assert history[1]["action"] == "granted"