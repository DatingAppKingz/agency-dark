"""
Test script for Comprehensive Audit Trail system.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables
os.environ["DATABASE_URL"] = "postgresql://mariuszbudzisz@localhost/agencydark_dev"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["DISABLE_ML"] = "true"

import logging
logging.basicConfig(level=logging.INFO)

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from models.user import User, UserRole
from models.audit_log import AuditLog, AuditAction, AuditSeverity
from core.audit.audit_service import audit_service
from core.audit.decorators import audit_log, audit_financial, AuditContext


async def get_test_user(db: AsyncSession) -> User:
    """Get or create a test user."""
    result = await db.execute(
        select(User).where(User.email == "admin@agency.com")
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            email="admin@agency.com",
            username="admin",
            first_name="Admin",
            last_name="User",
            role=UserRole.AGENCY_ADMIN,
            agency_id="11111111-1111-1111-1111-111111111111",
            hashed_password="dummy_hash",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user


async def test_basic_audit_logging(db: AsyncSession, user: User):
    """Test basic audit logging."""
    print("\n=== Testing Basic Audit Logging ===")
    
    # Log a simple action
    audit_log = await audit_service.log(
        db=db,
        action=AuditAction.USER_UPDATED,
        user=user,
        resource_type="user",
        resource_id=str(user.id),
        resource_name=user.email,
        description="Updated user profile",
        metadata={"fields_updated": ["first_name", "last_name"]},
        ip_address="127.0.0.1",
        severity=AuditSeverity.INFO
    )
    
    if audit_log:
        print(f"✅ Created audit log: {audit_log.id}")
        print(f"   Action: {audit_log.action.value}")
        print(f"   Description: {audit_log.description}")
        print(f"   Risk Score: {audit_log.risk_score}")


async def test_login_audit(db: AsyncSession, user: User):
    """Test login audit logging."""
    print("\n=== Testing Login Audit ===")
    
    # Successful login
    await audit_service.log_login(
        db=db,
        user=user,
        success=True,
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    )
    print("✅ Logged successful login")
    
    # Failed login
    await audit_service.log_login(
        db=db,
        user=user,
        success=False,
        ip_address="192.168.1.100",
        failure_reason="Invalid password"
    )
    print("✅ Logged failed login")


async def test_financial_audit(db: AsyncSession, user: User):
    """Test financial action audit logging."""
    print("\n=== Testing Financial Audit ===")
    
    await audit_service.log_financial_action(
        db=db,
        user=user,
        action=AuditAction.TRANSACTION_CREATED,
        amount=1500.00,
        currency="USD",
        transaction_id="TXN-12345",
        payment_method="credit_card"
    )
    print("✅ Logged financial transaction")


async def test_batch_logging(db: AsyncSession, user: User):
    """Test batch audit logging."""
    print("\n=== Testing Batch Logging ===")
    
    async with AuditContext(db) as audit_ctx:
        # Log multiple events in batch
        for i in range(5):
            await audit_ctx.log(
                action=AuditAction.DATA_EXPORTED,
                user=user,
                resource_type="report",
                resource_id=f"report-{i}",
                description=f"Exported report #{i}",
                severity=AuditSeverity.INFO
            )
    
    print("✅ Batch logged 5 events")


async def test_audit_search(db: AsyncSession, user: User):
    """Test searching audit logs."""
    print("\n=== Testing Audit Search ===")
    
    # Search recent logs
    logs, total = await audit_service.search(
        db=db,
        user=user,
        start_date=datetime.utcnow() - timedelta(hours=1),
        actions=[AuditAction.USER_UPDATED, AuditAction.LOGIN],
        limit=10
    )
    
    print(f"Found {len(logs)} logs (total: {total})")
    for log in logs[:3]:
        print(f"  - {log.timestamp}: {log.action.value} - {log.description}")


async def test_user_activity_summary(db: AsyncSession, user: User):
    """Test user activity summary."""
    print("\n=== Testing User Activity Summary ===")
    
    summary = await audit_service.get_user_activity_summary(
        db=db,
        user_id=str(user.id),
        days=7
    )
    
    print(f"User Activity Summary (last {summary['period_days']} days):")
    print(f"  Total Actions: {summary['total_actions']}")
    print(f"  High Risk Events: {summary['high_risk_events']}")
    
    if summary['action_breakdown']:
        print("  Action Breakdown:")
        for action, count in summary['action_breakdown'].items():
            print(f"    - {action}: {count}")


async def test_risk_scoring(db: AsyncSession, user: User):
    """Test risk scoring for different actions."""
    print("\n=== Testing Risk Scoring ===")
    
    test_cases = [
        (AuditAction.LOGIN, AuditSeverity.INFO, "Normal login"),
        (AuditAction.LOGIN_FAILED, AuditSeverity.WARNING, "Failed login"),
        (AuditAction.USER_DELETED, AuditSeverity.WARNING, "User deletion"),
        (AuditAction.API_KEY_CREATED, AuditSeverity.INFO, "API key creation"),
        (AuditAction.DATA_EXPORTED, AuditSeverity.INFO, "Data export"),
    ]
    
    for action, severity, description in test_cases:
        audit_log = await audit_service.log(
            db=db,
            action=action,
            user=user,
            description=description,
            severity=severity,
            ip_address="127.0.0.1"
        )
        
        if audit_log:
            print(f"  {action.value}: Risk Score = {audit_log.risk_score}")


async def test_decorator_usage(db: AsyncSession):
    """Test audit decorators."""
    print("\n=== Testing Audit Decorators ===")
    
    # Simulate using decorators
    @audit_log(
        action=AuditAction.USER_CREATED,
        resource_type="user",
        resource_id_param="new_user_id"
    )
    async def create_user_endpoint(new_user_id: str, current_user: User, db: AsyncSession):
        print(f"    Creating user {new_user_id}")
        return {"id": new_user_id, "status": "created"}
    
    @audit_financial(
        action=AuditAction.PAYOUT_INITIATED,
        amount_param="payout_amount"
    )
    async def initiate_payout(payout_amount: float, currency: str, current_user: User, db: AsyncSession):
        print(f"    Initiating payout of {payout_amount} {currency}")
        return {"status": "initiated", "amount": payout_amount}
    
    print("✅ Decorators defined successfully")


async def test_compliance_features(db: AsyncSession, user: User):
    """Test compliance-related features."""
    print("\n=== Testing Compliance Features ===")
    
    # Log GDPR-related action
    audit_log = await audit_service.log(
        db=db,
        action=AuditAction.USER_DATA_REQUESTED,
        user=user,
        resource_type="user",
        resource_id=str(user.id),
        description="User requested their data under GDPR",
        metadata={
            "request_type": "data_access",
            "legal_basis": "GDPR Article 15"
        },
        compliance_tags=["gdpr", "data_access"],
        severity=AuditSeverity.INFO
    )
    
    if audit_log:
        print("✅ Logged GDPR compliance action")
    
    # Log data deletion
    await audit_service.log(
        db=db,
        action=AuditAction.USER_DATA_DELETED,
        user=user,
        resource_type="user",
        resource_id="deleted-user-123",
        description="User data deleted per GDPR request",
        metadata={
            "deletion_type": "full",
            "data_categories": ["personal", "usage", "preferences"]
        },
        compliance_tags=["gdpr", "right_to_erasure"],
        severity=AuditSeverity.WARNING
    )
    
    print("✅ Logged data deletion for compliance")


async def main():
    """Run all audit logging tests."""
    print("Comprehensive Audit Trail Test Suite")
    print("=" * 50)
    
    # Create database engine
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False
    )
    
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as db:
        try:
            # Get test user
            user = await get_test_user(db)
            print(f"\nUsing test user: {user.email}")
            
            # Run tests
            await test_basic_audit_logging(db, user)
            await test_login_audit(db, user)
            await test_financial_audit(db, user)
            await test_batch_logging(db, user)
            await test_risk_scoring(db, user)
            await test_compliance_features(db, user)
            await test_audit_search(db, user)
            await test_user_activity_summary(db, user)
            await test_decorator_usage(db)
            
            print("\n\n✅ All audit logging tests completed successfully!")
            
        except Exception as e:
            print(f"\n\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())