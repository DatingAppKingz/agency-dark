#!/usr/bin/env python3
"""
Fix user roles directly via SQLAlchemy
Run this inside the backend container
"""

import asyncio
from sqlalchemy import text
from core.database import AsyncSessionLocal
import uuid
from datetime import datetime

async def fix_roles():
    async with AsyncSessionLocal() as session:
        try:
            print("Starting role fixes...")
            
            # Create agencies
            print("\n1. Creating agencies...")
            await session.execute(text("""
                INSERT INTO agencies (id, name, slug, domain, subscription_status, created_at, updated_at)
                VALUES 
                  (:id1, 'Test Agency Premium', 'test-agency-premium', 'testagency.com', 'ACTIVE', :now, :now),
                  (:id2, 'Competitor Agency', 'competitor-agency', 'competitor.com', 'ACTIVE', :now, :now)
                ON CONFLICT (slug) DO UPDATE SET
                  name = EXCLUDED.name,
                  updated_at = :now
            """), {
                "id1": str(uuid.uuid4()),
                "id2": str(uuid.uuid4()),
                "now": datetime.utcnow()
            })
            
            # Get agency IDs
            result = await session.execute(text("SELECT id, slug FROM agencies WHERE slug IN ('test-agency-premium', 'competitor-agency')"))
            agencies = {row.slug: row.id for row in result}
            print(f"Agencies: {agencies}")
            
            # Update user roles
            print("\n2. Updating user roles...")
            role_updates = [
                ("owner@testagency.com", "AGENCY_OWNER", agencies.get('test-agency-premium')),
                ("admin@testagency.com", "AGENCY_ADMIN", agencies.get('test-agency-premium')),
                ("model@testagency.com", "MODEL", agencies.get('test-agency-premium')),
                ("chatter@testagency.com", "CHATTER", agencies.get('test-agency-premium')),
                ("member@testagency.com", "AGENCY_MEMBER", agencies.get('test-agency-premium')),
                ("owner@competitor.com", "AGENCY_OWNER", agencies.get('competitor-agency')),
            ]
            
            for email, role, agency_id in role_updates:
                if agency_id:
                    result = await session.execute(text("""
                        UPDATE users 
                        SET role = :role, agency_id = :agency_id, updated_at = :now
                        WHERE email = :email
                        RETURNING id
                    """), {
                        "role": role,
                        "agency_id": agency_id,
                        "email": email,
                        "now": datetime.utcnow()
                    })
                    row = result.fetchone()
                    if row:
                        print(f"  ✅ Updated {email} to {role}")
                    else:
                        print(f"  ❌ User not found: {email}")
            
            # Create model profile
            print("\n3. Creating model profile...")
            model_result = await session.execute(text("""
                SELECT id, agency_id FROM users WHERE email = 'model@testagency.com'
            """))
            model_user = model_result.fetchone()
            
            if model_user:
                # Get chatter ID
                chatter_result = await session.execute(text("""
                    SELECT id FROM users WHERE email = 'chatter@testagency.com'
                """))
                chatter = chatter_result.fetchone()
                
                await session.execute(text("""
                    INSERT INTO model_profiles (
                        id, user_id, agency_id, stage_name, onlyfans_username,
                        bio, subscription_price, is_active,
                        inflow_api_key, inflow_account_id,
                        onlyfans_api_key, onlyfans_user_id,
                        settings, assigned_chatters,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :user_id, :agency_id, :stage_name, :of_username,
                        :bio, :price, :active,
                        :inflow_key, :inflow_account,
                        :of_key, :of_user,
                        :settings, :chatters,
                        :now, :now
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        assigned_chatters = EXCLUDED.assigned_chatters,
                        updated_at = :now
                """), {
                    "id": str(uuid.uuid4()),
                    "user_id": model_user.id,
                    "agency_id": model_user.agency_id,
                    "stage_name": "Emma Rose",
                    "of_username": "emmarose_of",
                    "bio": "Premium content creator | DM for customs",
                    "price": 9.99,
                    "active": True,
                    "inflow_key": "test_inflow_key_123",
                    "inflow_account": "inflow_account_emma",
                    "of_key": "test_of_key_123",
                    "of_user": "of_user_emma_123",
                    "settings": '{"auto_reply_enabled": true}',
                    "chatters": [chatter.id] if chatter else [],
                    "now": datetime.utcnow()
                })
                print("  ✅ Created model profile for Emma Rose")
            
            # Create commission rules
            print("\n4. Creating commission rules...")
            for agency_slug, agency_id in agencies.items():
                tiers = [
                    ("TIER_1", "Tier 1 - Starter", 70.00, 0, 5000),
                    ("TIER_2", "Tier 2 - Growth", 65.00, 5001, 10000),
                    ("TIER_3", "Tier 3 - Premium", 60.00, 10001, None)
                ]
                
                for tier, name, percentage, min_subs, max_subs in tiers:
                    await session.execute(text("""
                        INSERT INTO commission_rules (
                            id, agency_id, name, tier, percentage,
                            min_subscribers, max_subscribers, is_active,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :agency_id, :name, :tier, :percentage,
                            :min_subs, :max_subs, :active, :now, :now
                        )
                        ON CONFLICT DO NOTHING
                    """), {
                        "id": str(uuid.uuid4()),
                        "agency_id": agency_id,
                        "name": name,
                        "tier": tier,
                        "percentage": percentage,
                        "min_subs": min_subs,
                        "max_subs": max_subs,
                        "active": True,
                        "now": datetime.utcnow()
                    })
                print(f"  ✅ Created commission rules for {agency_slug}")
            
            await session.commit()
            print("\n✅ All fixes applied successfully!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(fix_roles())