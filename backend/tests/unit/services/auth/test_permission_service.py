"""Comprehensive tests for permission service."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Set

from services.auth.permission_service import (
    PermissionService,
    Permission,
    PermissionScope,
    PermissionLevel,
    ResourceType,
    RolePermissionMapping,
    DynamicPermission,
    PermissionPolicy
)
from models.user import User, UserRole, UserStatus
from models.agency import Agency
from models.model import Model
from tests.factories import create_test_user, create_test_agency, create_test_model


class TestPermissionService:
    """Test cases for permission service."""
    
    @pytest.fixture
    def permission_service(self):
        """Create permission service instance."""
        return PermissionService()
    
    @pytest.fixture
    def role_permissions(self):
        """Define role-based permission mappings."""
        return {
            UserRole.ADMIN: {
                "users": ["create", "read", "update", "delete"],
                "agency": ["create", "read", "update", "delete"],
                "models": ["create", "read", "update", "delete"],
                "finances": ["read", "update", "approve"],
                "analytics": ["read", "export"],
                "settings": ["read", "update"]
            },
            UserRole.MANAGER: {
                "users": ["create", "read", "update"],
                "models": ["read", "update"],
                "finances": ["read", "update"],
                "analytics": ["read", "export"],
                "settings": ["read"]
            },
            UserRole.CHATTER: {
                "models": ["read"],
                "chat": ["read", "write"],
                "analytics": ["read"]
            },
            UserRole.MODEL: {
                "profile": ["read", "update"],
                "finances": ["read"],
                "analytics": ["read"],
                "content": ["create", "read", "update", "delete"]
            }
        }
    
    @pytest.mark.asyncio
    async def test_check_permission_basic(self, permission_service, db_session):
        """Test basic permission checking."""
        admin = await create_test_user(role=UserRole.ADMIN)
        model = await create_test_user(role=UserRole.MODEL)
        
        # Admin has user management permission
        assert await permission_service.check_permission(
            user=admin,
            resource="users",
            action="create"
        ) is True
        
        # Model doesn't have user management permission
        assert await permission_service.check_permission(
            user=model,
            resource="users",
            action="create"
        ) is False
        
        # Model has own profile permission
        assert await permission_service.check_permission(
            user=model,
            resource="profile",
            action="update"
        ) is True
    
    @pytest.mark.asyncio
    async def test_check_resource_permission(self, permission_service, db_session):
        """Test resource-specific permission checking."""
        agency1 = await create_test_agency(name="Agency 1")
        agency2 = await create_test_agency(name="Agency 2")
        
        manager1 = await create_test_user(role=UserRole.MANAGER, agency_id=agency1.id)
        manager2 = await create_test_user(role=UserRole.MANAGER, agency_id=agency2.id)
        
        model1 = await create_test_model(agency=agency1)
        
        # Manager can access own agency's model
        assert await permission_service.check_resource_permission(
            user=manager1,
            resource_type=ResourceType.MODEL,
            resource_id=model1.id,
            action="read"
        ) is True
        
        # Manager cannot access other agency's model
        assert await permission_service.check_resource_permission(
            user=manager2,
            resource_type=ResourceType.MODEL,
            resource_id=model1.id,
            action="read"
        ) is False
        
        # Admin can access any model
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency1.id)
        assert await permission_service.check_resource_permission(
            user=admin,
            resource_type=ResourceType.MODEL,
            resource_id=model1.id,
            action="read"
        ) is True
    
    @pytest.mark.asyncio
    async def test_hierarchical_permissions(self, permission_service, db_session):
        """Test hierarchical permission inheritance."""
        agency = await create_test_agency()
        
        # Create hierarchy: Admin > Manager > Chatter
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency.id)
        manager = await create_test_user(role=UserRole.MANAGER, agency_id=agency.id)
        chatter = await create_test_user(role=UserRole.CHATTER, agency_id=agency.id)
        
        # Test permission inheritance
        permissions_to_test = [
            ("users", "create"),    # Admin only
            ("models", "update"),   # Admin & Manager
            ("chat", "write"),      # All three
            ("agency", "delete")    # Admin only
        ]
        
        for resource, action in permissions_to_test:
            admin_has = await permission_service.check_permission(admin, resource, action)
            manager_has = await permission_service.check_permission(manager, resource, action)
            chatter_has = await permission_service.check_permission(chatter, resource, action)
            
            if resource == "users" and action == "create":
                assert admin_has is True
                assert manager_has is True  # Managers can create users
                assert chatter_has is False
            elif resource == "models" and action == "update":
                assert admin_has is True
                assert manager_has is True
                assert chatter_has is False
            elif resource == "chat" and action == "write":
                assert admin_has is True
                assert manager_has is True
                assert chatter_has is True
            elif resource == "agency" and action == "delete":
                assert admin_has is True
                assert manager_has is False
                assert chatter_has is False
    
    @pytest.mark.asyncio
    async def test_dynamic_permissions(self, permission_service, db_session):
        """Test dynamically assigned permissions."""
        user = await create_test_user(role=UserRole.CHATTER)
        
        # Chatter normally can't manage content
        assert await permission_service.check_permission(
            user=user,
            resource="content",
            action="create"
        ) is False
        
        # Grant dynamic permission
        await permission_service.grant_permission(
            user_id=user.id,
            permission="content:create",
            granted_by="admin123",
            expires_at=datetime.utcnow() + timedelta(days=30),
            reason="Temporary content management duties"
        )
        
        # Now should have permission
        assert await permission_service.check_permission(
            user=user,
            resource="content",
            action="create"
        ) is True
        
        # Revoke permission
        await permission_service.revoke_permission(
            user_id=user.id,
            permission="content:create",
            revoked_by="admin123",
            reason="Duties completed"
        )
        
        # Permission should be gone
        assert await permission_service.check_permission(
            user=user,
            resource="content",
            action="create"
        ) is False
    
    @pytest.mark.asyncio
    async def test_permission_expiration(self, permission_service, db_session):
        """Test permission expiration handling."""
        user = await create_test_user(role=UserRole.MODEL)
        
        # Grant temporary permission
        await permission_service.grant_permission(
            user_id=user.id,
            permission="analytics:export",
            granted_by="admin123",
            expires_at=datetime.utcnow() + timedelta(seconds=1)
        )
        
        # Should have permission immediately
        assert await permission_service.check_permission(
            user=user,
            resource="analytics",
            action="export"
        ) is True
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Permission should be expired
        assert await permission_service.check_permission(
            user=user,
            resource="analytics",
            action="export"
        ) is False
    
    @pytest.mark.asyncio
    async def test_permission_groups(self, permission_service, db_session):
        """Test permission groups and bulk assignments."""
        agency = await create_test_agency()
        
        # Create multiple users
        users = []
        for i in range(3):
            user = await create_test_user(
                role=UserRole.CHATTER,
                agency_id=agency.id,
                username=f"chatter{i}"
            )
            users.append(user)
        
        # Create permission group
        group_id = await permission_service.create_permission_group(
            name="Content Moderators",
            permissions=[
                "content:read",
                "content:update",
                "content:delete",
                "reports:create"
            ],
            created_by="admin123"
        )
        
        # Assign group to users
        for user in users:
            await permission_service.assign_to_group(
                user_id=user.id,
                group_id=group_id
            )
        
        # All users should have group permissions
        for user in users:
            assert await permission_service.check_permission(
                user=user,
                resource="content",
                action="delete"
            ) is True
            assert await permission_service.check_permission(
                user=user,
                resource="reports",
                action="create"
            ) is True
        
        # Remove one user from group
        await permission_service.remove_from_group(
            user_id=users[0].id,
            group_id=group_id
        )
        
        # That user should lose permissions
        assert await permission_service.check_permission(
            user=users[0],
            resource="content",
            action="delete"
        ) is False
    
    @pytest.mark.asyncio
    async def test_permission_policies(self, permission_service, db_session):
        """Test complex permission policies."""
        agency = await create_test_agency()
        user = await create_test_user(role=UserRole.MANAGER, agency_id=agency.id)
        
        # Create time-based policy
        await permission_service.create_policy(
            name="Business Hours Only",
            conditions={
                "time_range": {
                    "start": "09:00",
                    "end": "17:00",
                    "timezone": "UTC",
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
                }
            },
            permissions=["finances:approve"],
            applies_to_roles=[UserRole.MANAGER]
        )
        
        # During business hours
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 0)  # Monday 10 AM
            mock_datetime.strptime.side_effect = datetime.strptime
            
            assert await permission_service.check_permission(
                user=user,
                resource="finances",
                action="approve",
                context={"check_policies": True}
            ) is True
        
        # Outside business hours
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 20, 0)  # Monday 8 PM
            mock_datetime.strptime.side_effect = datetime.strptime
            
            assert await permission_service.check_permission(
                user=user,
                resource="finances",
                action="approve",
                context={"check_policies": True}
            ) is False
    
    @pytest.mark.asyncio
    async def test_permission_delegation(self, permission_service, db_session):
        """Test permission delegation capabilities."""
        agency = await create_test_agency()
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency.id)
        manager = await create_test_user(role=UserRole.MANAGER, agency_id=agency.id)
        
        # Admin delegates user creation permission to manager
        delegation = await permission_service.delegate_permission(
            from_user=admin,
            to_user=manager,
            permission="users:delete",  # Managers don't normally have this
            can_sub_delegate=False,
            expires_at=datetime.utcnow() + timedelta(days=7),
            conditions={"max_uses": 5}
        )
        
        # Manager should now have the delegated permission
        assert await permission_service.check_permission(
            user=manager,
            resource="users",
            action="delete",
            context={"delegation_id": delegation.id}
        ) is True
        
        # Track usage
        for i in range(5):
            await permission_service.use_delegated_permission(
                delegation_id=delegation.id,
                used_by=manager.id
            )
        
        # After max uses, permission should be revoked
        assert await permission_service.check_permission(
            user=manager,
            resource="users",
            action="delete",
            context={"delegation_id": delegation.id}
        ) is False
    
    @pytest.mark.asyncio
    async def test_permission_audit_trail(self, permission_service, db_session):
        """Test permission audit trail functionality."""
        user = await create_test_user(role=UserRole.CHATTER)
        
        # Grant permission
        await permission_service.grant_permission(
            user_id=user.id,
            permission="models:update",
            granted_by="admin123",
            reason="Covering for sick colleague"
        )
        
        # Use permission
        await permission_service.check_permission(
            user=user,
            resource="models",
            action="update",
            audit=True
        )
        
        # Revoke permission
        await permission_service.revoke_permission(
            user_id=user.id,
            permission="models:update",
            revoked_by="admin123",
            reason="Colleague returned"
        )
        
        # Get audit trail
        audit_trail = await permission_service.get_permission_audit_trail(
            user_id=user.id,
            permission="models:update"
        )
        
        assert len(audit_trail) == 3
        assert audit_trail[0]["action"] == "granted"
        assert audit_trail[1]["action"] == "checked"
        assert audit_trail[2]["action"] == "revoked"
    
    @pytest.mark.asyncio
    async def test_permission_caching(self, permission_service):
        """Test permission caching for performance."""
        user = await create_test_user(role=UserRole.MANAGER)
        
        with patch.object(permission_service, "_load_permissions") as mock_load:
            mock_load.return_value = {"models": ["read", "update"]}
            
            # First check - should load from database
            result1 = await permission_service.check_permission(
                user=user,
                resource="models",
                action="read"
            )
            assert result1 is True
            assert mock_load.call_count == 1
            
            # Second check - should use cache
            result2 = await permission_service.check_permission(
                user=user,
                resource="models",
                action="read"
            )
            assert result2 is True
            assert mock_load.call_count == 1  # Not called again
            
            # Different permission - still uses cache
            result3 = await permission_service.check_permission(
                user=user,
                resource="models",
                action="update"
            )
            assert result3 is True
            assert mock_load.call_count == 1
            
            # Clear cache
            await permission_service.clear_permission_cache(user.id)
            
            # Next check should reload
            result4 = await permission_service.check_permission(
                user=user,
                resource="models",
                action="read"
            )
            assert result4 is True
            assert mock_load.call_count == 2
    
    @pytest.mark.asyncio
    async def test_bulk_permission_check(self, permission_service, db_session):
        """Test bulk permission checking for efficiency."""
        user = await create_test_user(role=UserRole.MANAGER)
        
        # Check multiple permissions at once
        permissions_to_check = [
            ("models", "read"),
            ("models", "update"),
            ("models", "delete"),
            ("users", "create"),
            ("users", "delete"),
            ("finances", "read"),
            ("finances", "approve")
        ]
        
        results = await permission_service.check_permissions_bulk(
            user=user,
            permissions=permissions_to_check
        )
        
        # Manager should have some but not all
        expected = {
            ("models", "read"): True,
            ("models", "update"): True,
            ("models", "delete"): False,
            ("users", "create"): True,
            ("users", "delete"): False,
            ("finances", "read"): True,
            ("finances", "approve"): False
        }
        
        assert results == expected
    
    @pytest.mark.asyncio
    async def test_permission_inheritance_override(self, permission_service, db_session):
        """Test permission inheritance with explicit overrides."""
        agency = await create_test_agency()
        manager = await create_test_user(role=UserRole.MANAGER, agency_id=agency.id)
        
        # Manager normally has models:update
        assert await permission_service.check_permission(
            user=manager,
            resource="models",
            action="update"
        ) is True
        
        # Explicitly deny this permission
        await permission_service.deny_permission(
            user_id=manager.id,
            permission="models:update",
            denied_by="admin123",
            reason="Pending investigation"
        )
        
        # Should now be denied despite role
        assert await permission_service.check_permission(
            user=manager,
            resource="models",
            action="update"
        ) is False
        
        # Remove denial
        await permission_service.remove_denial(
            user_id=manager.id,
            permission="models:update",
            removed_by="admin123"
        )
        
        # Should have permission again
        assert await permission_service.check_permission(
            user=manager,
            resource="models",
            action="update"
        ) is True
    
    @pytest.mark.asyncio
    async def test_context_aware_permissions(self, permission_service, db_session):
        """Test permissions that depend on context."""
        agency = await create_test_agency()
        model_user = await create_test_user(role=UserRole.MODEL, agency_id=agency.id)
        model = await create_test_model(agency=agency, user_id=model_user.id)
        
        other_model_user = await create_test_user(role=UserRole.MODEL, agency_id=agency.id)
        other_model = await create_test_model(agency=agency, user_id=other_model_user.id)
        
        # Model can update own profile
        assert await permission_service.check_resource_permission(
            user=model_user,
            resource_type=ResourceType.MODEL,
            resource_id=model.id,
            action="update",
            context={"owner_id": model_user.id}
        ) is True
        
        # Model cannot update another's profile
        assert await permission_service.check_resource_permission(
            user=model_user,
            resource_type=ResourceType.MODEL,
            resource_id=other_model.id,
            action="update",
            context={"owner_id": other_model_user.id}
        ) is False
    
    @pytest.mark.asyncio
    async def test_permission_templates(self, permission_service):
        """Test permission templates for common role combinations."""
        # Create permission template
        template = await permission_service.create_permission_template(
            name="Senior Chatter",
            base_role=UserRole.CHATTER,
            additional_permissions=[
                "models:update",
                "analytics:export",
                "reports:create"
            ],
            created_by="admin123"
        )
        
        # Apply template to user
        user = await create_test_user(role=UserRole.CHATTER)
        await permission_service.apply_template(
            user_id=user.id,
            template_id=template.id
        )
        
        # User should have all template permissions
        assert await permission_service.check_permission(
            user=user,
            resource="models",
            action="update"
        ) is True
        assert await permission_service.check_permission(
            user=user,
            resource="analytics",
            action="export"
        ) is True
        assert await permission_service.check_permission(
            user=user,
            resource="reports",
            action="create"
        ) is True