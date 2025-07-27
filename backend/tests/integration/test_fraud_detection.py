"""
Integration tests for fraud detection system.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from core.fraud_detection.fraud_detector import fraud_detector
from core.fraud_detection.models import (
    FraudRule, FraudScore, FraudEvent, FraudPattern,
    VelocityCheck, ReviewQueue, FraudWhitelist,
    RiskLevel, FraudType, ActionType
)
from core.domain.models import User, Agency, Transaction


class TestFraudDetector:
    
    @pytest.mark.asyncio
    async def test_basic_fraud_check(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test basic fraud detection functionality."""
        transaction_data = {
            "id": str(uuid4()),
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        assert "allowed" in result
        assert "risk_score" in result
        assert "risk_level" in result
        assert "reasons" in result
        assert "action" in result
        
        # First transaction should be low risk
        assert result["allowed"] is True
        assert result["risk_level"] == RiskLevel.LOW
    
    @pytest.mark.asyncio
    async def test_velocity_detection(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test velocity-based fraud detection."""
        # Create velocity check
        velocity_check = VelocityCheck(
            name="Test rapid transactions",
            check_type="transaction_count",
            entity_type="user",
            time_window_seconds=300,  # 5 minutes
            max_count=3,
            risk_score=50,
            is_active=True
        )
        db_session.add(velocity_check)
        await db_session.commit()
        
        # Make multiple transactions quickly
        for i in range(5):
            transaction_data = {
                "id": str(uuid4()),
                "amount": 50.0,
                "currency": "USD",
                "payment_method": "card",
                "agency_id": str(test_user.agency_id)
            }
            
            result = await fraud_detector.check_transaction(
                transaction_data=transaction_data,
                user_id=str(test_user.id),
                ip_address="192.168.1.1",
                session=db_session
            )
            
            if i < 3:
                # First 3 should be allowed
                assert result["allowed"] is True
            else:
                # After velocity limit, risk should increase
                assert result["risk_score"] >= 50
                assert "velocity" in " ".join(result["reasons"]).lower()
    
    @pytest.mark.asyncio
    async def test_pattern_matching(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test pattern-based fraud detection."""
        # Create a fraud pattern
        pattern = FraudPattern(
            name="Small amount pattern",
            pattern_type="transactional",
            fraud_type=FraudType.PAYMENT_FRAUD,
            pattern_data={
                "amount": {"operator": "lt", "value": 10},
                "payment_method": "card"
            },
            risk_score=40,
            is_active=True
        )
        db_session.add(pattern)
        await db_session.commit()
        
        # Test matching transaction
        transaction_data = {
            "id": str(uuid4()),
            "amount": 5.0,  # Matches pattern
            "currency": "USD",
            "payment_method": "card",  # Matches pattern
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        assert result["risk_score"] >= 40
        assert "pattern" in " ".join(result["reasons"]).lower()
        
        # Verify pattern match count was updated
        await db_session.refresh(pattern)
        assert pattern.match_count == 1
    
    @pytest.mark.asyncio
    async def test_anomaly_detection(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test anomaly-based fraud detection."""
        # Create transaction history
        for i in range(20):
            transaction = Transaction(
                user_id=test_user.id,
                agency_id=test_user.agency_id,
                type="payment",
                amount=50.0 + (i % 10),  # Normal range 50-60
                currency="USD",
                status="completed",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(transaction)
        await db_session.commit()
        
        # Test anomalous amount
        transaction_data = {
            "id": str(uuid4()),
            "amount": 5000.0,  # Way outside normal range
            "currency": "USD",
            "payment_method": "card",
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        assert result["risk_score"] > 0
        assert "unusual" in " ".join(result["reasons"]).lower()
    
    @pytest.mark.asyncio
    async def test_whitelist(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test whitelisting functionality."""
        # Add user to whitelist
        whitelist = FraudWhitelist(
            entity_type="user",
            entity_id=str(test_user.id),
            reason="Trusted user",
            whitelist_level="full",
            created_by_id=test_user.id,
            approved_by_id=test_user.id
        )
        db_session.add(whitelist)
        await db_session.commit()
        
        # Clear cache
        await fraud_detector.redis.delete(f"whitelist:user:{test_user.id}")
        
        # Even suspicious transaction should be allowed
        transaction_data = {
            "id": str(uuid4()),
            "amount": 10000.0,  # High amount
            "currency": "USD",
            "payment_method": "card",
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        assert result["allowed"] is True
        assert result["risk_score"] == 0
        assert result["reasons"] == ["whitelisted"]
    
    @pytest.mark.asyncio
    async def test_fraud_scoring(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test fraud score calculation and persistence."""
        # Make a suspicious transaction
        transaction_data = {
            "id": str(uuid4()),
            "amount": 1000.0,
            "currency": "USD",
            "payment_method": "card",
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        # Check fraud score was created/updated
        from sqlalchemy import select, and_
        score_result = await db_session.execute(
            select(FraudScore).where(
                and_(
                    FraudScore.entity_type == "user",
                    FraudScore.entity_id == str(test_user.id)
                )
            )
        )
        
        score = score_result.scalar_one_or_none()
        assert score is not None
        assert score.current_score == result["risk_score"]
        assert score.risk_level == result["risk_level"]
    
    @pytest.mark.asyncio
    async def test_review_queue(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test review queue functionality."""
        # Create a rule that triggers review
        rule = FraudRule(
            name="High amount review",
            rule_type="threshold",
            fraud_type=FraudType.PAYMENT_FRAUD,
            conditions=[
                {"field": "amount", "operator": "greater_than", "value": 500}
            ],
            risk_score=60,
            auto_action=ActionType.REVIEW,
            is_active=True,
            created_by_id=test_user.id
        )
        db_session.add(rule)
        await db_session.commit()
        
        # Make transaction that triggers review
        transaction_data = {
            "id": str(uuid4()),
            "amount": 750.0,
            "currency": "USD",
            "payment_method": "card",
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        # Check review queue
        from sqlalchemy import select
        queue_result = await db_session.execute(
            select(ReviewQueue).where(
                ReviewQueue.entity_id == transaction_data["id"]
            )
        )
        
        review_item = queue_result.scalar_one_or_none()
        assert review_item is not None
        assert review_item.status == "pending"
        assert review_item.risk_score == result["risk_score"]
    
    @pytest.mark.asyncio
    async def test_fraud_event_logging(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test fraud event logging."""
        # Create a pattern that will trigger
        pattern = FraudPattern(
            name="Test pattern",
            pattern_type="transactional",
            fraud_type=FraudType.SUSPICIOUS_BEHAVIOR,
            pattern_data={"test": True},
            risk_score=50,
            is_active=True
        )
        db_session.add(pattern)
        await db_session.commit()
        
        # Make suspicious transaction
        transaction_data = {
            "id": str(uuid4()),
            "amount": 100.0,
            "currency": "USD",
            "payment_method": "card",
            "test": True,  # Matches pattern
            "agency_id": str(test_user.agency_id)
        }
        
        result = await fraud_detector.check_transaction(
            transaction_data=transaction_data,
            user_id=str(test_user.id),
            ip_address="192.168.1.1",
            session=db_session
        )
        
        # Check fraud event was logged
        from sqlalchemy import select
        event_result = await db_session.execute(
            select(FraudEvent).where(
                FraudEvent.user_id == test_user.id
            ).order_by(FraudEvent.detected_at.desc())
        )
        
        event = event_result.scalar_one_or_none()
        assert event is not None
        assert event.risk_score == result["risk_score"]
        assert event.risk_level == result["risk_level"]
        assert event.ip_address == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_combined_risk_factors(
        self,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test combined risk factors increasing score."""
        # Create multiple risk factors
        
        # 1. Velocity check
        velocity = VelocityCheck(
            name="Quick transactions",
            check_type="transaction_count",
            entity_type="user",
            time_window_seconds=60,
            max_count=2,
            risk_score=20,
            is_active=True
        )
        
        # 2. Pattern
        pattern = FraudPattern(
            name="Round amount",
            pattern_type="transactional",
            fraud_type=FraudType.SUSPICIOUS_BEHAVIOR,
            pattern_data={"amount": 1000.0},
            risk_score=15,
            is_active=True
        )
        
        db_session.add_all([velocity, pattern])
        await db_session.commit()
        
        # 3. Create history (previous fraud event)
        previous_event = FraudEvent(
            event_type="transaction",
            entity_type="user",
            entity_id=str(test_user.id),
            fraud_type=FraudType.PAYMENT_FRAUD,
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            user_id=test_user.id,
            agency_id=test_user.agency_id,
            ip_address="192.168.1.1",
            false_positive=False
        )
        db_session.add(previous_event)
        await db_session.commit()
        
        # Make transactions to trigger multiple factors
        for i in range(3):
            transaction_data = {
                "id": str(uuid4()),
                "amount": 1000.0,  # Matches pattern
                "currency": "USD",
                "payment_method": "card",
                "agency_id": str(test_user.agency_id)
            }
            
            result = await fraud_detector.check_transaction(
                transaction_data=transaction_data,
                user_id=str(test_user.id),
                ip_address="192.168.1.1",
                session=db_session
            )
        
        # Last transaction should have high risk from combined factors
        assert result["risk_score"] >= 35  # velocity(20) + pattern(15) + history
        assert len(result["reasons"]) >= 2


class TestFraudDetectionAPI:
    
    @pytest.mark.asyncio
    async def test_fraud_dashboard(
        self,
        client,
        admin_headers,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test fraud dashboard endpoint."""
        # Create some fraud events
        for i, level in enumerate([RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]):
            event = FraudEvent(
                event_type="transaction",
                entity_type="user",
                entity_id=str(test_user.id),
                risk_score=30 * (i + 1),
                risk_level=level,
                user_id=test_user.id,
                agency_id=test_user.agency_id,
                ip_address="192.168.1.1",
                blocked=(level == RiskLevel.HIGH)
            )
            db_session.add(event)
        
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/fraud-detection/dashboard?hours=24",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "risk_distribution" in data
        assert "blocked_transactions" in data
        assert "review_queue_size" in data
        assert "top_fraud_types" in data
        
        # Check risk distribution
        assert data["risk_distribution"]["low"] >= 1
        assert data["risk_distribution"]["medium"] >= 1
        assert data["risk_distribution"]["high"] >= 1
        assert data["blocked_transactions"] >= 1
    
    @pytest.mark.asyncio
    async def test_create_fraud_rule(
        self,
        client,
        super_admin_headers,
        db_session: AsyncSession
    ):
        """Test creating fraud rule via API."""
        rule_data = {
            "name": "Test API Rule",
            "description": "Rule created via API",
            "rule_type": "threshold",
            "fraud_type": "payment_fraud",
            "conditions": {
                "amount": {"operator": "gt", "value": 1000}
            },
            "risk_score": 50,
            "auto_action": "review"
        }
        
        response = await client.post(
            "/api/v1/fraud-detection/rules",
            json=rule_data,
            headers=super_admin_headers
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify rule was created
        from sqlalchemy import select
        result = await db_session.execute(
            select(FraudRule).where(FraudRule.name == "Test API Rule")
        )
        rule = result.scalar_one_or_none()
        assert rule is not None
        assert rule.risk_score == 50
    
    @pytest.mark.asyncio
    async def test_manual_fraud_check(
        self,
        client,
        admin_headers,
        test_user: User
    ):
        """Test manual fraud check endpoint."""
        check_data = {
            "transaction_data": {
                "amount": 500.0,
                "currency": "USD",
                "payment_method": "card"
            },
            "user_id": str(test_user.id),
            "ip_address": "192.168.1.100"
        }
        
        response = await client.post(
            "/api/v1/fraud-detection/check",
            json=check_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "allowed" in data
        assert "risk_score" in data
        assert "risk_level" in data
        assert "reasons" in data
        assert "action" in data