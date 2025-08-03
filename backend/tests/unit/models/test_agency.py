"""Comprehensive tests for Agency model."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from models.agency import Agency, AgencyStatus, AgencyTier, AgencySettings
from models.user import User, UserRole
from models.model import Model
from tests.factories import create_test_agency, create_test_user, create_test_model


class TestAgencyModel:
    """Test cases for Agency model."""
    
    @pytest.mark.asyncio
    async def test_create_agency_with_valid_data(self, db_session: AsyncSession):
        """Test creating an agency with all valid data."""
        agency = Agency(
            name="Elite Models Agency",
            email="contact@elitemodels.com",
            phone="+1234567890",
            address="123 Fashion Ave, NY 10001",
            commission_rate=Decimal("0.20"),
            tier=AgencyTier.PROFESSIONAL,
            status=AgencyStatus.ACTIVE,
            settings={
                "auto_payout": True,
                "payout_frequency": "weekly",
                "minimum_payout": 100.00,
                "notification_preferences": {
                    "email": True,
                    "sms": False,
                    "in_app": True
                }
            }
        )
        
        db_session.add(agency)
        await db_session.commit()
        await db_session.refresh(agency)
        
        assert agency.id is not None
        assert agency.name == "Elite Models Agency"
        assert agency.commission_rate == Decimal("0.20")
        assert agency.tier == AgencyTier.PROFESSIONAL
        assert agency.status == AgencyStatus.ACTIVE
        assert agency.created_at is not None
        assert agency.settings["auto_payout"] is True
    
    @pytest.mark.asyncio
    async def test_agency_name_uniqueness(self, db_session: AsyncSession):
        """Test that agency names must be unique."""
        agency1 = await create_test_agency(name="Unique Agency")
        
        # Try to create another agency with same name
        agency2 = Agency(
            name="Unique Agency",
            email="different@email.com",
            commission_rate=Decimal("0.15")
        )
        db_session.add(agency2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_commission_rate_validation(self, db_session: AsyncSession):
        """Test commission rate validation."""
        # Test negative commission rate
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 1"):
            agency = Agency(
                name="Invalid Commission Agency",
                commission_rate=Decimal("-0.10")
            )
            agency.validate()
        
        # Test commission rate > 100%
        with pytest.raises(ValueError, match="Commission rate must be between 0 and 1"):
            agency = Agency(
                name="High Commission Agency",
                commission_rate=Decimal("1.5")
            )
            agency.validate()
        
        # Valid commission rates
        valid_rates = [Decimal("0.00"), Decimal("0.15"), Decimal("0.50"), Decimal("1.00")]
        for rate in valid_rates:
            agency = Agency(
                name=f"Agency {rate}",
                commission_rate=rate
            )
            agency.validate()  # Should not raise
    
    @pytest.mark.asyncio
    async def test_agency_tier_features(self, db_session: AsyncSession):
        """Test different agency tier features and limits."""
        # Basic tier
        basic_agency = await create_test_agency(
            name="Basic Agency",
            tier=AgencyTier.BASIC
        )
        assert basic_agency.get_model_limit() == 10
        assert basic_agency.get_user_limit() == 5
        assert basic_agency.can_use_feature("analytics") is False
        assert basic_agency.can_use_feature("basic_chat") is True
        
        # Professional tier
        pro_agency = await create_test_agency(
            name="Pro Agency",
            tier=AgencyTier.PROFESSIONAL
        )
        assert pro_agency.get_model_limit() == 50
        assert pro_agency.get_user_limit() == 20
        assert pro_agency.can_use_feature("analytics") is True
        assert pro_agency.can_use_feature("api_access") is False
        
        # Enterprise tier
        enterprise_agency = await create_test_agency(
            name="Enterprise Agency",
            tier=AgencyTier.ENTERPRISE
        )
        assert enterprise_agency.get_model_limit() == -1  # Unlimited
        assert enterprise_agency.get_user_limit() == -1  # Unlimited
        assert enterprise_agency.can_use_feature("analytics") is True
        assert enterprise_agency.can_use_feature("api_access") is True
        assert enterprise_agency.can_use_feature("white_label") is True
    
    @pytest.mark.asyncio
    async def test_agency_status_transitions(self, db_session: AsyncSession):
        """Test valid agency status transitions."""
        agency = await create_test_agency(status=AgencyStatus.ACTIVE)
        
        # Active -> Suspended
        agency.suspend(reason="Payment overdue", suspended_by="admin123")
        assert agency.status == AgencyStatus.SUSPENDED
        assert agency.suspended_at is not None
        assert agency.suspension_reason == "Payment overdue"
        
        # Suspended -> Active
        agency.reactivate(reactivated_by="admin123")
        assert agency.status == AgencyStatus.ACTIVE
        assert agency.suspended_at is None
        assert agency.suspension_reason is None
        
        # Active -> Inactive
        agency.deactivate(reason="Voluntary closure")
        assert agency.status == AgencyStatus.INACTIVE
        assert agency.deactivated_at is not None
        
        # Cannot suspend inactive agency
        with pytest.raises(ValueError, match="Can only suspend active agencies"):
            agency.suspend(reason="Test", suspended_by="admin")
    
    @pytest.mark.asyncio
    async def test_agency_model_management(self, db_session: AsyncSession):
        """Test agency model management capabilities."""
        agency = await create_test_agency(tier=AgencyTier.BASIC)
        
        # Add models up to limit
        models = []
        for i in range(10):  # Basic tier limit
            model = await create_test_model(
                agency=agency,
                name=f"Model {i}"
            )
            models.append(model)
        
        # Check model count
        assert await agency.get_active_model_count(db_session) == 10
        
        # Try to add one more (should fail for basic tier)
        with pytest.raises(ValueError, match="Model limit reached"):
            await agency.can_add_model(db_session)
        
        # Upgrade to professional tier
        agency.tier = AgencyTier.PROFESSIONAL
        await db_session.commit()
        
        # Now can add more models
        assert await agency.can_add_model(db_session) is True
    
    @pytest.mark.asyncio
    async def test_agency_user_management(self, db_session: AsyncSession):
        """Test agency user management and role distribution."""
        agency = await create_test_agency()
        
        # Create users with different roles
        admin = await create_test_user(role=UserRole.ADMIN, agency_id=agency.id)
        managers = []
        for i in range(3):
            manager = await create_test_user(
                role=UserRole.MANAGER,
                agency_id=agency.id,
                username=f"manager{i}"
            )
            managers.append(manager)
        
        chatters = []
        for i in range(5):
            chatter = await create_test_user(
                role=UserRole.CHATTER,
                agency_id=agency.id,
                username=f"chatter{i}"
            )
            chatters.append(chatter)
        
        # Get users by role
        agency_admins = await agency.get_users_by_role(db_session, UserRole.ADMIN)
        assert len(agency_admins) == 1
        assert agency_admins[0].id == admin.id
        
        agency_managers = await agency.get_users_by_role(db_session, UserRole.MANAGER)
        assert len(agency_managers) == 3
        
        # Check user limit enforcement
        assert await agency.get_total_user_count(db_session) == 9
    
    @pytest.mark.asyncio
    async def test_agency_financial_summary(self, db_session: AsyncSession):
        """Test agency financial summary calculations."""
        agency = await create_test_agency(commission_rate=Decimal("0.20"))
        
        # Create models with earnings
        model1 = await create_test_model(agency=agency)
        model2 = await create_test_model(agency=agency)
        
        # Simulate earnings
        from models.financial import Earning, EarningType
        
        earnings_data = [
            (model1.id, Decimal("1000.00"), EarningType.SUBSCRIPTION),
            (model1.id, Decimal("500.00"), EarningType.TIP),
            (model2.id, Decimal("2000.00"), EarningType.PPV),
            (model2.id, Decimal("300.00"), EarningType.TIP),
        ]
        
        for model_id, amount, earning_type in earnings_data:
            earning = Earning(
                model_id=model_id,
                agency_id=agency.id,
                amount=amount,
                type=earning_type,
                platform="onlyfans",
                earned_at=datetime.utcnow()
            )
            db_session.add(earning)
        
        await db_session.commit()
        
        # Calculate financial summary
        summary = await agency.get_financial_summary(
            db_session,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )
        
        assert summary["total_earnings"] == Decimal("3800.00")
        assert summary["total_commission"] == Decimal("760.00")  # 20% of 3800
        assert summary["earnings_by_type"]["subscription"] == Decimal("1000.00")
        assert summary["earnings_by_type"]["tip"] == Decimal("800.00")
        assert summary["earnings_by_type"]["ppv"] == Decimal("2000.00")
    
    @pytest.mark.asyncio
    async def test_agency_settings_management(self, db_session: AsyncSession):
        """Test agency settings and preferences."""
        agency = await create_test_agency()
        
        # Update settings
        new_settings = {
            "payout": {
                "auto_payout": True,
                "frequency": "weekly",
                "minimum_amount": 100.00,
                "method": "bank_transfer"
            },
            "notifications": {
                "new_subscriber": True,
                "tip_received": True,
                "daily_summary": False,
                "channels": ["email", "in_app"]
            },
            "features": {
                "auto_welcome_message": True,
                "ppv_approval_required": True,
                "content_watermark": True
            }
        }
        
        agency.update_settings(new_settings)
        await db_session.commit()
        
        # Verify settings
        assert agency.get_setting("payout.auto_payout") is True
        assert agency.get_setting("payout.minimum_amount") == 100.00
        assert agency.get_setting("notifications.channels") == ["email", "in_app"]
        assert agency.get_setting("features.content_watermark") is True
        assert agency.get_setting("non.existent.setting", default="default") == "default"
    
    @pytest.mark.asyncio
    async def test_agency_platform_integration(self, db_session: AsyncSession):
        """Test agency platform integration settings."""
        agency = await create_test_agency()
        
        # Add platform credentials
        await agency.add_platform_integration(
            platform="onlyfans",
            credentials={
                "api_key": "encrypted_key_123",
                "api_secret": "encrypted_secret_456"
            },
            settings={
                "auto_sync": True,
                "sync_interval": 300,  # 5 minutes
                "fetch_messages": True,
                "fetch_tips": True
            }
        )
        
        # Add another platform
        await agency.add_platform_integration(
            platform="fansly",
            credentials={
                "api_token": "encrypted_token_789"
            },
            settings={
                "auto_sync": False
            }
        )
        
        # Verify integrations
        integrations = agency.get_platform_integrations()
        assert len(integrations) == 2
        assert "onlyfans" in integrations
        assert integrations["onlyfans"]["settings"]["auto_sync"] is True
        
        # Remove integration
        agency.remove_platform_integration("fansly")
        integrations = agency.get_platform_integrations()
        assert len(integrations) == 1
        assert "fansly" not in integrations
    
    @pytest.mark.asyncio
    async def test_agency_analytics_permissions(self, db_session: AsyncSession):
        """Test agency analytics access based on tier."""
        basic_agency = await create_test_agency(tier=AgencyTier.BASIC)
        pro_agency = await create_test_agency(tier=AgencyTier.PROFESSIONAL)
        
        # Basic tier - limited analytics
        basic_analytics = basic_agency.get_available_analytics()
        assert "basic_revenue" in basic_analytics
        assert "basic_subscribers" in basic_analytics
        assert "advanced_retention" not in basic_analytics
        assert "predictive_analytics" not in basic_analytics
        
        # Professional tier - more analytics
        pro_analytics = pro_agency.get_available_analytics()
        assert "basic_revenue" in pro_analytics
        assert "advanced_retention" in pro_analytics
        assert "cohort_analysis" in pro_analytics
        assert "predictive_analytics" not in pro_analytics
        
        # Enterprise tier - all analytics
        enterprise_agency = await create_test_agency(tier=AgencyTier.ENTERPRISE)
        enterprise_analytics = enterprise_agency.get_available_analytics()
        assert "predictive_analytics" in enterprise_analytics
        assert "custom_reports" in enterprise_analytics
    
    @pytest.mark.asyncio
    async def test_agency_audit_trail(self, db_session: AsyncSession):
        """Test agency audit trail functionality."""
        agency = await create_test_agency()
        
        # Log various activities
        agency.log_activity("settings_updated", {
            "updated_by": "admin123",
            "changes": {"commission_rate": {"old": 0.20, "new": 0.15}}
        })
        
        agency.log_activity("user_added", {
            "user_id": "user456",
            "role": "manager",
            "added_by": "admin123"
        })
        
        agency.log_activity("platform_integrated", {
            "platform": "onlyfans",
            "integrated_by": "admin123"
        })
        
        # Retrieve audit trail
        activities = await agency.get_audit_trail(
            db_session,
            limit=10,
            activity_types=["settings_updated", "user_added"]
        )
        
        assert len(activities) == 2
        assert activities[0]["type"] == "user_added"
        assert activities[1]["type"] == "settings_updated"
        assert activities[1]["metadata"]["changes"]["commission_rate"]["new"] == 0.15
    
    @pytest.mark.asyncio
    async def test_agency_subscription_management(self, db_session: AsyncSession):
        """Test agency subscription and billing management."""
        agency = await create_test_agency(tier=AgencyTier.BASIC)
        
        # Set up subscription
        subscription = await agency.create_subscription(
            plan_id="pro_monthly",
            payment_method_id="pm_123",
            start_date=datetime.utcnow()
        )
        
        assert subscription.status == "active"
        assert subscription.current_period_end > datetime.utcnow()
        
        # Upgrade subscription
        upgraded = await agency.upgrade_subscription(
            new_plan_id="enterprise_monthly",
            immediate=True
        )
        
        assert upgraded.plan_id == "enterprise_monthly"
        assert agency.tier == AgencyTier.ENTERPRISE
        
        # Check subscription features
        features = agency.get_subscription_features()
        assert features["models_limit"] == -1
        assert features["api_access"] is True
        assert features["priority_support"] is True
    
    @pytest.mark.asyncio
    async def test_agency_performance_metrics(self, db_session: AsyncSession):
        """Test agency performance metrics calculation."""
        agency = await create_test_agency()
        
        # Create test data
        models = []
        for i in range(5):
            model = await create_test_model(agency=agency)
            models.append(model)
        
        # Calculate performance metrics
        metrics = await agency.calculate_performance_metrics(
            db_session,
            period="last_30_days"
        )
        
        assert "revenue_growth" in metrics
        assert "model_retention_rate" in metrics
        assert "average_model_earnings" in metrics
        assert "top_performing_models" in metrics
        assert "conversion_rates" in metrics
    
    @pytest.mark.asyncio
    async def test_agency_compliance_features(self, db_session: AsyncSession):
        """Test agency compliance and verification features."""
        agency = await create_test_agency()
        
        # Submit compliance documents
        await agency.submit_compliance_document(
            document_type="business_license",
            document_url="https://storage.example.com/docs/license.pdf",
            submitted_by="admin123"
        )
        
        await agency.submit_compliance_document(
            document_type="tax_id",
            document_url="https://storage.example.com/docs/tax.pdf",
            submitted_by="admin123"
        )
        
        # Verify compliance status
        compliance_status = await agency.get_compliance_status()
        assert compliance_status["business_license"]["status"] == "pending_review"
        assert compliance_status["tax_id"]["status"] == "pending_review"
        assert compliance_status["overall_status"] == "pending"
        
        # Approve documents
        await agency.update_compliance_status(
            document_type="business_license",
            status="approved",
            reviewed_by="compliance_team"
        )
        
        await agency.update_compliance_status(
            document_type="tax_id",
            status="approved",
            reviewed_by="compliance_team"
        )
        
        # Check verified status
        compliance_status = await agency.get_compliance_status()
        assert compliance_status["overall_status"] == "verified"
        assert agency.is_verified is True
    
    @pytest.mark.asyncio
    async def test_agency_soft_delete(self, db_session: AsyncSession):
        """Test soft delete functionality for agencies."""
        agency = await create_test_agency()
        agency_id = agency.id
        
        # Create associated data
        model = await create_test_model(agency=agency)
        user = await create_test_user(agency_id=agency.id)
        
        # Soft delete agency
        await agency.soft_delete(deleted_by="admin123", reason="Account closure requested")
        await db_session.commit()
        
        assert agency.deleted_at is not None
        assert agency.deleted_by == "admin123"
        assert agency.deletion_reason == "Account closure requested"
        assert agency.status == AgencyStatus.INACTIVE
        
        # Agency should not appear in active queries
        active_agencies = await db_session.query(Agency).filter(
            Agency.deleted_at.is_(None)
        ).all()
        assert agency not in active_agencies
        
        # But should still exist in database
        deleted_agency = await db_session.get(Agency, agency_id)
        assert deleted_agency is not None
        assert deleted_agency.deleted_at is not None