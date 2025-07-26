#!/usr/bin/env python3
"""Create simple test data for AgencyDark"""

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
    FinancialTransaction, TransactionType,
    Payout, PayoutStatus
)
from modules.analytics.domain.models import MetricSnapshot

fake = Faker()


async def get_test_agency(session: AsyncSession):
    """Get the test agency"""
    result = await session.execute(
        select(Agency).where(Agency.slug == "test-agency")
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
    """Create financial transactions"""
    print("Creating financial transactions...")
    
    total_revenue = Decimal("0")
    
    # Create transactions for each model
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
                type=TransactionType.REVENUE,
                amount=amount,
                currency="USD",
                external_reference=f"of_{fake.uuid4()}",
                description=fake.sentence(nb_words=5),
                transaction_date=trans_date
            )
            session.add(transaction)
        
        total_revenue += model_revenue
        print(f"  Created {num_transactions} transactions for {model.full_name}: ${model_revenue:.2f}")
    
    await session.flush()
    print(f"  Total revenue generated: ${total_revenue:.2f}")


async def create_analytics_data(session: AsyncSession, models: list):
    """Create analytics metrics"""
    print("Creating analytics metrics...")
    
    # Create metrics for each model for the last 30 days
    for model in models[:3]:  # Top 3 models only
        for days_ago in range(30):
            metric_date = datetime.utcnow() - timedelta(days=days_ago)
            
            metric = MetricSnapshot(
                id=uuid.uuid4(),
                model_id=model.id,
                timestamp=metric_date,
                total_subscribers=random.randint(100, 1000),
                paying_subscribers=random.randint(50, 500),
                non_paying_fans=random.randint(50, 500),
                new_subscribers=random.randint(5, 50),
                lost_subscribers=random.randint(0, 10),
                total_revenue=Decimal(str(round(random.uniform(100, 5000), 2))),
                subscription_revenue=Decimal(str(round(random.uniform(50, 2000), 2))),
                tip_revenue=Decimal(str(round(random.uniform(0, 1000), 2))),
                ppv_revenue=Decimal(str(round(random.uniform(0, 1500), 2))),
                total_posts=random.randint(1, 10),
                total_messages_sent=random.randint(50, 500),
                total_messages_received=random.randint(20, 200),
                avg_fan_spend=Decimal(str(round(random.uniform(10, 100), 2))),
                conversion_rate=Decimal(str(round(random.uniform(5, 25), 2)))
            )
            session.add(metric)
    
    await session.flush()
    print("  Created 30 days of analytics metrics for top 3 models")


async def create_test_data():
    """Create all test data"""
    async with AsyncSessionLocal() as session:
        try:
            # Get test agency
            agency = await get_test_agency(session)
            print(f"\n✅ Using test agency: {agency.name} (ID: {agency.id})")
            
            # Create models
            models = await create_models(session, agency.id, num_models=5)
            
            # Create chatters
            chatters = await create_chatters(session, agency.id, num_chatters=3)
            
            # Create financial data
            await create_financial_data(session, agency.id, models)
            
            # Create analytics data
            await create_analytics_data(session, models)
            
            # Commit all changes
            await session.commit()
            
            print("\n✅ Test data created successfully!")
            print("\nSummary:")
            print(f"  - Models: {len(models)}")
            print(f"  - Chatters: {len(chatters)}")
            print("  - Financial transactions: Generated")
            print("  - Analytics metrics: 30 days for top 3 models")
            print("\n🎯 You can now login and see a populated dashboard!")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error creating test data: {e}")
            raise


async def main():
    """Run the test data creation"""
    print("Creating test data for AgencyDark...")
    await create_test_data()


if __name__ == "__main__":
    asyncio.run(main())