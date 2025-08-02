"""
Integration tests for bulk operations system.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from core.bulk_operations.bulk_processor import bulk_processor
from core.bulk_operations.models import (
    BulkOperation, BulkOperationItem, BulkOperationType,
    BulkOperationStatus, BulkOperationTemplate, BulkOperationLimit
)
from core.bulk_operations.handlers import register_bulk_handlers
from core.domain.models import User, Agency, UserRole
from modules.financial.domain.models import Payout


class TestBulkProcessor:
    
    @pytest.mark.asyncio
    async def test_create_bulk_operation(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test creating a bulk operation."""
        # Create test users to operate on
        users = []
        for i in range(5):
            user = User(
                email=f"bulk_test_{i}@example.com",
                username=f"bulk_test_{i}",
                first_name=f"Test{i}",
                last_name="User",
                role=UserRole.MEMBER,
                agency_id=test_user.agency_id,
                hashed_password="dummy"
            )
            db_session.add(user)
            users.append(user)
        await db_session.commit()
        
        # Create bulk operation
        entity_ids = [str(user.id) for user in users]
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=entity_ids,
            params={"is_active": False},
            user=test_user,
            session=db_session
        )
        
        assert operation is not None
        assert operation.operation_type == BulkOperationType.USER_UPDATE
        assert operation.total_count == 5
        assert operation.status == BulkOperationStatus.PENDING
        assert len(operation.items) == 5
    
    @pytest.mark.asyncio
    async def test_process_bulk_operation(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test processing a bulk operation."""
        # Register handlers
        register_bulk_handlers()
        
        # Create test users
        users = []
        for i in range(3):
            user = User(
                email=f"process_test_{i}@example.com",
                username=f"process_test_{i}",
                first_name=f"Process{i}",
                last_name="Test",
                role=UserRole.MEMBER,
                agency_id=test_user.agency_id,
                is_active=True,
                hashed_password="dummy"
            )
            db_session.add(user)
            users.append(user)
        await db_session.commit()
        
        # Create and process operation
        entity_ids = [str(user.id) for user in users]
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_DEACTIVATE,
            entity_type="users",
            entity_ids=entity_ids,
            params={},
            user=test_user,
            session=db_session
        )
        
        # Process the operation
        await bulk_processor.process_operation(str(operation.id), db_session)
        
        # Verify results
        await db_session.refresh(operation)
        assert operation.status == BulkOperationStatus.COMPLETED
        assert operation.processed_count == 3
        assert operation.success_count == 3
        assert operation.failed_count == 0
        
        # Verify users were deactivated
        for user in users:
            await db_session.refresh(user)
            assert user.is_active is False
    
    @pytest.mark.asyncio
    async def test_bulk_operation_validation(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test bulk operation validation."""
        # Try to update with invalid email
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=[str(test_user.id)],
            params={"email": "existing@example.com"},  # Assume this exists
            user=test_user,
            session=db_session,
            validation_rules={"check_email_unique": True}
        )
        
        # Process should handle validation
        await bulk_processor.process_operation(str(operation.id), db_session)
        
        await db_session.refresh(operation)
        # Should complete but with potential validation failures
        assert operation.status == BulkOperationStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_bulk_operation_limits(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test bulk operation limits."""
        # Create a limit
        limit = BulkOperationLimit(
            user_id=test_user.id,
            operation_type=BulkOperationType.USER_UPDATE,
            max_entities_per_operation=2,
            max_operations_per_hour=1
        )
        db_session.add(limit)
        await db_session.commit()
        
        # Try to exceed entity limit
        with pytest.raises(ValueError, match="Too many entities"):
            await bulk_processor.create_operation(
                operation_type=BulkOperationType.USER_UPDATE,
                entity_type="users",
                entity_ids=[str(uuid4()) for _ in range(5)],
                params={},
                user=test_user,
                session=db_session
            )
        
        # Create within limit
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=[str(uuid4()) for _ in range(2)],
            params={},
            user=test_user,
            session=db_session
        )
        assert operation is not None
        
        # Try to exceed hourly limit
        with pytest.raises(ValueError, match="Hourly operation limit"):
            await bulk_processor.create_operation(
                operation_type=BulkOperationType.USER_UPDATE,
                entity_type="users",
                entity_ids=[str(uuid4())],
                params={},
                user=test_user,
                session=db_session
            )
    
    @pytest.mark.asyncio
    async def test_bulk_operation_cancel(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test cancelling a bulk operation."""
        # Create operation
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=[str(uuid4()) for _ in range(10)],
            params={"is_active": False},
            user=test_user,
            session=db_session,
            scheduled_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        assert operation.status == BulkOperationStatus.SCHEDULED
        
        # Cancel it
        success = await bulk_processor.cancel_operation(
            str(operation.id),
            test_user,
            db_session
        )
        
        assert success is True
        await db_session.refresh(operation)
        assert operation.status == BulkOperationStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_bulk_operation_progress(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test getting bulk operation progress."""
        # Create operation
        operation = await bulk_processor.create_operation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=[str(uuid4()) for _ in range(5)],
            params={},
            user=test_user,
            session=db_session
        )
        
        # Get progress
        progress = await bulk_processor.get_progress(str(operation.id), db_session)
        
        assert progress.operation_id == str(operation.id)
        assert progress.status == "pending"
        assert progress.total_count == 5
        assert progress.processed_count == 0
        assert progress.progress_percentage == 0


class TestBulkOperationHandlers:
    
    @pytest.mark.asyncio
    async def test_user_update_handler(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test user update bulk handler."""
        from core.bulk_operations.handlers import handle_user_update
        
        # Update user
        result = await handle_user_update(
            str(test_user.id),
            {"first_name": "Updated", "last_name": "Name"},
            db_session
        )
        
        assert "changes" in result
        assert result["changes"]["first_name"] == "Updated"
        assert result["changes"]["last_name"] == "Name"
        
        # Verify update
        await db_session.refresh(test_user)
        assert test_user.first_name == "Updated"
        assert test_user.last_name == "Name"
    
    @pytest.mark.asyncio
    async def test_payout_schedule_handler(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test payout schedule bulk handler."""
        from core.bulk_operations.handlers import handle_payout_schedule
        
        # Create test payout
        payout = Payout(
            user_id=test_user.id,
            agency_id=test_user.agency_id,
            amount=100.0,
            currency="USD",
            status="pending",
            payment_method="bank_transfer"
        )
        db_session.add(payout)
        await db_session.commit()
        
        # Schedule payout
        scheduled_date = datetime.utcnow() + timedelta(days=1)
        result = await handle_payout_schedule(
            str(payout.id),
            {"scheduled_date": scheduled_date.isoformat()},
            db_session
        )
        
        assert result["changes"]["status"] == "scheduled"
        
        # Verify update
        await db_session.refresh(payout)
        assert payout.status == "scheduled"
        assert payout.scheduled_date is not None


class TestBulkOperationAPI:
    
    @pytest.mark.asyncio
    async def test_create_bulk_operation_api(
        self,
        client,
        admin_headers,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test creating bulk operation via API."""
        # Create test users
        users = []
        for i in range(3):
            user = User(
                email=f"api_bulk_{i}@example.com",
                username=f"api_bulk_{i}",
                first_name=f"API{i}",
                last_name="Test",
                role=UserRole.MEMBER,
                agency_id=test_user.agency_id,
                hashed_password="dummy"
            )
            db_session.add(user)
            users.append(user)
        await db_session.commit()
        
        # Create bulk operation
        response = await client.post(
            "/api/v1/bulk-operations/",
            json={
                "operation_type": "user_update",
                "entity_type": "users",
                "entity_ids": [str(user.id) for user in users],
                "operation_params": {"is_active": False}
            },
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert data["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_list_bulk_operations_api(
        self,
        client,
        admin_headers,
        db_session: AsyncSession,
        test_agency: Agency
    ):
        """Test listing bulk operations via API."""
        # Create some operations
        for i in range(3):
            operation = BulkOperation(
                operation_type=BulkOperationType.USER_UPDATE,
                entity_type="users",
                entity_ids=[],
                total_count=0,
                created_by_id=test_agency.owner_id,
                agency_id=test_agency.id
            )
            db_session.add(operation)
        await db_session.commit()
        
        # List operations
        response = await client.get(
            "/api/v1/bulk-operations/",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
    
    @pytest.mark.asyncio
    async def test_bulk_operation_progress_api(
        self,
        client,
        admin_headers,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test getting operation progress via API."""
        # Create operation
        operation = BulkOperation(
            operation_type=BulkOperationType.USER_UPDATE,
            entity_type="users",
            entity_ids=[str(test_user.id)],
            total_count=1,
            created_by_id=test_user.id,
            agency_id=test_user.agency_id,
            progress_percentage=50,
            processed_count=1,
            success_count=1
        )
        db_session.add(operation)
        await db_session.commit()
        
        # Get progress
        response = await client.get(
            f"/api/v1/bulk-operations/{operation.id}/progress",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["progress_percentage"] == 50
        assert data["processed_count"] == 1
    
    @pytest.mark.asyncio
    async def test_bulk_templates_api(
        self,
        client,
        admin_headers,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test bulk operation templates via API."""
        # Create template
        response = await client.post(
            "/api/v1/bulk-operations/templates",
            json={
                "name": "Test Template",
                "description": "Test bulk operation template",
                "operation_type": "user_update",
                "default_params": {"is_active": True}
            },
            headers=admin_headers
        )
        
        assert response.status_code == 200
        
        # List templates
        response = await client.get(
            "/api/v1/bulk-operations/templates",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert any(t["name"] == "Test Template" for t in data)
    
    @pytest.mark.asyncio
    async def test_bulk_limits_api(
        self,
        client,
        admin_headers,
        super_admin_headers,
        test_user: User
    ):
        """Test bulk operation limits via API."""
        # Get current limits
        response = await client.get(
            "/api/v1/bulk-operations/limits",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "user_limits" in data
        assert "agency_limits" in data
        
        # Update limits (requires super admin)
        response = await client.put(
            f"/api/v1/bulk-operations/limits/{test_user.id}",
            json={
                "max_entities_per_operation": 500,
                "max_operations_per_day": 50
            },
            headers=super_admin_headers
        )
        
        assert response.status_code == 200