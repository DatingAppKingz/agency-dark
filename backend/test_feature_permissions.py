#!/usr/bin/env python3
"""
Test script for Phase 4: Feature-Specific Permissions
"""
import asyncio
import sys
from datetime import datetime, timedelta
from sqlalchemy import select

# Add the backend directory to Python path
sys.path.append('.')

from core.database import engine, get_db_context
from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, ReportType, ExportFormat,
    AnalyticsScope, MessagePermission, DataSensitivity
)
from core.security.feature_permissions.service import feature_permission_service
from core.security.feature_permissions.report_permissions import report_permission_service
from core.security.feature_permissions.export_permissions import export_permission_service
from core.security.feature_permissions.analytics_permissions import analytics_permission_service
from core.security.feature_permissions.messaging_permissions import messaging_permission_service


async def test_feature_permissions():
    """Test feature permission functionality."""
    print("\n=== Testing Phase 4: Feature-Specific Permissions ===\n")
    
    async with get_db_context() as db:
        # Get test users
        admin_user = await db.execute(
            select(User).where(User.email == "admin@agency.com")
        )
        admin_user = admin_user.scalar_one_or_none()
        
        manager_user = await db.execute(
            select(User).where(User.email == "manager@agency.com")
        )
        manager_user = manager_user.scalar_one_or_none()
        
        if not admin_user or not manager_user:
            print("❌ Test users not found. Please run migrations first.")
            return
        
        print(f"✅ Found test users: Admin ({admin_user.email}), Manager ({manager_user.email})")
        
        # Test 1: Create feature permissions
        print("\n1. Testing feature permission creation...")
        
        try:
            # Create analytics permission for managers
            analytics_perm = await feature_permission_service.create_feature_permission(
                db=db,
                user=admin_user,
                name="Manager Analytics Access",
                feature_type=FeatureType.ANALYTICS,
                role_id=manager_user.primary_role_id,
                analytics_scope=AnalyticsScope.AGENCY,
                allowed_metrics=["revenue", "performance", "engagement"],
                can_view_revenue_data=True,
                can_view_cost_data=False,
                access_start_time="08:00",
                access_end_time="20:00",
                usage_quota_daily=1000
            )
            print(f"✅ Created analytics permission: {analytics_perm.name}")
            
            # Create export permission
            export_perm = await feature_permission_service.create_feature_permission(
                db=db,
                user=admin_user,
                name="Manager Export Access",
                feature_type=FeatureType.EXPORTS,
                role_id=manager_user.primary_role_id,
                allowed_export_formats=[ExportFormat.CSV.value, ExportFormat.EXCEL.value],
                max_export_rows=50000,
                max_export_size_mb=100,
                export_rate_limit_per_hour=20,
                data_sensitivity_level=DataSensitivity.CONFIDENTIAL
            )
            print(f"✅ Created export permission: {export_perm.name}")
            
        except Exception as e:
            print(f"❌ Error creating permissions: {e}")
            return
        
        # Test 2: Check analytics access
        print("\n2. Testing analytics access control...")
        
        # Test manager access to analytics
        allowed, reason, filters = await analytics_permission_service.check_analytics_access(
            db=db,
            user=manager_user,
            analytics_type="revenue_dashboard",
            requested_scope=AnalyticsScope.AGENCY,
            metrics=["revenue", "performance"],
            date_range={
                "start": datetime.utcnow() - timedelta(days=30),
                "end": datetime.utcnow()
            }
        )
        
        if allowed:
            print(f"✅ Manager can access agency analytics")
            print(f"   Data filters: {filters}")
        else:
            print(f"❌ Manager denied analytics access: {reason}")
        
        # Test access to restricted metrics
        allowed, reason, _ = await analytics_permission_service.check_analytics_access(
            db=db,
            user=manager_user,
            analytics_type="cost_analysis",
            requested_scope=AnalyticsScope.AGENCY,
            metrics=["costs", "expenses"]
        )
        
        if not allowed:
            print(f"✅ Manager correctly denied cost data access: {reason}")
        else:
            print(f"❌ Manager incorrectly allowed cost data access")
        
        # Test 3: Check export permissions
        print("\n3. Testing export access control...")
        
        # Test allowed export
        allowed, reason, limits = await export_permission_service.can_export_data(
            db=db,
            user=manager_user,
            export_type="analytics_report",
            format=ExportFormat.EXCEL,
            estimated_rows=10000,
            estimated_size_mb=20,
            data_sensitivity=DataSensitivity.INTERNAL
        )
        
        if allowed:
            print(f"✅ Manager can export in Excel format")
            print(f"   Export limits: {limits}")
        else:
            print(f"❌ Manager denied export: {reason}")
        
        # Test denied export (wrong format)
        allowed, reason, _ = await export_permission_service.can_export_data(
            db=db,
            user=manager_user,
            export_type="analytics_report",
            format=ExportFormat.PDF,
            estimated_rows=10000
        )
        
        if not allowed:
            print(f"✅ Manager correctly denied PDF export: {reason}")
        else:
            print(f"❌ Manager incorrectly allowed PDF export")
        
        # Test 4: Check messaging permissions
        print("\n4. Testing messaging permissions...")
        
        # Create messaging permission
        messaging_perm = await feature_permission_service.create_feature_permission(
            db=db,
            user=admin_user,
            name="Manager Messaging Access",
            feature_type=FeatureType.MESSAGING,
            role_id=manager_user.primary_role_id,
            message_permissions=[
                MessagePermission.SEND_INDIVIDUAL.value,
                MessagePermission.SEND_BULK.value,
                MessagePermission.VIEW_HISTORY.value
            ],
            max_bulk_recipients=100,
            max_messages_per_hour=500,
            can_use_automation=False
        )
        print(f"✅ Created messaging permission: {messaging_perm.name}")
        
        # Test bulk messaging
        allowed, reason, limits = await messaging_permission_service.can_send_message(
            db=db,
            user=manager_user,
            message_type="bulk",
            recipient_count=50,
            is_automated=False
        )
        
        if allowed:
            print(f"✅ Manager can send bulk messages to 50 recipients")
            print(f"   Messaging limits: {limits}")
        else:
            print(f"❌ Manager denied bulk messaging: {reason}")
        
        # Test automation (should be denied)
        allowed, reason, _ = await messaging_permission_service.can_send_message(
            db=db,
            user=manager_user,
            message_type="bulk",
            recipient_count=50,
            is_automated=True
        )
        
        if not allowed:
            print(f"✅ Manager correctly denied automation: {reason}")
        else:
            print(f"❌ Manager incorrectly allowed automation")
        
        # Test 5: Time-based restrictions
        print("\n5. Testing time-based access...")
        
        # Create a permission with current time outside window
        current_hour = datetime.utcnow().hour
        restricted_start = f"{(current_hour + 2) % 24:02d}:00"
        restricted_end = f"{(current_hour + 4) % 24:02d}:00"
        
        time_perm = await feature_permission_service.create_feature_permission(
            db=db,
            user=admin_user,
            name="Time Restricted Access",
            feature_type=FeatureType.REPORTS,
            user_id=manager_user.id,
            access_start_time=restricted_start,
            access_end_time=restricted_end,
            access_timezone="UTC"
        )
        print(f"✅ Created time-restricted permission (access window: {restricted_start}-{restricted_end} UTC)")
        
        # Check access (should be denied due to time)
        allowed, reason = await feature_permission_service.check_feature_permission(
            db=db,
            user=manager_user,
            feature_type=FeatureType.REPORTS,
            action="view_report"
        )
        
        if not allowed and "time window" in reason:
            print(f"✅ Access correctly denied outside time window: {reason}")
        else:
            print(f"❌ Time restriction not working properly")
        
        # Test 6: Usage quotas
        print("\n6. Testing usage quotas...")
        
        # Check quota usage
        daily_used, daily_limit = await feature_permission_service.check_quota_usage(
            db=db,
            user=manager_user,
            permission=analytics_perm,
            period="daily"
        )
        
        print(f"✅ Analytics quota usage: {daily_used}/{daily_limit} (daily)")
        
        # Test 7: Get user's permissions
        print("\n7. Testing permission listing...")
        
        all_perms = await feature_permission_service.get_user_permissions(
            db=db,
            user=manager_user
        )
        
        print(f"✅ Manager has {len(all_perms)} total permissions:")
        for perm in all_perms:
            print(f"   - {perm.name} ({perm.feature_type.value})")
        
        # Test 8: Available dashboards
        print("\n8. Testing available dashboards...")
        
        dashboards = await analytics_permission_service.get_analytics_dashboards(
            db=db,
            user=manager_user
        )
        
        print(f"✅ Manager has access to {len(dashboards)} dashboards:")
        for dash in dashboards:
            print(f"   - {dash['name']} (scope: {dash['scope']})")
            print(f"     Available metrics: {len(dash['available_metrics'])}")
        
        print("\n✅ All feature permission tests completed!")


async def main():
    """Run all tests."""
    try:
        await test_feature_permissions()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())