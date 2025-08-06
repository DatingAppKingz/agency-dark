"""
Advanced Fraud Detection System

Features:
- Real-time anomaly detection
- Velocity checks for transactions
- Behavioral pattern analysis
- Machine learning-based scoring
- Automatic blocking mechanisms
"""
import asyncio
import hashlib
import json
import math
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import numpy as np
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_

from core.redis import redis_client
from core.logging import get_logger
from core.config import settings
from core.tasks.db_context import get_db_context
from models.user import User
from models.api_key import APIKey

logger = get_logger(__name__)


class FraudRiskLevel(str, Enum):
    """Risk levels for fraud detection"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudIndicator(str, Enum):
    """Types of fraud indicators"""
    VELOCITY_CHECK = "velocity_check"
    GEO_ANOMALY = "geo_anomaly"
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    TRANSACTION_PATTERN = "transaction_pattern"
    ACCOUNT_TAKEOVER = "account_takeover"
    API_ABUSE = "api_abuse"
    PAYMENT_FRAUD = "payment_fraud"
    IDENTITY_FRAUD = "identity_fraud"


@dataclass
class FraudScore:
    """Fraud risk score with details"""
    score: float  # 0-100
    risk_level: FraudRiskLevel
    indicators: List[Dict[str, Any]]
    confidence: float  # 0-1
    recommendations: List[str]
    block_transaction: bool = False
    require_verification: bool = False


@dataclass
class VelocityRule:
    """Velocity check rule configuration"""
    name: str
    window_seconds: int
    max_count: int
    action: str  # "block", "flag", "monitor"
    weight: float = 1.0  # Impact on fraud score


class FraudDetector:
    """Advanced fraud detection system"""
    
    def __init__(self):
        self.velocity_rules = self._initialize_velocity_rules()
        self.geo_database = {}  # Would be loaded from GeoIP database
        self.ml_model = None  # Would be loaded from trained model
        
        # Scoring weights
        self.indicator_weights = {
            FraudIndicator.VELOCITY_CHECK: 2.0,
            FraudIndicator.GEO_ANOMALY: 1.5,
            FraudIndicator.BEHAVIORAL_ANOMALY: 1.8,
            FraudIndicator.TRANSACTION_PATTERN: 2.5,
            FraudIndicator.ACCOUNT_TAKEOVER: 3.0,
            FraudIndicator.API_ABUSE: 1.5,
            FraudIndicator.PAYMENT_FRAUD: 3.0,
            FraudIndicator.IDENTITY_FRAUD: 2.8
        }
        
        # Risk thresholds
        self.risk_thresholds = {
            FraudRiskLevel.LOW: 0,
            FraudRiskLevel.MEDIUM: 30,
            FraudRiskLevel.HIGH: 60,
            FraudRiskLevel.CRITICAL: 85
        }
    
    def _initialize_velocity_rules(self) -> Dict[str, VelocityRule]:
        """Initialize velocity check rules"""
        return {
            # Authentication rules
            "login_attempts": VelocityRule(
                name="Login Attempts",
                window_seconds=300,  # 5 minutes
                max_count=5,
                action="block",
                weight=2.0
            ),
            "password_resets": VelocityRule(
                name="Password Resets",
                window_seconds=3600,  # 1 hour
                max_count=3,
                action="flag",
                weight=1.5
            ),
            
            # Transaction rules
            "withdrawals_hourly": VelocityRule(
                name="Hourly Withdrawals",
                window_seconds=3600,
                max_count=3,
                action="block",
                weight=3.0
            ),
            "withdrawals_daily": VelocityRule(
                name="Daily Withdrawals",
                window_seconds=86400,
                max_count=5,
                action="flag",
                weight=2.5
            ),
            "high_value_transactions": VelocityRule(
                name="High Value Transactions",
                window_seconds=3600,
                max_count=2,
                action="flag",
                weight=2.8
            ),
            
            # API usage rules
            "api_key_generation": VelocityRule(
                name="API Key Generation",
                window_seconds=3600,
                max_count=5,
                action="flag",
                weight=1.2
            ),
            "bulk_operations": VelocityRule(
                name="Bulk Operations",
                window_seconds=3600,
                max_count=10,
                action="monitor",
                weight=1.5
            ),
            
            # Account changes
            "email_changes": VelocityRule(
                name="Email Changes",
                window_seconds=86400,
                max_count=2,
                action="flag",
                weight=2.0
            ),
            "payment_method_changes": VelocityRule(
                name="Payment Method Changes",
                window_seconds=3600,
                max_count=3,
                action="flag",
                weight=2.2
            )
        }
    
    async def check_fraud(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        action: str = None,
        amount: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FraudScore:
        """Perform comprehensive fraud check"""
        
        indicators = []
        total_score = 0.0
        
        # Velocity checks
        if action:
            velocity_score, velocity_indicators = await self._check_velocity(
                user_id, ip_address, action, amount
            )
            total_score += velocity_score
            indicators.extend(velocity_indicators)
        
        # Geo-location anomaly detection
        if ip_address and user_id:
            geo_score, geo_indicators = await self._check_geo_anomaly(
                user_id, ip_address
            )
            total_score += geo_score
            indicators.extend(geo_indicators)
        
        # Behavioral analysis
        if user_id:
            behavior_score, behavior_indicators = await self._check_behavioral_anomaly(
                user_id, action, metadata
            )
            total_score += behavior_score
            indicators.extend(behavior_indicators)
        
        # Transaction pattern analysis
        if amount and user_id:
            transaction_score, transaction_indicators = await self._check_transaction_pattern(
                user_id, amount, action
            )
            total_score += transaction_score
            indicators.extend(transaction_indicators)
        
        # Account takeover detection
        if user_id and ip_address:
            ato_score, ato_indicators = await self._check_account_takeover(
                user_id, ip_address, metadata
            )
            total_score += ato_score
            indicators.extend(ato_indicators)
        
        # Calculate final score and risk level
        final_score = min(100, total_score)
        risk_level = self._calculate_risk_level(final_score)
        confidence = self._calculate_confidence(indicators)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_level, indicators)
        
        # Determine actions
        block_transaction = risk_level == FraudRiskLevel.CRITICAL or final_score >= 90
        require_verification = risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]
        
        # Log fraud check
        await self._log_fraud_check(
            user_id, ip_address, action, final_score, risk_level, indicators
        )
        
        return FraudScore(
            score=final_score,
            risk_level=risk_level,
            indicators=indicators,
            confidence=confidence,
            recommendations=recommendations,
            block_transaction=block_transaction,
            require_verification=require_verification
        )
    
    async def _check_velocity(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        action: str,
        amount: Optional[float]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Check velocity rules"""
        
        score = 0.0
        indicators = []
        
        # Map actions to velocity rules
        action_rules = {
            "login": ["login_attempts"],
            "password_reset": ["password_resets"],
            "withdrawal": ["withdrawals_hourly", "withdrawals_daily"],
            "api_key_create": ["api_key_generation"],
            "bulk_operation": ["bulk_operations"],
            "email_change": ["email_changes"],
            "payment_method_change": ["payment_method_changes"]
        }
        
        # Add high value check for transactions
        if amount and amount > 1000:
            if "high_value_transactions" not in action_rules.get(action, []):
                action_rules.setdefault(action, []).append("high_value_transactions")
        
        rules_to_check = action_rules.get(action, [])
        
        for rule_name in rules_to_check:
            rule = self.velocity_rules.get(rule_name)
            if not rule:
                continue
            
            # Create velocity key
            identifiers = []
            if user_id:
                identifiers.append(f"user:{user_id}")
            if ip_address:
                identifiers.append(f"ip:{ip_address}")
            
            for identifier in identifiers:
                key = f"velocity:{rule_name}:{identifier}"
                
                # Count occurrences in window
                current_time = datetime.now().timestamp()
                window_start = current_time - rule.window_seconds
                
                # Use Redis sorted set
                count = await redis_client.zcount(key, window_start, current_time)
                
                # Add current occurrence
                await redis_client.zadd(key, {str(current_time): current_time})
                await redis_client.expire(key, rule.window_seconds + 60)
                
                # Clean old entries
                await redis_client.zremrangebyscore(key, 0, window_start)
                
                if count >= rule.max_count:
                    # Rule violated
                    violation_score = 20 * rule.weight
                    score += violation_score
                    
                    indicators.append({
                        "type": FraudIndicator.VELOCITY_CHECK,
                        "rule": rule_name,
                        "count": count + 1,
                        "limit": rule.max_count,
                        "window": rule.window_seconds,
                        "score": violation_score,
                        "action": rule.action
                    })
        
        return score, indicators
    
    async def _check_geo_anomaly(
        self,
        user_id: str,
        ip_address: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Check for geographical anomalies"""
        
        score = 0.0
        indicators = []
        
        # Get user's location history
        location_key = f"user_locations:{user_id}"
        locations = await redis_client.zrange(location_key, -10, -1, withscores=True)
        
        # Get current location (simplified - would use GeoIP in production)
        current_location = self._get_location_from_ip(ip_address)
        
        if locations and current_location:
            # Check for impossible travel
            last_location, last_time = locations[-1] if locations else (None, None)
            
            if last_location:
                last_loc_data = json.loads(last_location)
                time_diff = datetime.now().timestamp() - last_time
                distance = self._calculate_distance(
                    last_loc_data.get("lat", 0),
                    last_loc_data.get("lon", 0),
                    current_location.get("lat", 0),
                    current_location.get("lon", 0)
                )
                
                # Check if travel is physically impossible (>1000 km/h)
                if time_diff > 0:
                    speed_kmh = (distance / 1000) / (time_diff / 3600)
                    
                    if speed_kmh > 1000:
                        anomaly_score = 30 * self.indicator_weights[FraudIndicator.GEO_ANOMALY]
                        score += anomaly_score
                        
                        indicators.append({
                            "type": FraudIndicator.GEO_ANOMALY,
                            "reason": "impossible_travel",
                            "distance_km": distance / 1000,
                            "time_hours": time_diff / 3600,
                            "speed_kmh": speed_kmh,
                            "score": anomaly_score
                        })
            
            # Check for new country
            user_countries = set()
            for loc, _ in locations:
                loc_data = json.loads(loc)
                user_countries.add(loc_data.get("country", ""))
            
            if current_location.get("country") not in user_countries:
                anomaly_score = 15 * self.indicator_weights[FraudIndicator.GEO_ANOMALY]
                score += anomaly_score
                
                indicators.append({
                    "type": FraudIndicator.GEO_ANOMALY,
                    "reason": "new_country",
                    "country": current_location.get("country"),
                    "score": anomaly_score
                })
        
        # Store current location
        await redis_client.zadd(
            location_key,
            {json.dumps(current_location): datetime.now().timestamp()}
        )
        await redis_client.expire(location_key, 2592000)  # 30 days
        
        return score, indicators
    
    async def _check_behavioral_anomaly(
        self,
        user_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Check for behavioral anomalies"""
        
        score = 0.0
        indicators = []
        
        # Get user's behavioral profile
        profile_key = f"user_behavior:{user_id}"
        profile = await redis_client.hgetall(profile_key)
        
        if not profile:
            # New user, create profile
            profile = await self._create_behavioral_profile(user_id)
        
        # Check time-based anomalies
        current_hour = datetime.now().hour
        usual_hours = json.loads(profile.get("usual_hours", "[]"))
        
        if usual_hours and current_hour not in usual_hours:
            # Activity outside usual hours
            anomaly_score = 10 * self.indicator_weights[FraudIndicator.BEHAVIORAL_ANOMALY]
            score += anomaly_score
            
            indicators.append({
                "type": FraudIndicator.BEHAVIORAL_ANOMALY,
                "reason": "unusual_time",
                "current_hour": current_hour,
                "usual_hours": usual_hours,
                "score": anomaly_score
            })
        
        # Check action frequency anomaly
        action_count_key = f"user_actions:{user_id}:{action}"
        daily_count = await redis_client.incr(action_count_key)
        await redis_client.expire(action_count_key, 86400)
        
        avg_daily_actions = float(profile.get(f"avg_daily_{action}", 0))
        if avg_daily_actions > 0 and daily_count > avg_daily_actions * 3:
            # Significant increase in activity
            anomaly_score = 15 * self.indicator_weights[FraudIndicator.BEHAVIORAL_ANOMALY]
            score += anomaly_score
            
            indicators.append({
                "type": FraudIndicator.BEHAVIORAL_ANOMALY,
                "reason": "unusual_frequency",
                "action": action,
                "current_count": daily_count,
                "average_count": avg_daily_actions,
                "score": anomaly_score
            })
        
        # Update behavioral profile
        await self._update_behavioral_profile(user_id, action, metadata)
        
        return score, indicators
    
    async def _check_transaction_pattern(
        self,
        user_id: str,
        amount: float,
        action: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Check transaction patterns for anomalies"""
        
        score = 0.0
        indicators = []
        
        # Get transaction history
        async with get_db_context() as db:
            # Get recent transactions
            result = await db.execute(text("""
                SELECT 
                    amount,
                    created_at,
                    transaction_type
                FROM transactions
                WHERE user_id = :user_id
                    AND created_at >= NOW() - INTERVAL '30 days'
                ORDER BY created_at DESC
                LIMIT 100
            """), {"user_id": user_id})
            
            transactions = result.fetchall()
            
            if transactions:
                amounts = [t.amount for t in transactions]
                
                # Calculate statistics
                avg_amount = np.mean(amounts)
                std_amount = np.std(amounts)
                max_amount = np.max(amounts)
                
                # Check for amount anomaly
                if std_amount > 0:
                    z_score = abs((amount - avg_amount) / std_amount)
                    
                    if z_score > 3:  # 3 standard deviations
                        anomaly_score = 25 * self.indicator_weights[FraudIndicator.TRANSACTION_PATTERN]
                        score += anomaly_score
                        
                        indicators.append({
                            "type": FraudIndicator.TRANSACTION_PATTERN,
                            "reason": "unusual_amount",
                            "amount": amount,
                            "average": round(avg_amount, 2),
                            "std_dev": round(std_amount, 2),
                            "z_score": round(z_score, 2),
                            "score": anomaly_score
                        })
                
                # Check for sudden increase
                if amount > max_amount * 2:
                    anomaly_score = 20 * self.indicator_weights[FraudIndicator.TRANSACTION_PATTERN]
                    score += anomaly_score
                    
                    indicators.append({
                        "type": FraudIndicator.TRANSACTION_PATTERN,
                        "reason": "sudden_increase",
                        "amount": amount,
                        "previous_max": round(max_amount, 2),
                        "score": anomaly_score
                    })
                
                # Check for structuring (multiple small transactions)
                recent_count = len([t for t in transactions[:10] if t.created_at > datetime.now() - timedelta(hours=1)])
                if recent_count > 5:
                    anomaly_score = 30 * self.indicator_weights[FraudIndicator.TRANSACTION_PATTERN]
                    score += anomaly_score
                    
                    indicators.append({
                        "type": FraudIndicator.TRANSACTION_PATTERN,
                        "reason": "potential_structuring",
                        "recent_transactions": recent_count,
                        "score": anomaly_score
                    })
        
        return score, indicators
    
    async def _check_account_takeover(
        self,
        user_id: str,
        ip_address: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Check for account takeover indicators"""
        
        score = 0.0
        indicators = []
        
        # Check for sudden device change
        device_key = f"user_devices:{user_id}"
        known_devices = await redis_client.smembers(device_key)
        
        current_device = metadata.get("device_fingerprint") if metadata else None
        
        if current_device and known_devices and current_device not in known_devices:
            # New device
            device_score = 15 * self.indicator_weights[FraudIndicator.ACCOUNT_TAKEOVER]
            score += device_score
            
            indicators.append({
                "type": FraudIndicator.ACCOUNT_TAKEOVER,
                "reason": "new_device",
                "device_count": len(known_devices),
                "score": device_score
            })
            
            # Add device to known list
            await redis_client.sadd(device_key, current_device)
            await redis_client.expire(device_key, 2592000)  # 30 days
        
        # Check for password reset followed by unusual activity
        reset_key = f"password_reset:{user_id}"
        last_reset = await redis_client.get(reset_key)
        
        if last_reset:
            reset_time = float(last_reset)
            time_since_reset = datetime.now().timestamp() - reset_time
            
            if time_since_reset < 3600:  # Within 1 hour
                ato_score = 20 * self.indicator_weights[FraudIndicator.ACCOUNT_TAKEOVER]
                score += ato_score
                
                indicators.append({
                    "type": FraudIndicator.ACCOUNT_TAKEOVER,
                    "reason": "recent_password_reset",
                    "minutes_since_reset": int(time_since_reset / 60),
                    "score": ato_score
                })
        
        # Check for multiple failed logins before success
        failed_key = f"failed_logins:{user_id}"
        failed_count = await redis_client.get(failed_key)
        
        if failed_count and int(failed_count) > 3:
            ato_score = 25 * self.indicator_weights[FraudIndicator.ACCOUNT_TAKEOVER]
            score += ato_score
            
            indicators.append({
                "type": FraudIndicator.ACCOUNT_TAKEOVER,
                "reason": "multiple_failed_logins",
                "failed_attempts": int(failed_count),
                "score": ato_score
            })
            
            # Reset counter
            await redis_client.delete(failed_key)
        
        return score, indicators
    
    def _calculate_risk_level(self, score: float) -> FraudRiskLevel:
        """Calculate risk level from score"""
        for level in [FraudRiskLevel.CRITICAL, FraudRiskLevel.HIGH, 
                      FraudRiskLevel.MEDIUM, FraudRiskLevel.LOW]:
            if score >= self.risk_thresholds[level]:
                return level
        return FraudRiskLevel.LOW
    
    def _calculate_confidence(self, indicators: List[Dict[str, Any]]) -> float:
        """Calculate confidence level based on indicators"""
        if not indicators:
            return 0.0
        
        # More indicators = higher confidence
        indicator_count = len(indicators)
        
        # Variety of indicator types = higher confidence
        unique_types = len(set(i["type"] for i in indicators))
        
        # Higher scores = higher confidence
        total_score = sum(i.get("score", 0) for i in indicators)
        
        confidence = min(1.0, (
            (indicator_count / 10) * 0.3 +
            (unique_types / 5) * 0.3 +
            (total_score / 100) * 0.4
        ))
        
        return round(confidence, 2)
    
    def _generate_recommendations(
        self,
        risk_level: FraudRiskLevel,
        indicators: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on risk assessment"""
        recommendations = []
        
        if risk_level == FraudRiskLevel.CRITICAL:
            recommendations.append("Block transaction immediately")
            recommendations.append("Freeze account pending review")
            recommendations.append("Notify security team")
        elif risk_level == FraudRiskLevel.HIGH:
            recommendations.append("Require additional verification")
            recommendations.append("Enable enhanced monitoring")
            recommendations.append("Review recent account activity")
        elif risk_level == FraudRiskLevel.MEDIUM:
            recommendations.append("Send verification email")
            recommendations.append("Monitor next transactions")
        
        # Specific recommendations based on indicators
        indicator_types = [i["type"] for i in indicators]
        
        if FraudIndicator.ACCOUNT_TAKEOVER in indicator_types:
            recommendations.append("Force password reset")
            recommendations.append("Invalidate all sessions")
        
        if FraudIndicator.TRANSACTION_PATTERN in indicator_types:
            recommendations.append("Review transaction history")
            recommendations.append("Set temporary transaction limits")
        
        if FraudIndicator.GEO_ANOMALY in indicator_types:
            recommendations.append("Verify new location")
            recommendations.append("Check for VPN/proxy usage")
        
        return recommendations
    
    async def _log_fraud_check(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        action: str,
        score: float,
        risk_level: FraudRiskLevel,
        indicators: List[Dict[str, Any]]
    ):
        """Log fraud check for analysis"""
        try:
            async with get_db_context() as db:
                await db.execute(text("""
                    INSERT INTO fraud_checks (
                        user_id, ip_address, action, score, risk_level,
                        indicators, created_at
                    ) VALUES (
                        :user_id, :ip_address, :action, :score, :risk_level,
                        :indicators, NOW()
                    )
                """), {
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "action": action,
                    "score": score,
                    "risk_level": risk_level.value,
                    "indicators": json.dumps(indicators)
                })
                await db.commit()
        except Exception as e:
            logger.error(f"Error logging fraud check: {e}")
    
    def _get_location_from_ip(self, ip_address: str) -> Dict[str, Any]:
        """Get location from IP address (simplified)"""
        # In production, would use MaxMind GeoIP or similar
        # For now, return mock data
        return {
            "ip": ip_address,
            "country": "US",
            "city": "New York",
            "lat": 40.7128,
            "lon": -74.0060
        }
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in meters"""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    async def _create_behavioral_profile(self, user_id: str) -> Dict[str, str]:
        """Create initial behavioral profile for user"""
        async with get_db_context() as db:
            # Get user's historical data
            result = await db.execute(text("""
                SELECT 
                    EXTRACT(HOUR FROM created_at) as hour,
                    COUNT(*) as activity_count
                FROM user_activities
                WHERE user_id = :user_id
                    AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY EXTRACT(HOUR FROM created_at)
                ORDER BY activity_count DESC
            """), {"user_id": user_id})
            
            hours = [int(row.hour) for row in result.fetchall()[:5]]  # Top 5 hours
            
            profile = {
                "usual_hours": json.dumps(hours),
                "created_at": str(datetime.now().timestamp())
            }
            
            # Store profile
            profile_key = f"user_behavior:{user_id}"
            await redis_client.hset(profile_key, mapping=profile)
            await redis_client.expire(profile_key, 2592000)  # 30 days
            
            return profile
    
    async def _update_behavioral_profile(
        self,
        user_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """Update user's behavioral profile"""
        # Update action counts
        daily_key = f"user_daily_actions:{user_id}:{action}"
        await redis_client.incr(daily_key)
        await redis_client.expire(daily_key, 86400)
        
        # Update hourly patterns periodically
        update_key = f"profile_update:{user_id}"
        should_update = await redis_client.set(
            update_key, "1", nx=True, ex=3600  # Update hourly
        )
        
        if should_update:
            await self._create_behavioral_profile(user_id)


# Global fraud detector instance
fraud_detector = FraudDetector()