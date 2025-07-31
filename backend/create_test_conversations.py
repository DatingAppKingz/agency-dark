#!/usr/bin/env python3
"""Create test conversations and transactions data"""

import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from models.user import User, UserRole
from models.model import Model
from models.chat import Conversation, ConversationStatus, Message, MessageType, MessageStatus
from models.financial import Transaction, TransactionType, TransactionStatus
from models.agency import Agency

async def create_test_data():
    async with AsyncSessionLocal() as db:
        print("Creating test conversations and transactions...")
        
        # Get chatters
        chatters_result = await db.execute(
            select(User).where(User.role == UserRole.CHATTER)
        )
        chatters = list(chatters_result.scalars())
        print(f"Found {len(chatters)} chatters")
        
        # Get models
        models_result = await db.execute(
            select(Model).limit(3)
        )
        models = list(models_result.scalars())
        print(f"Found {len(models)} models")
        
        # Get agencies
        agencies_result = await db.execute(
            select(Agency).limit(2)
        )
        agencies = list(agencies_result.scalars())
        print(f"Found {len(agencies)} agencies")
        
        if not models:
            print("No models found. Please run the initial data setup first.")
            return
        
        # Create conversations
        conversations = []
        fan_names = [
            ("superfan1", "Super Fan 1"),
            ("megafan2", "Mega Fan 2"),
            ("topfan3", "Top Fan 3"),
            ("vipfan4", "VIP Fan 4"),
            ("premiumfan5", "Premium Fan 5"),
            ("loyalfan6", "Loyal Fan 6"),
            ("newfan7", "New Fan 7"),
            ("regularfan8", "Regular Fan 8"),
            ("bigspender9", "Big Spender 9"),
            ("justlooking10", "Just Looking 10"),
            ("curious11", "Curious 11"),
            ("dedicated12", "Dedicated 12"),
            ("superfan13", "Super Fan 13"),
            ("megafan14", "Mega Fan 14"),
            ("topfan15", "Top Fan 15"),
        ]
        
        for i in range(15):
            model = models[i % len(models)]
            chatter = random.choice(chatters) if chatters else None
            fan_username, fan_display_name = fan_names[i % len(fan_names)]
            
            # Check if conversation already exists
            exists_check = await db.execute(
                select(func.count(Conversation.id)).where(
                    and_(
                        Conversation.model_id == model.id,
                        Conversation.fan_id == f"fan_{i+1}"
                    )
                )
            )
            exists = exists_check.scalar()
            
            if not exists:
                conversation = Conversation(
                    model_id=model.id,
                    fan_id=f"fan_{i+1}",
                    fan_username=fan_username,
                    fan_display_name=fan_display_name,
                    assigned_chatter_id=chatter.id if chatter else None,
                    assigned_at=datetime.utcnow().isoformat() if chatter else None,
                    status=ConversationStatus.ACTIVE if i < 10 else ConversationStatus.ARCHIVED,
                    priority=i if i < 5 else 0,  # Top 5 have priority
                    fan_location="USA" if i % 2 == 0 else "UK",
                    fan_timezone="America/New_York" if i % 2 == 0 else "Europe/London",
                    total_spent=Decimal(random.randint(100, 5000)),
                    total_tips=Decimal(random.randint(50, 1000)),
                    ppv_purchased=random.randint(0, 10),
                    last_message_at=(datetime.utcnow() - timedelta(minutes=random.randint(1, 120))).isoformat(),
                    last_fan_message_at=(datetime.utcnow() - timedelta(minutes=random.randint(1, 120))).isoformat(),
                    unread_count=random.randint(0, 5) if i < 10 else 0,
                    tags=["vip"] if i < 3 else ["regular"],
                    notes=f"Test notes for {fan_username}"
                )
                db.add(conversation)
                conversations.append(conversation)
        
        await db.flush()
        print(f"Created {len(conversations)} conversations")
        
        # Create messages
        messages = []
        for conv in conversations[:10]:  # Only active conversations
            # Get model user ID
            model_user = await db.execute(
                select(Model.user_id).where(Model.id == conv.model_id)
            )
            model_user_id = model_user.scalar()
            
            # Create 5-15 messages per conversation
            num_messages = random.randint(5, 15)
            for j in range(num_messages):
                # Alternate between model/chatter and fan
                if j % 2 == 0:
                    sender_id = conv.assigned_chatter_id if conv.assigned_chatter_id else model_user_id
                    sender_name = "Model/Chatter"
                else:
                    # For fan messages, use NULL for sender_id
                    sender_id = None  # NULL = fan according to model comment
                    sender_name = conv.fan_display_name
                
                message_type = MessageType.TEXT
                if random.random() < 0.1:  # 10% chance of tip message
                    message_type = MessageType.TIP
                elif random.random() < 0.05:  # 5% chance of PPV
                    message_type = MessageType.PPV
                
                message = Message(
                    conversation_id=conv.id,
                    sender_id=sender_id,
                    sender_type="model" if j % 2 == 0 else "fan",
                    content=f"Test message {j+1} from {sender_name}",
                    type=message_type,
                    status=MessageStatus.READ if j < num_messages - 2 else MessageStatus.SENT,
                    amount=Decimal(random.randint(10, 50)) if message_type == MessageType.PPV else Decimal(random.randint(5, 100)) if message_type == MessageType.TIP else None,
                    is_paid=True if message_type in [MessageType.PPV, MessageType.TIP] else False,
                    created_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
                    read_at=(datetime.utcnow() - timedelta(minutes=random.randint(0, 30))).isoformat() if j < num_messages - 2 else None
                )
                db.add(message)
                messages.append(message)
        
        await db.flush()
        print(f"Created {len(messages)} messages")
        
        # Create transactions
        transactions = []
        for i in range(30):
            model = random.choice(models)
            agency = agencies[0] if agencies else None
            
            # Some transactions linked to conversations
            conversation = random.choice(conversations) if i < 10 and conversations else None
            
            trans_type = random.choice([
                TransactionType.TIP,
                TransactionType.PPV,
                TransactionType.SUBSCRIPTION,
                TransactionType.MESSAGE
            ])
            
            gross_amount = Decimal(random.randint(10, 500))
            platform_fee = gross_amount * Decimal('0.20')  # 20% platform fee
            agency_commission = (gross_amount - platform_fee) * Decimal('0.30')  # 30% agency commission
            net_amount = gross_amount - platform_fee - agency_commission
            
            transaction = Transaction(
                agency_id=agency.id if agency else 1,
                model_id=model.id,
                type=trans_type,
                status=TransactionStatus.COMPLETED,
                platform_transaction_id=f"trans_{uuid.uuid4().hex[:8]}",
                conversation_id=conversation.id if conversation else None,
                gross_amount=gross_amount,
                platform_fee=platform_fee,
                agency_commission=agency_commission,
                net_amount=net_amount,
                fan_id=f"fan_{random.randint(1, 10)}",
                fan_username=f"superfan{random.randint(1, 10)}",
                transaction_date=datetime.utcnow().isoformat(),
                processed_at=datetime.utcnow().isoformat(),
                description=f"Test {trans_type.value} transaction",
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30))
            )
            db.add(transaction)
            transactions.append(transaction)
        
        await db.flush()
        print(f"Created {len(transactions)} transactions")
        
        # Commit all changes
        await db.commit()
        print("Test data created successfully!")
        
        # Print summary
        print("\nSummary:")
        print(f"- Conversations: {len(conversations)} (10 active, 5 archived)")
        print(f"- Messages: {len(messages)}")
        print(f"- Transactions: {len(transactions)} (some linked to conversations)")
        print(f"- Chatters with assigned conversations: {len([c for c in conversations if c.assigned_chatter_id])}")

if __name__ == "__main__":
    asyncio.run(create_test_data())