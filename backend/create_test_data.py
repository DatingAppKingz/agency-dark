#!/usr/bin/env python3
"""Create comprehensive test data for AgencyDark"""

import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from faker import Faker

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.security import get_password_hash
from core.domain.models import Agency, User, UserRole
from modules.financial.domain.models import (
    CommissionRule, CommissionTier, BillingCycle,
    FinancialTransaction, TransactionType,
    Payout, PayoutStatus, Invoice, InvoiceStatus
)
from modules.analytics.domain.models import MetricSnapshot, MetricType

fake = Faker()


async def get_test_agency(session: AsyncSession):
    """Get the test agency"""
    result = await session.execute(
        select(Agency).where(Agency.slug == "test-agency")
    )
    return result.scalar_one()


async def get_test_user(session: AsyncSession):
    """Get the test user"""
    result = await session.execute(
        select(User).where(User.email == "test@example.com")
    )
    return result.scalar_one()


async def create_models(session: AsyncSession, agency_id: uuid.UUID, num_models: int = 5):
    """Create test model accounts"""
    print(f"Creating {num_models} model accounts...")
    
    models = []
    for i in range(num_models):
        model = User(
            id=uuid.uuid4(),
            agency_id=agency_id,
            email=f"model{i+1}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name=fake.name(),
            role=UserRole.MODEL,
            is_active=True,
            is_verified=True,
            verified_at=datetime.utcnow() - timedelta(days=random.randint(30, 180)),
            created_at=datetime.utcnow() - timedelta(days=random.randint(30, 180)),
            updated_at=datetime.utcnow()
        )
        session.add(model)
        models.append(model)
        print(f"  Created model: {model.full_name} ({model.email})")
    
    await session.flush()
    return models


async def create_chatters(session: AsyncSession, agency_id: uuid.UUID, num_chatters: int = 3):
    """Create test chatter accounts"""
    print(f"Creating {num_chatters} chatter accounts...")
    
    chatters = []
    for i in range(num_chatters):
        chatter = User(
            id=uuid.uuid4(),
            agency_id=agency_id,
            email=f"chatter{i+1}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name=fake.name(),
            role=UserRole.CHATTER,
            is_active=True,
            is_verified=True,
            verified_at=datetime.utcnow() - timedelta(days=random.randint(15, 90)),
            created_at=datetime.utcnow() - timedelta(days=random.randint(15, 90)),
            updated_at=datetime.utcnow()
        )
        session.add(chatter)
        chatters.append(chatter)
        print(f"  Created chatter: {chatter.full_name} ({chatter.email})")
    
    await session.flush()
    return chatters


async def create_financial_data(session: AsyncSession, agency_id: uuid.UUID, models: list):
    """Create financial data including transactions, commissions, and payouts"""
    print("Creating financial data...")
    
    # Create commission rules
    commission_rule = CommissionRule(
        id=uuid.uuid4(),
        agency_id=agency_id,
        tier=CommissionTier.TIER_2,
        rate=Decimal("20.00"),  # 20% commission
        effective_from=datetime.utcnow() - timedelta(days=90)
    )
    session.add(commission_rule)
    
    # Create billing cycle
    billing_cycle = BillingCycle(
        id=uuid.uuid4(),
        agency_id=agency_id,
        cycle_start=datetime.utcnow() - timedelta(days=30),
        cycle_end=datetime.utcnow() + timedelta(days=30),
        gross_revenue=Decimal("0"),
        total_commission=Decimal("0"),
        net_revenue=Decimal("0"),
        is_closed=False
    )
    session.add(billing_cycle)
    await session.flush()
    
    # Create transactions for each model
    total_revenue = Decimal("0")
    for model in models:
        num_transactions = random.randint(50, 200)
        model_revenue = Decimal("0")
        
        for i in range(num_transactions):
            # Random transaction date within the last 30 days
            trans_date = datetime.utcnow() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            # Random amount between $5 and $500
            amount = Decimal(str(round(random.uniform(5, 500), 2)))
            model_revenue += amount
            
            transaction = FinancialTransaction(
                id=uuid.uuid4(),
                agency_id=agency_id,
                model_id=model.id,
                billing_cycle_id=billing_cycle.id,
                type=random.choice([
                    TransactionType.REVENUE,
                    TransactionType.COMMISSION
                ]),
                amount=amount,
                currency="USD",
                external_reference=f"of_{fake.uuid4()}",
                description=fake.sentence(nb_words=5),
                transaction_date=trans_date
            )
            session.add(transaction)
        
        total_revenue += model_revenue
        print(f"  Created {num_transactions} transactions for {model.full_name}: ${model_revenue:.2f}")
    
    # Create payouts
    for model in models:
        if random.random() > 0.3:  # 70% chance of having a payout
            payout = Payout(
                id=uuid.uuid4(),
                billing_cycle_id=billing_cycle.id,
                recipient_id=model.id,
                recipient_type="model",
                amount=Decimal(str(round(random.uniform(500, 5000), 2))),
                currency="USD",
                status=random.choice([PayoutStatus.PENDING, PayoutStatus.COMPLETED]),
                payment_method="bank_transfer",
                scheduled_at=datetime.utcnow() + timedelta(days=random.randint(1, 7))
            )
            session.add(payout)
            print(f"  Created payout for {model.full_name}: ${payout.amount:.2f}")
    
    # Create invoices
    invoice = Invoice(
        id=uuid.uuid4(),
        agency_id=agency_id,
        billing_cycle_id=billing_cycle.id,
        invoice_number=f"INV-{datetime.utcnow().strftime('%Y%m')}-001",
        amount=total_revenue * Decimal("0.20"),  # Agency commission
        currency="USD",
        status=InvoiceStatus.DRAFT,
        issue_date=datetime.utcnow().date(),
        due_date=datetime.utcnow().date() + timedelta(days=30),
        created_at=datetime.utcnow()
    )
    session.add(invoice)
    
    await session.flush()
    print(f"  Total revenue generated: ${total_revenue:.2f}")


