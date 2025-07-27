"""
Fraud detection service with anomaly detection, pattern matching, and risk scoring.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import statistics
import numpy as np
from collections import defaultdict
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from core.redis import redis_client
from core.database import get_db
from core.fraud_detection.models import (
    FraudRule, FraudScore, FraudEvent, FraudPattern,
    VelocityCheck, ReviewQueue, FraudWhitelist,
    RiskLevel, FraudType, ActionType
)
from core.domain.models import User, Transaction

logger = logging.getLogger(__name__)


class FraudDetector:
    """Main fraud detection service."""
    
    def __init__(self):
        self.redis = redis_client
        self._rule_cache = {}
        self._pattern_cache = {}
        self._whitelist_cache = {}
        
    async def check_transaction(
        self,
        transaction_data: Dict[str, Any],
        user_id: str,
        ip_address: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Check a transaction for fraud.
        
        Returns:
            Dict containing:
            - allowed: bool
            - risk_score: int
            - risk_level: RiskLevel
            - reasons: List[str]
            - action: ActionType
        """
        # Check whitelist first
        if await self._is_whitelisted(user_id, "user", session):
            return {
                "allowed": True,
                "risk_score": 0,
                "risk_level": RiskLevel.LOW,
                "reasons": ["whitelisted"],
                "action": ActionType.MONITOR
            }
        
        # Run all fraud checks in parallel
        tasks = [
            self._check_velocity(user_id, transaction_data, session),
            self._detect_anomalies(user_id, transaction_data, session),
            self._match_patterns(transaction_data, session),
            self._calculate_history_score(user_id, session),
            self._check_rules(transaction_data, user_id, session)
        ]
        
        results = await asyncio.gather(*tasks)
        velocity_result, anomaly_result, pattern_result, history_score, rule_result = results
        
        # Calculate total risk score
        total_score = (
            velocity_result["score"] +
            anomaly_result["score"] +
            pattern_result["score"] +
            history_score +
            rule_result["score"]
        )
        
        # Determine risk level
        risk_level = self._calculate_risk_level(total_score)
        
        # Combine all reasons
        reasons = (
            velocity_result.get("reasons", []) +
            anomaly_result.get("reasons", []) +
            pattern_result.get("reasons", []) +
            rule_result.get("reasons", [])
        )
        
        # Determine action
        action = await self._determine_action(
            total_score, risk_level, reasons, session
        )
        
        # Update fraud score
        await self._update_fraud_score(
            user_id, total_score, risk_level, 
            velocity_result["score"], pattern_result["score"],
            anomaly_result["score"], history_score,
            action, session
        )
        
        # Log fraud event if suspicious
        if risk_level != RiskLevel.LOW:
            await self._log_fraud_event(
                user_id, transaction_data, ip_address,
                total_score, risk_level, reasons,
                action, session
            )
        
        # Add to review queue if needed
        if action == ActionType.REVIEW:
            await self._add_to_review_queue(
                user_id, transaction_data, total_score,
                risk_level, reasons, session
            )
        
        return {
            "allowed": action not in [ActionType.BLOCK, ActionType.SUSPEND],
            "risk_score": total_score,
            "risk_level": risk_level,
            "reasons": reasons,
            "action": action
        }
    
    async def _check_velocity(
        self,
        user_id: str,
        transaction_data: Dict[str, Any],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Check velocity limits."""
        score = 0
        reasons = []
        
        # Get active velocity checks
        result = await session.execute(
            select(VelocityCheck)
            .where(VelocityCheck.is_active == True)
        )
        checks = result.scalars().all()
        
        for check in checks:
            key = f"velocity:{check.check_type}:{user_id}"
            window = check.time_window_seconds
            
            # Get current count
            current_count = await self.redis.get(key)
            current_count = int(current_count) if current_count else 0
            
            # Check limits
            if check.max_count and current_count >= check.max_count:
                score += check.risk_score
                reasons.append(f"High velocity: {check.name}")
            
            # Increment counter
            await self.redis.incr(key)
            await self.redis.expire(key, window)
            
            # Check amount-based velocity
            if check.check_type == "amount_sum" and check.max_amount:
                amount_key = f"velocity:amount:{user_id}"
                current_amount = await self.redis.get(amount_key)
                current_amount = float(current_amount) if current_amount else 0.0
                
                if current_amount + transaction_data.get("amount", 0) > check.max_amount:
                    score += check.risk_score
                    reasons.append(f"Amount velocity exceeded: {check.name}")
                
                # Update amount
                await self.redis.incrbyfloat(amount_key, transaction_data.get("amount", 0))
                await self.redis.expire(amount_key, window)
        
        return {"score": score, "reasons": reasons}
    
    async def _detect_anomalies(
        self,
        user_id: str,
        transaction_data: Dict[str, Any],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Detect anomalous behavior using statistical methods."""
        score = 0
        reasons = []
        anomaly_factors = {}
        
        # Get user's transaction history
        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(100)
        )
        transactions = result.scalars().all()
        
        if len(transactions) < 10:
            # Not enough history for anomaly detection
            return {"score": 0, "reasons": [], "factors": {}}
        
        # Extract features
        amounts = [t.amount for t in transactions]
        hours = [t.created_at.hour for t in transactions]
        days_of_week = [t.created_at.weekday() for t in transactions]
        
        # Check amount anomaly
        current_amount = transaction_data.get("amount", 0)
        if amounts:
            mean_amount = statistics.mean(amounts)
            std_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0
            
            if std_amount > 0:
                z_score = abs((current_amount - mean_amount) / std_amount)
                if z_score > 3:  # 3 standard deviations
                    score += 30
                    reasons.append(f"Unusual transaction amount (Z-score: {z_score:.2f})")
                    anomaly_factors["amount_z_score"] = z_score
                elif z_score > 2:
                    score += 15
                    reasons.append("Moderately unusual transaction amount")
                    anomaly_factors["amount_z_score"] = z_score
        
        # Check time-based anomaly
        current_hour = datetime.utcnow().hour
        if hours:
            # Check if transaction is at unusual hour
            hour_freq = defaultdict(int)
            for hour in hours:
                hour_freq[hour] += 1
            
            avg_freq = len(hours) / 24
            current_freq = hour_freq.get(current_hour, 0)
            
            if current_freq == 0:
                score += 20
                reasons.append(f"Transaction at unusual hour: {current_hour}:00")
                anomaly_factors["unusual_hour"] = True
        
        # Check transaction frequency anomaly
        recent_count = await self._get_recent_transaction_count(user_id, 3600, session)
        if recent_count > 5:
            score += 25
            reasons.append(f"High transaction frequency: {recent_count} in last hour")
            anomaly_factors["high_frequency"] = recent_count
        
        # Check location anomaly (if location data available)
        if "location" in transaction_data:
            location_anomaly = await self._check_location_anomaly(
                user_id, transaction_data["location"], session
            )
            if location_anomaly:
                score += location_anomaly["score"]
                reasons.extend(location_anomaly["reasons"])
                anomaly_factors["location"] = location_anomaly
        
        return {
            "score": score,
            "reasons": reasons,
            "factors": anomaly_factors
        }
    
    async def _match_patterns(
        self,
        transaction_data: Dict[str, Any],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Match against known fraud patterns."""
        score = 0
        reasons = []
        matches = []
        
        # Get active patterns
        result = await session.execute(
            select(FraudPattern)
            .where(FraudPattern.is_active == True)
        )
        patterns = result.scalars().all()
        
        for pattern in patterns:
            if self._pattern_matches(transaction_data, pattern.pattern_data):
                score += pattern.risk_score
                reasons.append(f"Matches fraud pattern: {pattern.name}")
                matches.append({
                    "pattern_id": str(pattern.id),
                    "pattern_name": pattern.name,
                    "fraud_type": pattern.fraud_type.value
                })
                
                # Update pattern statistics
                pattern.match_count += 1
                pattern.last_matched = datetime.utcnow()
        
        await session.commit()
        
        return {
            "score": score,
            "reasons": reasons,
            "matches": matches
        }
    
    def _pattern_matches(self, data: Dict[str, Any], pattern_data: Dict[str, Any]) -> bool:
        """Check if data matches a pattern."""
        for key, condition in pattern_data.items():
            if key not in data:
                return False
            
            value = data[key]
            
            # Handle different condition types
            if isinstance(condition, dict):
                op = condition.get("operator", "eq")
                cond_value = condition.get("value")
                
                if op == "eq" and value != cond_value:
                    return False
                elif op == "gt" and value <= cond_value:
                    return False
                elif op == "lt" and value >= cond_value:
                    return False
                elif op == "in" and value not in cond_value:
                    return False
                elif op == "contains" and cond_value not in str(value):
                    return False
            else:
                # Simple equality
                if value != condition:
                    return False
        
        return True
    
    async def _calculate_history_score(
        self,
        user_id: str,
        session: AsyncSession
    ) -> int:
        """Calculate score based on user's fraud history."""
        score = 0
        
        # Check previous fraud events
        result = await session.execute(
            select(func.count(FraudEvent.id))
            .where(
                and_(
                    FraudEvent.user_id == user_id,
                    FraudEvent.false_positive == False,
                    FraudEvent.detected_at >= datetime.utcnow() - timedelta(days=90)
                )
            )
        )
        fraud_count = result.scalar() or 0
        
        # Add score based on history
        if fraud_count > 5:
            score += 40
        elif fraud_count > 3:
            score += 25
        elif fraud_count > 1:
            score += 15
        elif fraud_count > 0:
            score += 10
        
        # Check if user has been blocked before
        result = await session.execute(
            select(FraudScore)
            .where(
                and_(
                    FraudScore.entity_type == "user",
                    FraudScore.entity_id == user_id
                )
            )
        )
        fraud_score = result.scalar_one_or_none()
        
        if fraud_score and fraud_score.max_score > 80:
            score += 20
        
        return score
    
    async def _check_rules(
        self,
        transaction_data: Dict[str, Any],
        user_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Check against configured fraud rules."""
        score = 0
        reasons = []
        triggered_rules = []
        
        # Get active rules
        result = await session.execute(
            select(FraudRule)
            .where(FraudRule.is_active == True)
            .order_by(FraudRule.priority.desc())
        )
        rules = result.scalars().all()
        
        for rule in rules:
            if self._evaluate_rule(transaction_data, user_id, rule):
                score += rule.risk_score
                reasons.append(f"Triggered rule: {rule.name}")
                triggered_rules.append(str(rule.id))
        
        return {
            "score": score,
            "reasons": reasons,
            "triggered_rules": triggered_rules
        }
    
    def _evaluate_rule(
        self,
        data: Dict[str, Any],
        user_id: str,
        rule: FraudRule
    ) -> bool:
        """Evaluate if a rule is triggered."""
        try:
            conditions = rule.conditions
            
            # Simple rule evaluation engine
            for condition in conditions:
                field = condition.get("field")
                operator = condition.get("operator")
                value = condition.get("value")
                
                # Get field value from data
                if field == "user_id":
                    field_value = user_id
                else:
                    field_value = data.get(field)
                
                if field_value is None:
                    return False
                
                # Evaluate condition
                if operator == "equals" and field_value != value:
                    return False
                elif operator == "greater_than" and field_value <= value:
                    return False
                elif operator == "less_than" and field_value >= value:
                    return False
                elif operator == "contains" and value not in str(field_value):
                    return False
                elif operator == "regex":
                    import re
                    if not re.match(value, str(field_value)):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.id}: {e}")
            return False
    
    def _calculate_risk_level(self, score: int) -> RiskLevel:
        """Calculate risk level from score."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def _determine_action(
        self,
        score: int,
        risk_level: RiskLevel,
        reasons: List[str],
        session: AsyncSession
    ) -> ActionType:
        """Determine what action to take based on risk."""
        if score >= 100:
            return ActionType.BLOCK
        elif score >= 80:
            return ActionType.SUSPEND
        elif score >= 60:
            return ActionType.REVIEW
        elif score >= 40:
            return ActionType.RESTRICT
        elif score >= 20:
            return ActionType.FLAG
        else:
            return ActionType.MONITOR
    
    async def _update_fraud_score(
        self,
        user_id: str,
        total_score: int,
        risk_level: RiskLevel,
        velocity_score: int,
        pattern_score: int,
        anomaly_score: int,
        history_score: int,
        action: ActionType,
        session: AsyncSession
    ):
        """Update or create fraud score for user."""
        result = await session.execute(
            select(FraudScore)
            .where(
                and_(
                    FraudScore.entity_type == "user",
                    FraudScore.entity_id == user_id
                )
            )
        )
        fraud_score = result.scalar_one_or_none()
        
        if not fraud_score:
            fraud_score = FraudScore(
                entity_type="user",
                entity_id=user_id
            )
            session.add(fraud_score)
        
        # Update scores
        fraud_score.current_score = total_score
        fraud_score.max_score = max(fraud_score.max_score, total_score)
        fraud_score.risk_level = risk_level
        fraud_score.velocity_score = velocity_score
        fraud_score.pattern_score = pattern_score
        fraud_score.anomaly_score = anomaly_score
        fraud_score.history_score = history_score
        fraud_score.auto_action_taken = action
        fraud_score.last_activity = datetime.utcnow()
        fraud_score.score_updated_at = datetime.utcnow()
        
        if action in [ActionType.BLOCK, ActionType.SUSPEND]:
            fraud_score.is_blocked = True
        elif action == ActionType.REVIEW:
            fraud_score.is_under_review = True
        
        await session.commit()
    
    async def _log_fraud_event(
        self,
        user_id: str,
        transaction_data: Dict[str, Any],
        ip_address: str,
        risk_score: int,
        risk_level: RiskLevel,
        reasons: List[str],
        action: ActionType,
        session: AsyncSession
    ):
        """Log a fraud detection event."""
        event = FraudEvent(
            event_type="transaction",
            entity_type="user",
            entity_id=user_id,
            fraud_type=self._determine_fraud_type(reasons),
            risk_score=risk_score,
            risk_level=risk_level,
            ip_address=ip_address,
            amount=transaction_data.get("amount"),
            currency=transaction_data.get("currency"),
            payment_method=transaction_data.get("payment_method"),
            action_taken=action,
            blocked=action in [ActionType.BLOCK, ActionType.SUSPEND],
            user_id=user_id,
            agency_id=transaction_data.get("agency_id")
        )
        
        session.add(event)
        await session.commit()
    
    def _determine_fraud_type(self, reasons: List[str]) -> FraudType:
        """Determine fraud type from reasons."""
        reason_text = " ".join(reasons).lower()
        
        if "velocity" in reason_text or "frequency" in reason_text:
            return FraudType.VELOCITY_ABUSE
        elif "pattern" in reason_text:
            return FraudType.SUSPICIOUS_BEHAVIOR
        elif "payment" in reason_text:
            return FraudType.PAYMENT_FRAUD
        elif "bot" in reason_text:
            return FraudType.BOT_ACTIVITY
        else:
            return FraudType.SUSPICIOUS_BEHAVIOR
    
    async def _add_to_review_queue(
        self,
        user_id: str,
        transaction_data: Dict[str, Any],
        risk_score: int,
        risk_level: RiskLevel,
        reasons: List[str],
        session: AsyncSession
    ):
        """Add item to manual review queue."""
        review_item = ReviewQueue(
            priority=self._calculate_priority(risk_score),
            entity_type="transaction",
            entity_id=transaction_data.get("id", "unknown"),
            reason="; ".join(reasons),
            risk_score=risk_score,
            risk_level=risk_level,
            evidence=transaction_data,
            user_id=user_id,
            agency_id=transaction_data.get("agency_id"),
            due_date=datetime.utcnow() + timedelta(hours=24)
        )
        
        session.add(review_item)
        await session.commit()
    
    def _calculate_priority(self, risk_score: int) -> int:
        """Calculate review priority based on risk score."""
        if risk_score >= 80:
            return 10
        elif risk_score >= 60:
            return 7
        elif risk_score >= 40:
            return 5
        else:
            return 3
    
    async def _is_whitelisted(
        self,
        entity_id: str,
        entity_type: str,
        session: AsyncSession
    ) -> bool:
        """Check if entity is whitelisted."""
        # Check cache first
        cache_key = f"whitelist:{entity_type}:{entity_id}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached == "true"
        
        # Check database
        result = await session.execute(
            select(FraudWhitelist)
            .where(
                and_(
                    FraudWhitelist.entity_type == entity_type,
                    FraudWhitelist.entity_id == entity_id,
                    or_(
                        FraudWhitelist.valid_until.is_(None),
                        FraudWhitelist.valid_until > datetime.utcnow()
                    )
                )
            )
        )
        whitelist = result.scalar_one_or_none()
        
        # Cache result
        is_whitelisted = whitelist is not None
        await self.redis.setex(cache_key, 3600, "true" if is_whitelisted else "false")
        
        return is_whitelisted
    
    async def _get_recent_transaction_count(
        self,
        user_id: str,
        seconds: int,
        session: AsyncSession
    ) -> int:
        """Get count of recent transactions."""
        since = datetime.utcnow() - timedelta(seconds=seconds)
        
        result = await session.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.created_at >= since
                )
            )
        )
        
        return result.scalar() or 0
    
    async def _check_location_anomaly(
        self,
        user_id: str,
        location: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Check for location-based anomalies."""
        # This would implement geo-velocity checks
        # For now, return None
        return None


# Singleton instance
fraud_detector = FraudDetector()