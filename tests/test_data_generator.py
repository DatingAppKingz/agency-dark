#!/usr/bin/env python3
"""
Test Data Generator for AgencyDark
Creates comprehensive test data for WebSocket, Multi-tenant, and RBAC testing
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import random
import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TestDataGenerator:
    def __init__(self, db_url="postgresql://mariuszbudzisz@localhost:5432/agencydark_dev"):
        self.db_url = db_url
        self.conn = psycopg2.connect(db_url)
        self.cur = self.conn.cursor()
        self.password_hash = pwd_context.hash("Test123!")
        
    def create_agency(self, name, slug, domain):
        """Create a test agency"""
        agency_id = str(uuid.uuid4())
        self.cur.execute("""
            INSERT INTO agencies (id, name, slug, domain, settings, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, (
            agency_id,
            name,
            slug,
            domain,
            {
                "features": {
                    "analytics": True,
                    "financial": True,
                    "whitelabel": True
                },
                "commission_rate": 0.25
            }
        ))
        return self.cur.fetchone()[0]
    
    def create_users_for_agency(self, agency_id, agency_name):
        """Create all role types for an agency"""
        users = []
        
        # Define users for each role
        user_configs = [
            ("owner", f"owner@{agency_name}.com", f"{agency_name} Owner", "AGENCY_OWNER"),
            ("admin", f"admin@{agency_name}.com", f"{agency_name} Admin", "AGENCY_ADMIN"),
            ("model1", f"model1@{agency_name}.com", f"{agency_name} Model 1", "MODEL"),
            ("model2", f"model2@{agency_name}.com", f"{agency_name} Model 2", "MODEL"),
            ("chatter1", f"chatter1@{agency_name}.com", f"{agency_name} Chatter 1", "CHATTER"),
            ("chatter2", f"chatter2@{agency_name}.com", f"{agency_name} Chatter 2", "CHATTER"),
            ("member", f"member@{agency_name}.com", f"{agency_name} Member", "AGENCY_MEMBER"),
        ]
        
        for username, email, full_name, role in user_configs:
            user_id = str(uuid.uuid4())
            self.cur.execute("""
                INSERT INTO users (
                    id, email, hashed_password, full_name, role, agency_id, 
                    is_active, is_verified, created_at, verified_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, true, true, NOW(), NOW())
                ON CONFLICT (email) DO UPDATE SET 
                    role = EXCLUDED.role,
                    agency_id = EXCLUDED.agency_id
                RETURNING id
            """, (user_id, email, self.password_hash, full_name, role, agency_id))
            
            user_id = self.cur.fetchone()[0]
            users.append({
                "id": user_id,
                "email": email,
                "role": role,
                "username": username
            })
            
        return users
    
    def create_model_profiles(self, agency_id, model_users):
        """Create model profiles for model users"""
        profiles = []
        
        for i, user in enumerate(model_users):
            profile_id = str(uuid.uuid4())
            stage_names = ["Bella Rose", "Sophia Sky", "Luna Star", "Mia Moon"]
            
            self.cur.execute("""
                INSERT INTO model_profiles (
                    id, user_id, agency_id, display_name, bio,
                    onlyfans_username, onlyfans_user_id, is_active,
                    subscriber_count, paying_subscriber_count,
                    total_earnings, commission_rate,
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, true,
                    %s, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name
                RETURNING id
            """, (
                profile_id,
                user["id"],
                agency_id,
                stage_names[i % len(stage_names)],
                f"Premium content creator at {user['email'].split('@')[1]}",
                f"{user['username']}_of",
                f"of_user_{i+1}",
                random.randint(500, 5000),  # subscribers
                random.randint(100, 1000),  # paying subscribers
                random.randint(10000, 100000),  # total earnings
                0.25  # commission rate
            ))
            
            profile_id = self.cur.fetchone()[0]
            profiles.append({
                "id": profile_id,
                "user_id": user["id"],
                "username": user["username"]
            })
            
        return profiles
    
    def assign_chatters_to_models(self, model_profiles, chatter_users):
        """Create model-chatter assignments"""
        for profile in model_profiles:
            # Assign 1-2 chatters to each model
            num_chatters = random.randint(1, min(2, len(chatter_users)))
            assigned_chatters = random.sample(chatter_users, num_chatters)
            
            for chatter in assigned_chatters:
                self.cur.execute("""
                    INSERT INTO model_chatters (
                        model_id, chatter_id, assigned_at, is_active
                    )
                    VALUES (%s, %s, NOW(), true)
                    ON CONFLICT (model_id, chatter_id) DO NOTHING
                """, (profile["id"], chatter["id"]))
    
    def create_chat_messages(self, model_profiles, num_messages=50):
        """Create sample chat messages"""
        fan_names = ["John", "Mike", "David", "James", "Robert", "William"]
        message_templates = [
            "Hey beautiful!",
            "Love your content!",
            "Can we chat?",
            "You're amazing!",
            "Just subscribed!",
            "When's your next post?"
        ]
        
        for profile in model_profiles:
            for _ in range(num_messages):
                fan_id = f"fan_{random.randint(1000, 9999)}"
                fan_name = random.choice(fan_names)
                
                self.cur.execute("""
                    INSERT INTO chat_messages (
                        id, model_id, fan_id, fan_username,
                        message, is_from_fan, created_at
                    )
                    VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, true, 
                        NOW() - INTERVAL '%s minutes'
                    )
                """, (
                    profile["id"],
                    fan_id,
                    fan_name,
                    random.choice(message_templates),
                    random.randint(0, 1440)  # within last 24 hours
                ))
    
    def create_financial_data(self, agency_id, model_profiles):
        """Create financial transactions and commission rules"""
        # Commission rules
        self.cur.execute("""
            INSERT INTO commission_rules (
                id, agency_id, name, tier, rate,
                min_subscribers, max_subscribers,
                is_active, created_at
            )
            VALUES 
                (gen_random_uuid(), %s, 'Starter', 'tier_1', 0.20, 0, 100, true, NOW()),
                (gen_random_uuid(), %s, 'Growth', 'tier_2', 0.25, 101, 500, true, NOW()),
                (gen_random_uuid(), %s, 'Premium', 'tier_3', 0.30, 501, NULL, true, NOW())
        """, (agency_id, agency_id, agency_id))
        
        # Create transactions
        transaction_types = ['subscription', 'tip', 'ppv_purchase', 'stream_tip']
        
        for profile in model_profiles:
            for _ in range(random.randint(10, 30)):
                amount = random.randint(5, 200)
                commission = amount * 0.25
                
                self.cur.execute("""
                    INSERT INTO financial_transactions (
                        id, agency_id, model_id, transaction_type,
                        amount, commission_amount, status,
                        processed_at, created_at
                    )
                    VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s,
                        'completed', NOW() - INTERVAL '%s days', 
                        NOW() - INTERVAL '%s days'
                    )
                """, (
                    agency_id,
                    profile["id"],
                    random.choice(transaction_types),
                    amount,
                    commission,
                    random.randint(0, 30),
                    random.randint(0, 30)
                ))
    
    def create_whitelabel_config(self, agency_id):
        """Create white-label configuration"""
        self.cur.execute("""
            INSERT INTO theme_configurations (
                id, agency_id, default_mode, allow_user_preference,
                light_theme, dark_theme, created_at
            )
            VALUES (
                gen_random_uuid(), %s, 'light', true,
                %s, %s, NOW()
            )
            ON CONFLICT (agency_id) DO UPDATE SET
                default_mode = EXCLUDED.default_mode
        """, (
            agency_id,
            {
                "primary": "#3B82F6",
                "secondary": "#8B5CF6",
                "background": "#FFFFFF",
                "text": "#1F2937"
            },
            {
                "primary": "#60A5FA",
                "secondary": "#A78BFA",
                "background": "#1F2937",
                "text": "#F9FAFB"
            }
        ))
    
    def generate_complete_test_data(self):
        """Generate complete test dataset"""
        print("🚀 Generating comprehensive test data...")
        
        # Create multiple agencies
        agencies = [
            ("Test Agency Premium", "test-agency-premium", "premium.testagency.com"),
            ("Competitor Agency", "competitor-agency", "competitor.agency.com"),
            ("Elite Models Agency", "elite-models", "elite.models.com"),
        ]
        
        for agency_name, slug, domain in agencies:
            print(f"\n📁 Creating agency: {agency_name}")
            
            # Create agency
            agency_id = self.create_agency(agency_name, slug, domain)
            print(f"  ✅ Agency created: {agency_id}")
            
            # Create users
            users = self.create_users_for_agency(agency_id, slug.replace("-", ""))
            print(f"  ✅ Created {len(users)} users")
            
            # Get models and chatters
            model_users = [u for u in users if u["role"] == "MODEL"]
            chatter_users = [u for u in users if u["role"] == "CHATTER"]
            
            # Create model profiles
            profiles = self.create_model_profiles(agency_id, model_users)
            print(f"  ✅ Created {len(profiles)} model profiles")
            
            # Assign chatters
            self.assign_chatters_to_models(profiles, chatter_users)
            print(f"  ✅ Assigned chatters to models")
            
            # Create chat messages
            self.create_chat_messages(profiles, num_messages=20)
            print(f"  ✅ Created chat messages")
            
            # Create financial data
            self.create_financial_data(agency_id, profiles)
            print(f"  ✅ Created financial data")
            
            # Create white-label config
            self.create_whitelabel_config(agency_id)
            print(f"  ✅ Created white-label configuration")
        
        # Commit all changes
        self.conn.commit()
        print("\n✅ Test data generation complete!")
        
        # Print access info
        print("\n📋 Test Accounts (Password: Test123!):")
        print("=" * 60)
        for agency_name, slug, _ in agencies:
            print(f"\n{agency_name}:")
            print(f"  Owner: owner@{slug.replace('-', '')}.com")
            print(f"  Admin: admin@{slug.replace('-', '')}.com")
            print(f"  Model: model1@{slug.replace('-', '')}.com")
            print(f"  Chatter: chatter1@{slug.replace('-', '')}.com")
    
    def cleanup(self):
        """Close database connection"""
        self.cur.close()
        self.conn.close()


if __name__ == "__main__":
    generator = TestDataGenerator()
    try:
        generator.generate_complete_test_data()
    finally:
        generator.cleanup()