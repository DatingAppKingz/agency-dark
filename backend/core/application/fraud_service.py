"""Fraud detection service for identifying suspicious activities."""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime, timedelta, date
from decimal import Decimal
import hashlib
import json

from models.user import User
from models.agency import Agency
from models.model import Model
from models.financial import Transaction
from models.chat import Conversation, Message
from core.exceptions import ValidationError, NotFoundError
from core.redis import redis_manager, cached
from core.celery_app import celery_app as celery


class FraudService:
    """Service for detecting and managing fraudulent activities."""
    
    # Risk score thresholds
    RISK_THRESHOLD_LOW = 30
    RISK_THRESHOLD_MEDIUM = 60
    RISK_THRESHOLD_HIGH = 80
    
    # Fraud indicators and their weights
    FRAUD_INDICATORS = {
        "rapid_transactions": 20,  # Multiple transactions in short time
        "unusual_amount": 15,      # Transaction amount deviates from normal
        "new_fan": 10,            # Fan account is very new
        "location_mismatch": 15,   # IP location doesn't match profile
        "velocity_spike": 25,      # Sudden increase in activity
        "pattern_anomaly": 15,     # Deviates from normal patterns
        "chargeback_history": 30,  # Previous chargebacks
        "multiple_cards": 20       # Using multiple payment methods
    }
    
    @staticmethod
    async def check_transaction(
        db: AsyncSession,
        transaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check a transaction for fraud indicators."""
        risk_score = 0
        indicators = []
        
        # Extract transaction details
        fan_id = transaction_data.get("fan_id")
        amount = Decimal(str(transaction_data.get("amount", 0)))
        payment_method = transaction_data.get("payment_method")
        ip_address = transaction_data.get("ip_address")
        
        # For now, we'll work with transaction data directly
        # In production, this would check against a Fan model
        
        # Check 1: New fan (simplified - check first transaction date)
        first_trans = await db.execute(
            select(func.min(Transaction.created_at))
            .where(Transaction.fan_id == fan_id)
        )
        first_date = first_trans.scalar()
        if first_date:
            account_age = (datetime.utcnow() - first_date).days
            if account_age < 7:
                risk_score += FraudService.FRAUD_INDICATORS["new_fan"]
                indicators.append({
                    "type": "new_fan",
                    "details": f"First transaction: {account_age} days ago",
                    "score": FraudService.FRAUD_INDICATORS["new_fan"]
                })
        
        # Check 2: Rapid transactions
        recent_trans = await FraudService._check_rapid_transactions(
            db, fan_id, hours=1
        )
        if recent_trans > 3:
            risk_score += FraudService.FRAUD_INDICATORS["rapid_transactions"]
            indicators.append({
                "type": "rapid_transactions",
                "details": f"{recent_trans} transactions in last hour",
                "score": FraudService.FRAUD_INDICATORS["rapid_transactions"]
            })
        
        # Check 3: Unusual amount
        avg_amount = await FraudService._get_average_transaction_amount(db, fan_id)
        if avg_amount > 0:
            deviation = abs(float(amount - avg_amount) / float(avg_amount))
            if deviation > 2.0:  # More than 200% deviation
                risk_score += FraudService.FRAUD_INDICATORS["unusual_amount"]
                indicators.append({
                    "type": "unusual_amount",
                    "details": f"Amount ${amount} deviates {deviation:.1%} from average ${avg_amount}",
                    "score": FraudService.FRAUD_INDICATORS["unusual_amount"]
                })
        
        # Check 4: Velocity spike
        velocity_spike = await FraudService._check_velocity_spike(db, fan_id)
        if velocity_spike:
            risk_score += FraudService.FRAUD_INDICATORS["velocity_spike"]
            indicators.append({
                "type": "velocity_spike",
                "details": "Sudden increase in transaction frequency",
                "score": FraudService.FRAUD_INDICATORS["velocity_spike"]
            })
        
        # Check 5: Multiple payment methods
        payment_methods = await FraudService._count_payment_methods(db, fan_id)
        if payment_methods > 2:
            risk_score += FraudService.FRAUD_INDICATORS["multiple_cards"]
            indicators.append({
                "type": "multiple_cards",
                "details": f"Using {payment_methods} different payment methods",
                "score": FraudService.FRAUD_INDICATORS["multiple_cards"]
            })
        
        # Determine risk level
        if risk_score >= FraudService.RISK_THRESHOLD_HIGH:
            risk_level = "high"
            action = "block"
        elif risk_score >= FraudService.RISK_THRESHOLD_MEDIUM:
            risk_level = "medium"
            action = "review"
        elif risk_score >= FraudService.RISK_THRESHOLD_LOW:
            risk_level = "low"
            action = "monitor"
        else:
            risk_level = "minimal"
            action = "allow"
        
        # Store fraud check result
        check_id = hashlib.md5(
            f"{fan_id}:{amount}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()
        
        result = {
            "check_id": check_id,
            "transaction_data": transaction_data,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recommended_action": action,
            "indicators": indicators,
            "checked_at": datetime.utcnow().isoformat()
        }
        
        # Cache result
        await redis_manager.set(
            f"fraud_check:{check_id}",
            result,
            expire=86400  # 24 hours
        )
        
        # If high risk, create alert
        if risk_level in ["high", "medium"]:
            await FraudService._create_alert(db, fan_id, result)
        
        return result
    
    @staticmethod
    async def get_alerts(
        db: AsyncSession,
        agency_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get fraud alerts for agency."""
        # Get alerts from Redis (would be database in production)
        pattern = f"fraud_alert:{agency_id}:*"
        
        alerts = []
        cursor = 0
        while True:
            cursor, keys = await redis_manager.client.scan(
                cursor, match=pattern, count=100
            )
            
            for key in keys[:limit]:
                alert_data = await redis_manager.get(key.decode())
                if alert_data:
                    if not status or alert_data.get("status") == status:
                        alerts.append(alert_data)
            
            if cursor == 0 or len(alerts) >= limit:
                break
        
        # Sort by created_at descending
        alerts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return alerts[:limit]
    
    @staticmethod
    async def update_alert_status(
        db: AsyncSession,
        alert_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """Update fraud alert status."""
        alert_key = f"fraud_alert:*:{alert_id}"
        
        # Find alert
        cursor = 0
        alert_found = None
        while True:
            cursor, keys = await redis_manager.client.scan(
                cursor, match=alert_key, count=10
            )
            if keys:
                alert_data = await redis_manager.get(keys[0].decode())
                if alert_data:
                    alert_found = alert_data
                    alert_key_full = keys[0].decode()
                    break
            if cursor == 0:
                break
        
        if not alert_found:
            raise NotFoundError("Alert not found")
        
        # Update alert
        alert_found["status"] = status
        alert_found["updated_at"] = datetime.utcnow().isoformat()
        if notes:
            alert_found["notes"] = notes
        
        await redis_manager.set(
            alert_key_full,
            alert_found,
            expire=604800  # 7 days
        )
        
        return True
    
    @staticmethod
    async def get_risk_profile(
        db: AsyncSession,
        fan_id: int
    ) -> Dict[str, Any]:
        """Get comprehensive risk profile for a fan."""
        # Check if fan has any transactions
        trans_check = await db.execute(
            select(func.count(Transaction.id))
            .where(Transaction.fan_id == fan_id)
        )
        if not trans_check.scalar():
            raise NotFoundError("Fan not found")
        
        # Get transaction history
        trans_count = await db.execute(
            select(func.count(Transaction.id))
            .where(Transaction.fan_id == fan_id)
        )
        total_transactions = trans_count.scalar() or 0
        
        # Get chargeback count
        chargeback_count = await db.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.status == "refunded"
                )
            )
        )
        chargebacks = chargeback_count.scalar() or 0
        
        # Calculate risk factors
        # Get first transaction date for account age
        first_trans = await db.execute(
            select(func.min(Transaction.created_at))
            .where(Transaction.fan_id == fan_id)
        )
        first_date = first_trans.scalar()
        account_age = (datetime.utcnow() - first_date).days if first_date else 0
        chargeback_rate = (chargebacks / total_transactions * 100) if total_transactions > 0 else 0
        
        # Get agency_id from transaction
        agency_result = await db.execute(
            select(Transaction.agency_id)
            .where(Transaction.fan_id == fan_id)
            .limit(1)
        )
        agency_id = agency_result.scalar()
        
        # Get recent alerts
        recent_alerts = await FraudService.get_alerts(
            db, agency_id, limit=10
        ) if agency_id else []
        fan_alerts = [a for a in recent_alerts if a.get("fan_id") == fan_id]
        
        return {
            "fan_id": fan_id,
            "account_age_days": account_age,
            "total_transactions": total_transactions,
            "chargebacks": chargebacks,
            "chargeback_rate": chargeback_rate,
            "risk_indicators": {
                "new_account": account_age < 30,
                "high_chargeback_rate": chargeback_rate > 5,
                "recent_alerts": len(fan_alerts) > 0
            },
            "recent_alerts": fan_alerts,
            "overall_risk": "high" if chargeback_rate > 5 or len(fan_alerts) > 2 else "low"
        }
    
    @staticmethod
    async def _check_rapid_transactions(
        db: AsyncSession,
        fan_id: int,
        hours: int = 1
    ) -> int:
        """Check for rapid transactions."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await db.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= since
                )
            )
        )
        
        return result.scalar() or 0
    
    @staticmethod
    async def _get_average_transaction_amount(
        db: AsyncSession,
        fan_id: int
    ) -> Decimal:
        """Get average transaction amount for fan."""
        result = await db.execute(
            select(func.avg(Transaction.amount))
            .where(Transaction.fan_id == fan_id)
        )
        
        avg = result.scalar()
        return Decimal(str(avg)) if avg else Decimal(0)
    
    @staticmethod
    async def _check_velocity_spike(
        db: AsyncSession,
        fan_id: int
    ) -> bool:
        """Check for velocity spike in transactions."""
        # Compare last 24 hours to previous week average
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        # Recent transactions
        recent = await db.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= day_ago
                )
            )
        )
        recent_count = recent.scalar() or 0
        
        # Week average
        week = await db.execute(
            select(func.count(Transaction.id))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= week_ago,
                    Transaction.created_at < day_ago
                )
            )
        )
        week_count = week.scalar() or 0
        week_avg = week_count / 6  # 6 days
        
        # Spike if recent is 3x higher than average
        return recent_count > week_avg * 3 if week_avg > 0 else recent_count > 5
    
    @staticmethod
    async def _count_payment_methods(
        db: AsyncSession,
        fan_id: int
    ) -> int:
        """Count unique payment methods used."""
        result = await db.execute(
            select(func.count(func.distinct(Transaction.payment_method_id)))
            .where(Transaction.fan_id == fan_id)
        )
        
        return result.scalar() or 0
    
    @staticmethod
    async def _create_alert(
        db: AsyncSession,
        fan_id: int,
        check_result: Dict[str, Any]
    ):
        """Create fraud alert."""
        # Get agency_id from transaction data
        agency_id = check_result.get("transaction_data", {}).get("agency_id")
        if not agency_id:
            # Try to get from database
            agency_result = await db.execute(
                select(Transaction.agency_id)
                .where(Transaction.fan_id == fan_id)
                .limit(1)
            )
            agency_id = agency_result.scalar()
            if not agency_id:
                return
        
        alert_id = hashlib.md5(
            f"{fan_id}:{check_result['check_id']}".encode()
        ).hexdigest()[:16]
        
        alert = {
            "alert_id": alert_id,
            "agency_id": agency_id,
            "fan_id": fan_id,
            "check_id": check_result["check_id"],
            "risk_level": check_result["risk_level"],
            "risk_score": check_result["risk_score"],
            "indicators": check_result["indicators"],
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        await redis_manager.set(
            f"fraud_alert:{agency_id}:{alert_id}",
            alert,
            expire=604800  # 7 days
        )
        
        # Schedule review task if medium/high risk
        if check_result["risk_level"] in ["high", "medium"]:
            celery.send_task(
                "tasks.review_fraud_alert",
                args=[alert_id],
                countdown=300  # Review in 5 minutes
            )