async def create_analytics_data(session: AsyncSession, agency_id: uuid.UUID, models: list):
    """Create analytics metrics"""
    print("Creating analytics data...")
    
    # Create metrics for the last 30 days
    for days_ago in range(30):
        metric_date = datetime.utcnow() - timedelta(days=days_ago)
        
        # Agency-wide metrics
        agency_metric = MetricSnapshot(
            id=uuid.uuid4(),
            agency_id=agency_id,
            metric_type=MetricType.DAILY,
            period_start=metric_date.replace(hour=0, minute=0, second=0),
            period_end=metric_date.replace(hour=23, minute=59, second=59),
            metrics={
                "total_revenue": float(Decimal(str(round(random.uniform(1000, 10000), 2)))),
                "total_subscribers": random.randint(100, 1000),
                "new_subscribers": random.randint(10, 100),
                "messages_sent": random.randint(500, 5000),
                "active_fans": random.randint(50, 500),
                "conversion_rate": round(random.uniform(0.1, 0.3), 3),
                "average_order_value": float(Decimal(str(round(random.uniform(20, 100), 2))))
            },
            created_at=metric_date
        )
        session.add(agency_metric)
        
        # Model-specific metrics
        for model in models[:3]:  # Top 3 models only to avoid too much data
            model_metric = MetricSnapshot(
                id=uuid.uuid4(),
                agency_id=agency_id,
                model_id=model.id,
                metric_type=MetricType.DAILY,
                period_start=metric_date.replace(hour=0, minute=0, second=0),
                period_end=metric_date.replace(hour=23, minute=59, second=59),
                metrics={
                    "revenue": float(Decimal(str(round(random.uniform(100, 2000), 2)))),
                    "subscribers": random.randint(20, 200),
                    "new_subscribers": random.randint(1, 20),
                    "messages_sent": random.randint(50, 500),
                    "content_posts": random.randint(1, 10),
                    "engagement_rate": round(random.uniform(0.05, 0.25), 3),
                    "tips_received": float(Decimal(str(round(random.uniform(0, 500), 2))))
                },
                created_at=metric_date
            )
            session.add(model_metric)
    
    await session.flush()
    print("  Created 30 days of analytics metrics")


async def create_test_data():
    """Create all test data"""
    async with AsyncSessionLocal() as session:
        try:
            # Get test agency and user
            agency = await get_test_agency(session)
            user = await get_test_user(session)
            
            print(f"\n✅ Using test agency: {agency.name} (ID: {agency.id})")
            print(f"✅ Using test user: {user.email}\n")
            
            # Create models
            models = await create_models(session, agency.id, num_models=5)
            
            # Create chatters
            chatters = await create_chatters(session, agency.id, num_chatters=3)
            
            # Create financial data
            await create_financial_data(session, agency.id, models)
            
            # Create analytics data
            await create_analytics_data(session, agency.id, models)
            
            # Commit all changes
            await session.commit()
            
            print("\n✅ Test data created successfully!")
            print("\nSummary:")
            print(f"  - Models: {len(models)}")
            print(f"  - Chatters: {len(chatters)}")
            print("  - Financial transactions: Generated")
            print("  - Analytics metrics: 30 days")
            print("\n🎯 You can now login and see a populated dashboard!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error creating test data: {e}")
            raise


async def main():
    """Run the test data creation"""
    print("Creating comprehensive test data for AgencyDark...")
    await create_test_data()


if __name__ == "__main__":
    asyncio.run(main())