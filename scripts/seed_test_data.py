#!/usr/bin/env python3
"""
Seed script to create comprehensive test data for AgencyDark
Creates agencies, users with all roles, model profiles, and sample data
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal, create_tables
from core.security import get_password_hash
from core.domain.models import (
    Agency, User, UserRole, ModelProfile, 
    CommissionRule, CommissionTier, BillingCycle,
    ThemeConfiguration, AgencyProfile
)
from modules.analytics.domain.models import MetricSnapshot
from modules.financial.domain.models import FinancialTransaction, TransactionType


async def create_agencies(session: AsyncSession):
    """Create test agencies"""
    print("Creating agencies...")
    
    # Main test agency
    main_agency = Agency(
        id=uuid.uuid4(),
        name="Test Agency Premium",
        slug="test-agency-premium",
        domain="premium.testagency.com",
        subscription_status="ACTIVE",
        subscription_ends_at=datetime.utcnow() + timedelta(days=365),
        settings={
            "features": {
                "analytics": True,
                "financial": True,
                "whitelabel": True,
                "api_access": True
            },
            "limits": {
                "models": 100,
                "chatters": 500,
                "api_calls_per_hour": 1000
            }
        }
    )
    
    # Secondary agency for multi-tenant testing
    secondary_agency = Agency(
        id=uuid.uuid4(),
        name="Competitor Agency",
        slug="competitor-agency",
        domain="competitor.example.com",
        subscription_status="ACTIVE",
        subscription_ends_at=datetime.utcnow() + timedelta(days=180),
        settings={
            "features": {
                "analytics": True,
                "financial": True,
                "whitelabel": False,
                "api_access": True
            }
        }
    )
    
    session.add(main_agency)
    session.add(secondary_agency)
    await session.commit()
    
    return main_agency, secondary_agency


async def create_users(session: AsyncSession, main_agency, secondary_agency):
    """Create users with all 6 roles"""
    print("Creating users with all roles...")
    
    users = {}
    
    # 1. Super Admin (no agency)
    super_admin = User(
        id=uuid.uuid4(),
        email="superadmin@agencydark.com",
        hashed_password=get_password_hash("SuperAdmin123!"),
        full_name="Super Administrator",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['super_admin'] = super_admin
    
    # 2. Agency Owner (main agency)
    agency_owner = User(
        id=uuid.uuid4(),
        agency_id=main_agency.id,
        email="owner@testagency.com",
        hashed_password=get_password_hash("AgencyOwner123!"),
        full_name="John Agency Owner",
        role=UserRole.AGENCY_OWNER,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['agency_owner'] = agency_owner
    
    # 3. Agency Admin (main agency)
    agency_admin = User(
        id=uuid.uuid4(),
        agency_id=main_agency.id,
        email="admin@testagency.com",
        hashed_password=get_password_hash("AgencyAdmin123!"),
        full_name="Sarah Admin",
        role=UserRole.AGENCY_ADMIN,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['agency_admin'] = agency_admin
    
    # 4. Agency Member (main agency)
    agency_member = User(
        id=uuid.uuid4(),
        agency_id=main_agency.id,
        email="member@testagency.com",
        hashed_password=get_password_hash("AgencyMember123!"),
        full_name="Mike Member",
        role=UserRole.AGENCY_MEMBER,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['agency_member'] = agency_member
    
    # 5. Model (main agency)
    model_user = User(
        id=uuid.uuid4(),
        agency_id=main_agency.id,
        email="model@testagency.com",
        hashed_password=get_password_hash("ModelUser123!"),
        full_name="Emma Model",
        role=UserRole.MODEL,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['model'] = model_user
    
    # 6. Chatter (main agency)
    chatter_user = User(
        id=uuid.uuid4(),
        agency_id=main_agency.id,
        email="chatter@testagency.com",
        hashed_password=get_password_hash("ChatterUser123!"),
        full_name="Chris Chatter",
        role=UserRole.CHATTER,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['chatter'] = chatter_user
    
    # Additional users for secondary agency (for multi-tenant testing)
    competitor_owner = User(
        id=uuid.uuid4(),
        agency_id=secondary_agency.id,
        email="owner@competitor.com",
        hashed_password=get_password_hash("CompetitorOwner123!"),
        full_name="Jane Competitor",
        role=UserRole.AGENCY_OWNER,
        is_active=True,
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    users['competitor_owner'] = competitor_owner
    
    # Add all users to session
    for user in users.values():
        session.add(user)
    
    await session.commit()
    return users


async def create_model_profiles(session: AsyncSession, users, agency):
    """Create model profiles for MODEL users"""
    print("Creating model profiles...")
    
    model_profile = ModelProfile(
        id=uuid.uuid4(),
        user_id=users['model'].id,
        agency_id=agency.id,
        stage_name="Emma Rose",
        onlyfans_username="emmarose_of",
        bio="Premium content creator | DM for customs",
        subscription_price=Decimal("9.99"),
        is_active=True,
        inflow_api_key="test_inflow_api_key_123",
        inflow_account_id="inflow_account_emma",
        onlyfans_api_key="test_onlyfans_api_key_123",
        onlyfans_user_id="of_user_emma_123",
        settings={
            "auto_reply_enabled": True,
            "ppv_minimum_price": 10,
            "custom_rates": {
                "text_message": 0.50,
                "voice_message": 2.00,
                "custom_content": 25.00
            },
            "working_hours": {
                "monday": {"start": "09:00", "end": "17:00"},
                "tuesday": {"start": "09:00", "end": "17:00"},
                "wednesday": {"start": "09:00", "end": "17:00"},
                "thursday": {"start": "09:00", "end": "17:00"},
                "friday": {"start": "09:00", "end": "15:00"}
            }
        },
        assigned_chatters=[users['chatter'].id]
    )
    
    session.add(model_profile)
    await session.commit()
    return model_profile


async def create_financial_data(session: AsyncSession, agency):
    """Create commission rules and billing cycles"""
    print("Creating financial data...")
    
    # Commission rules (tiered based on subscriber count)
    rule1 = CommissionRule(
        id=uuid.uuid4(),
        agency_id=agency.id,
        name="Tier 1 - Starter",
        tier=CommissionTier.TIER_1,
        percentage=Decimal("70.00"),
        min_subscribers=0,
        max_subscribers=5000,
        is_active=True,
        description="70% commission for models with 0-5,000 subscribers"
    )
    
    rule2 = CommissionRule(
        id=uuid.uuid4(),
        agency_id=agency.id,
        name="Tier 2 - Growth",
        tier=CommissionTier.TIER_2,
        percentage=Decimal("65.00"),
        min_subscribers=5001,
        max_subscribers=10000,
        is_active=True,
        description="65% commission for models with 5,001-10,000 subscribers"
    )
    
    rule3 = CommissionRule(
        id=uuid.uuid4(),
        agency_id=agency.id,
        name="Tier 3 - Premium",
        tier=CommissionTier.TIER_3,
        percentage=Decimal("60.00"),
        min_subscribers=10001,
        max_subscribers=None,
        is_active=True,
        description="60% commission for models with 10,000+ subscribers"
    )
    
    # Current billing cycle
    current_cycle = BillingCycle(
        id=uuid.uuid4(),
        agency_id=agency.id,
        start_date=datetime.utcnow().replace(day=1),
        end_date=(datetime.utcnow().replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1),
        is_closed=False,
        total_revenue=Decimal("0.00"),
        total_commission=Decimal("0.00"),
        total_payout=Decimal("0.00")
    )
    
    session.add_all([rule1, rule2, rule3, current_cycle])
    await session.commit()
    return [rule1, rule2, rule3], current_cycle


async def create_analytics_data(session: AsyncSession, model_profile):
    """Create sample analytics data"""
    print("Creating analytics data...")
    
    # Create metric snapshots for the last 7 days
    for days_ago in range(7):
        snapshot_date = datetime.utcnow() - timedelta(days=days_ago)
        
        snapshot = MetricSnapshot(
            id=uuid.uuid4(),
            model_id=model_profile.id,
            snapshot_date=snapshot_date,
            subscriber_count=5000 + (days_ago * 50),  # Growing subscriber count
            total_revenue=Decimal(str(1000 + (days_ago * 100))),
            message_count=100 + (days_ago * 10),
            ppv_count=10 + days_ago,
            tip_count=20 + (days_ago * 2),
            post_count=5,
            new_subscribers=50 + (days_ago * 5),
            churned_subscribers=10 + days_ago,
            metrics={
                "engagement_rate": 0.65 + (days_ago * 0.02),
                "avg_message_price": 2.50,
                "top_spending_fans": [
                    {"fan_id": f"fan_{i}", "amount": 100 - (i * 10)}
                    for i in range(5)
                ]
            }
        )
        session.add(snapshot)
    
    await session.commit()


async def create_whitelabel_data(session: AsyncSession, agency):
    """Create white-label configuration"""
    print("Creating white-label data...")
    
    # Theme configuration
    theme = ThemeConfiguration(
        id=uuid.uuid4(),
        agency_id=agency.id,
        default_mode="light",
        allow_user_preference=True,
        light_theme={
            "primary": "#1976d2",
            "secondary": "#dc004e",
            "background": "#ffffff",
            "surface": "#f5f5f5",
            "error": "#f44336",
            "warning": "#ff9800",
            "info": "#2196f3",
            "success": "#4caf50"
        },
        dark_theme={
            "primary": "#90caf9",
            "secondary": "#f48fb1",
            "background": "#121212",
            "surface": "#1e1e1e",
            "error": "#f44336",
            "warning": "#ff9800",
            "info": "#2196f3",
            "success": "#4caf50"
        },
        font_family="Inter, system-ui, sans-serif",
        font_size_base="16px",
        border_radius="8px",
        custom_css="""
        /* Custom styles for Test Agency */
        .brand-header {
            background: linear-gradient(135deg, #1976d2 0%, #dc004e 100%);
        }
        """
    )
    
    # Agency profile
    profile = AgencyProfile(
        id=uuid.uuid4(),
        agency_id=agency.id,
        display_name="Test Agency Premium",
        tagline="Your Success, Our Priority",
        description="Leading OnlyFans management agency with proven results",
        support_email="support@testagency.com",
        support_phone="+1-555-123-4567",
        website_url="https://testagency.com",
        social_links={
            "twitter": "https://twitter.com/testagency",
            "instagram": "https://instagram.com/testagency",
            "tiktok": "https://tiktok.com/@testagency"
        },
        legal_name="Test Agency LLC",
        tax_id="12-3456789",
        address={
            "street": "123 Business Ave",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
            "country": "USA"
        },
        from_email_name="Test Agency",
        from_email_address="noreply@testagency.com",
        reply_to_email="support@testagency.com"
    )
    
    session.add_all([theme, profile])
    await session.commit()


async def main():
    """Main seed function"""
    print("=" * 60)
    print("AgencyDark Test Data Seeder")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        try:
            # Create agencies
            main_agency, secondary_agency = await create_agencies(session)
            print(f"✅ Created agencies: {main_agency.name}, {secondary_agency.name}")
            
            # Create users with all roles
            users = await create_users(session, main_agency, secondary_agency)
            print(f"✅ Created {len(users)} users with all 6 roles")
            
            # Create model profiles
            model_profile = await create_model_profiles(session, users, main_agency)
            print(f"✅ Created model profile: {model_profile.stage_name}")
            
            # Create financial data
            rules, billing_cycle = await create_financial_data(session, main_agency)
            print(f"✅ Created {len(rules)} commission rules and billing cycle")
            
            # Create analytics data
            await create_analytics_data(session, model_profile)
            print("✅ Created analytics data for last 7 days")
            
            # Create white-label data
            await create_whitelabel_data(session, main_agency)
            print("✅ Created white-label configuration")
            
            print("\n" + "=" * 60)
            print("Test data seeded successfully!")
            print("=" * 60)
            
            print("\n📝 Test Credentials:")
            print("-" * 40)
            for role, user in users.items():
                print(f"{role.upper()}:")
                print(f"  Email: {user.email}")
                print(f"  Password: {role.title().replace('_', '')}123!")
                print()
            
        except Exception as e:
            print(f"❌ Error seeding data: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())