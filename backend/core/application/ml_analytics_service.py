"""ML Analytics service for anomaly detection and predictive analytics."""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime, timedelta, date
from decimal import Decimal
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import json
import hashlib
from collections import defaultdict

from models.user import User
from models.agency import Agency
from models.financial import Transaction
from models.chat import Conversation, Message
from models.model import Model
from core.redis import redis_manager
from core.exceptions import ValidationError, NotFoundError


class MLAnalyticsService:
    """Service for ML-based analytics and anomaly detection."""
    
    # Model cache TTL (1 hour)
    MODEL_CACHE_TTL = 3600
    
    # Anomaly detection thresholds
    CONTAMINATION_RATE = 0.01  # Expected 1% anomaly rate
    VELOCITY_SPIKE_THRESHOLD = 3.0  # 3x normal rate
    
    @staticmethod
    async def train_anomaly_model(
        db: AsyncSession,
        model_type: str = "transaction",
        lookback_days: int = 90,
        contamination: float = 0.01
    ) -> Dict[str, Any]:
        """Train anomaly detection model."""
        # Get training data based on model type
        if model_type == "transaction":
            features, ids = await MLAnalyticsService._get_transaction_features(
                db, lookback_days
            )
        elif model_type == "behavior":
            features, ids = await MLAnalyticsService._get_behavior_features(
                db, lookback_days
            )
        else:
            raise ValidationError(f"Unknown model type: {model_type}")
        
        if len(features) < 100:
            return {
                "status": "insufficient_data",
                "message": f"Need at least 100 samples, found {len(features)}",
                "model_type": model_type
            }
        
        # Scale features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        # Train Isolation Forest
        model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        model.fit(scaled_features)
        
        # Calculate model metrics
        predictions = model.predict(scaled_features)
        anomaly_scores = model.score_samples(scaled_features)
        
        n_anomalies = sum(1 for p in predictions if p == -1)
        
        # Cache model (in production, use model serialization)
        model_data = {
            "type": model_type,
            "trained_at": datetime.utcnow().isoformat(),
            "lookback_days": lookback_days,
            "contamination": contamination,
            "n_samples": len(features),
            "n_anomalies": n_anomalies,
            "feature_means": scaler.mean_.tolist(),
            "feature_stds": scaler.scale_.tolist()
        }
        
        await redis_manager.set(
            f"ml_model:{model_type}",
            model_data,
            expire=MLAnalyticsService.MODEL_CACHE_TTL
        )
        
        return {
            "status": "success",
            "model_type": model_type,
            "trained_at": model_data["trained_at"],
            "metrics": {
                "samples_used": len(features),
                "anomalies_detected": n_anomalies,
                "anomaly_rate": n_anomalies / len(features),
                "lookback_days": lookback_days
            }
        }
    
    @staticmethod
    async def detect_anomalies(
        db: AsyncSession,
        time_window_hours: int = 24,
        anomaly_types: Optional[List[str]] = None,
        min_severity: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in recent data."""
        if not anomaly_types:
            anomaly_types = ["transaction", "behavior", "velocity"]
        
        anomalies = []
        since = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # Detect transaction anomalies
        if "transaction" in anomaly_types:
            trans_anomalies = await MLAnalyticsService._detect_transaction_anomalies(
                db, since, min_severity
            )
            anomalies.extend(trans_anomalies)
        
        # Detect behavior anomalies
        if "behavior" in anomaly_types:
            behavior_anomalies = await MLAnalyticsService._detect_behavior_anomalies(
                db, since, min_severity
            )
            anomalies.extend(behavior_anomalies)
        
        # Detect velocity anomalies
        if "velocity" in anomaly_types:
            velocity_anomalies = await MLAnalyticsService._detect_velocity_anomalies(
                db, since, min_severity
            )
            anomalies.extend(velocity_anomalies)
        
        # Sort by severity
        anomalies.sort(key=lambda x: x["severity_score"], reverse=True)
        
        return anomalies
    
    @staticmethod
    async def get_risk_scores(
        db: AsyncSession,
        entity_type: str = "fan",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get risk scores for entities."""
        if entity_type == "fan":
            return await MLAnalyticsService._get_fan_risk_scores(db, limit)
        elif entity_type == "model":
            return await MLAnalyticsService._get_model_risk_scores(db, limit)
        else:
            raise ValidationError(f"Unknown entity type: {entity_type}")
    
    @staticmethod
    async def analyze_entity(
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze specific entity for anomalies."""
        since = datetime.utcnow() - timedelta(days=lookback_days)
        
        if entity_type == "fan":
            return await MLAnalyticsService._analyze_fan(db, entity_id, since)
        elif entity_type == "model":
            return await MLAnalyticsService._analyze_model(db, entity_id, since)
        else:
            raise ValidationError(f"Unknown entity type: {entity_type}")
    
    @staticmethod
    async def get_conversation_insights(
        db: AsyncSession,
        conversation_id: int,
        include_sentiment: bool = True
    ) -> Dict[str, Any]:
        """Extract insights from conversation using ML."""
        # Get conversation messages
        messages = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = messages.scalars().all()
        
        if not messages:
            raise NotFoundError("Conversation not found or has no messages")
        
        # Extract text features
        message_texts = [m.content for m in messages if m.content]
        
        # Calculate basic metrics
        total_messages = len(messages)
        avg_message_length = np.mean([len(m.content or "") for m in messages])
        response_times = []
        
        for i in range(1, len(messages)):
            if messages[i].sender_id != messages[i-1].sender_id:
                time_diff = (messages[i].created_at - messages[i-1].created_at).total_seconds()
                response_times.append(time_diff)
        
        avg_response_time = np.mean(response_times) if response_times else 0
        
        # Topic extraction (simplified - in production use proper NLP)
        topics = MLAnalyticsService._extract_topics(message_texts)
        
        # Sentiment analysis (simplified)
        sentiment_scores = []
        if include_sentiment:
            for text in message_texts:
                sentiment_scores.append(MLAnalyticsService._analyze_sentiment(text))
        
        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0
        
        # Engagement metrics
        engagement_score = MLAnalyticsService._calculate_engagement_score(
            total_messages,
            avg_response_time,
            avg_message_length
        )
        
        return {
            "conversation_id": conversation_id,
            "total_messages": total_messages,
            "avg_message_length": round(avg_message_length, 2),
            "avg_response_time_seconds": round(avg_response_time, 2),
            "topics": topics[:5],  # Top 5 topics
            "sentiment": {
                "average": round(avg_sentiment, 2),
                "trend": "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
            },
            "engagement_score": round(engagement_score, 2),
            "insights": MLAnalyticsService._generate_conversation_insights(
                engagement_score, avg_sentiment, topics
            )
        }
    
    @staticmethod
    async def predict_churn_risk(
        db: AsyncSession,
        fan_id: int
    ) -> Dict[str, Any]:
        """Predict fan churn risk."""
        # Get fan activity data
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        
        # Recent transactions
        recent_trans = await db.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= thirty_days_ago
                )
            )
        )
        recent_count, recent_amount = recent_trans.one()
        
        # Previous period transactions
        prev_trans = await db.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= sixty_days_ago,
                    Transaction.created_at < thirty_days_ago
                )
            )
        )
        prev_count, prev_amount = prev_trans.one()
        
        # Calculate trends
        transaction_trend = (recent_count - prev_count) / max(prev_count, 1)
        amount_trend = (float(recent_amount or 0) - float(prev_amount or 0)) / max(float(prev_amount or 1), 1)
        
        # Risk factors
        risk_factors = []
        risk_score = 0
        
        # No recent activity
        if recent_count == 0:
            risk_factors.append("No transactions in last 30 days")
            risk_score += 40
        
        # Declining activity
        if transaction_trend < -0.5:
            risk_factors.append(f"Transaction frequency declined by {abs(transaction_trend)*100:.0f}%")
            risk_score += 30
        
        # Declining spend
        if amount_trend < -0.5:
            risk_factors.append(f"Spending declined by {abs(amount_trend)*100:.0f}%")
            risk_score += 20
        
        # Low engagement (simplified)
        if recent_count < 2:
            risk_factors.append("Low engagement level")
            risk_score += 10
        
        # Determine risk level
        if risk_score >= 60:
            risk_level = "high"
            recommendation = "Immediate re-engagement campaign recommended"
        elif risk_score >= 30:
            risk_level = "medium"
            recommendation = "Monitor closely and consider targeted offers"
        else:
            risk_level = "low"
            recommendation = "Continue normal engagement"
        
        return {
            "fan_id": fan_id,
            "churn_risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "metrics": {
                "recent_transactions": recent_count or 0,
                "recent_spend": float(recent_amount or 0),
                "transaction_trend": round(transaction_trend * 100, 2),
                "amount_trend": round(amount_trend * 100, 2)
            },
            "recommendation": recommendation,
            "predicted_churn_probability": risk_score / 100
        }
    
    @staticmethod
    async def _get_transaction_features(
        db: AsyncSession,
        lookback_days: int
    ) -> Tuple[np.ndarray, List[int]]:
        """Extract transaction features for anomaly detection."""
        since = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get transactions with aggregated features
        query = text("""
            SELECT 
                t.id,
                t.gross_amount as amount,
                t.fan_id,
                COUNT(*) OVER (PARTITION BY t.fan_id ORDER BY t.created_at 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as recent_trans_count,
                AVG(t.gross_amount) OVER (PARTITION BY t.fan_id ORDER BY t.created_at 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as recent_avg_amount,
                EXTRACT(HOUR FROM t.created_at) as hour_of_day,
                EXTRACT(DOW FROM t.created_at) as day_of_week
            FROM transactions t
            WHERE t.created_at >= :since
            ORDER BY t.created_at
        """)
        
        result = await db.execute(query, {"since": since})
        rows = result.fetchall()
        
        if not rows:
            return np.array([]), []
        
        features = []
        ids = []
        
        for row in rows:
            features.append([
                float(row[1]),  # amount
                row[3],  # recent_trans_count
                float(row[4]),  # recent_avg_amount
                row[5],  # hour_of_day
                row[6]   # day_of_week
            ])
            ids.append(row[0])
        
        return np.array(features), ids
    
    @staticmethod
    async def _get_behavior_features(
        db: AsyncSession,
        lookback_days: int
    ) -> Tuple[np.ndarray, List[int]]:
        """Extract behavior features for anomaly detection."""
        since = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get aggregated behavior data by fan
        # Since we don't have a proper fan/subscriber table, aggregate from transactions
        query = text("""
            SELECT 
                t.fan_id as fan_id,
                COUNT(DISTINCT t.id) as transaction_count,
                COALESCE(AVG(t.gross_amount), 0) as avg_transaction_amount,
                COUNT(DISTINCT DATE(t.created_at)) as active_days,
                0 as message_count,
                MAX(t.created_at) as last_transaction_date
            FROM transactions t
            WHERE t.created_at >= :since
            GROUP BY t.fan_id
            HAVING COUNT(t.id) > 0
        """)
        
        result = await db.execute(query, {"since": since})
        rows = result.fetchall()
        
        if not rows:
            return np.array([]), []
        
        features = []
        ids = []
        
        for row in rows:
            days_since_last = (datetime.utcnow() - row[5]).days if row[5] else lookback_days
            
            features.append([
                row[1],  # transaction_count
                float(row[2]),  # avg_transaction_amount
                row[3],  # active_days
                row[4],  # message_count
                days_since_last  # days_since_last_transaction
            ])
            ids.append(row[0])
        
        return np.array(features), ids
    
    @staticmethod
    async def _detect_transaction_anomalies(
        db: AsyncSession,
        since: datetime,
        min_severity: float
    ) -> List[Dict[str, Any]]:
        """Detect transaction anomalies."""
        anomalies = []
        
        # Get recent transactions
        transactions = await db.execute(
            select(Transaction)
            .where(Transaction.created_at >= since)
            .order_by(Transaction.created_at.desc())
            .limit(1000)
        )
        transactions = transactions.scalars().all()
        
        for trans in transactions:
            # Check for amount anomalies
            severity_score = 0
            reasons = []
            
            # Very high amount
            if trans.gross_amount > 500:
                severity_score = 8.5
                reasons.append(f"Unusually high amount: ${trans.gross_amount}")
            elif trans.gross_amount > 200:
                severity_score = 6.0
                reasons.append(f"High amount: ${trans.gross_amount}")
            
            if severity_score >= min_severity:
                anomalies.append({
                    "type": "transaction_anomaly",
                    "entity_type": "transaction",
                    "entity_id": str(trans.id),
                    "detected_at": datetime.utcnow().isoformat(),
                    "severity_score": severity_score,
                    "details": {
                        "amount": float(trans.gross_amount),
                        "fan_id": trans.fan_id,
                        "anomaly_score": -0.85  # Mock score
                    },
                    "reasons": reasons,
                    "recommended_actions": [
                        "Review transaction details",
                        "Check fan transaction history",
                        "Verify payment method"
                    ]
                })
        
        return anomalies
    
    @staticmethod
    async def _detect_behavior_anomalies(
        db: AsyncSession,
        since: datetime,
        min_severity: float
    ) -> List[Dict[str, Any]]:
        """Detect behavior anomalies."""
        # Simplified implementation
        return []
    
    @staticmethod
    async def _detect_velocity_anomalies(
        db: AsyncSession,
        since: datetime,
        min_severity: float
    ) -> List[Dict[str, Any]]:
        """Detect velocity (rate) anomalies."""
        anomalies = []
        
        # Check for transaction velocity spikes
        query = text("""
            WITH hourly_counts AS (
                SELECT 
                    fan_id,
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as trans_count
                FROM transactions
                WHERE created_at >= :since
                GROUP BY fan_id, DATE_TRUNC('hour', created_at)
            ),
            avg_rates AS (
                SELECT 
                    fan_id,
                    AVG(trans_count) as avg_rate,
                    MAX(trans_count) as max_rate
                FROM hourly_counts
                GROUP BY fan_id
            )
            SELECT 
                h.fan_id,
                h.hour,
                h.trans_count,
                a.avg_rate
            FROM hourly_counts h
            JOIN avg_rates a ON h.fan_id = a.fan_id
            WHERE h.trans_count > a.avg_rate * :threshold
                AND h.trans_count >= 5
            ORDER BY h.trans_count DESC
            LIMIT 10
        """)
        
        result = await db.execute(
            query, 
            {"since": since, "threshold": MLAnalyticsService.VELOCITY_SPIKE_THRESHOLD}
        )
        rows = result.fetchall()
        
        for row in rows:
            spike_ratio = row[2] / row[3] if row[3] > 0 else 0
            severity_score = min(spike_ratio * 3, 10)  # Scale to 0-10
            
            if severity_score >= min_severity:
                anomalies.append({
                    "type": "velocity_anomaly",
                    "entity_type": "fan",
                    "entity_id": str(row[0]),
                    "detected_at": datetime.utcnow().isoformat(),
                    "severity_score": round(severity_score, 1),
                    "details": {
                        "spike_hour": row[1].isoformat(),
                        "transaction_count": row[2],
                        "normal_rate": round(row[3], 2),
                        "spike_ratio": round(spike_ratio, 2)
                    },
                    "reasons": [
                        f"Transaction rate {spike_ratio:.1f}x normal"
                    ],
                    "recommended_actions": [
                        "Investigate transaction burst",
                        "Check for automated activity",
                        "Review transaction details"
                    ]
                })
        
        return anomalies
    
    @staticmethod
    async def _get_fan_risk_scores(
        db: AsyncSession,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Calculate risk scores for fans."""
        # Get fans with risk indicators
        # Since fan_id in transactions is a string and we don't have a proper fan/subscriber table,
        # we'll aggregate by fan_id directly from transactions
        query = text("""
            WITH fan_metrics AS (
                SELECT 
                    t.fan_id as id,
                    t.fan_username as username,
                    COUNT(t.id) as transaction_count,
                    COALESCE(SUM(t.gross_amount), 0) as total_spent,
                    COALESCE(AVG(t.gross_amount), 0) as avg_amount,
                    MAX(t.created_at) as last_activity
                FROM transactions t
                GROUP BY t.fan_id, t.fan_username
            )
            SELECT *
            FROM fan_metrics
            WHERE transaction_count > 0
            ORDER BY total_spent DESC
            LIMIT :limit
        """)
        
        result = await db.execute(query, {"limit": limit})
        rows = result.fetchall()
        
        risk_scores = []
        for row in rows:
            risk_score = 0
            risk_factors = []
            
            # High average transaction
            if row[4] > 100:
                risk_score += 25
                risk_factors.append("High average transaction amount")
            
            # High total spend
            if row[3] > 1000:
                risk_score += 25
                risk_factors.append("High total spending")
            
            # Recent high activity (mock)
            if row[2] > 20:
                risk_score += 25
                risk_factors.append("High recent activity")
            
            risk_scores.append({
                "fan_id": row[0],
                "username": row[1],
                "risk_score": min(risk_score, 100),
                "transaction_count": row[2],
                "total_spent": float(row[3]),
                "risk_factors": risk_factors,
                "last_activity": row[5].isoformat() if row[5] else None
            })
        
        return risk_scores
    
    @staticmethod
    async def _get_model_risk_scores(
        db: AsyncSession,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Calculate risk scores for models."""
        # Simplified implementation
        return []
    
    @staticmethod
    async def _analyze_fan(
        db: AsyncSession,
        fan_id: int,
        since: datetime
    ) -> Dict[str, Any]:
        """Analyze specific fan for anomalies."""
        # Get fan transactions
        transactions = await db.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.fan_id == fan_id,
                    Transaction.created_at >= since
                )
            )
            .order_by(Transaction.created_at)
        )
        transactions = transactions.scalars().all()
        
        if not transactions:
            raise NotFoundError("No transactions found for fan")
        
        # Calculate statistics
        amounts = [float(t.amount) for t in transactions]
        avg_amount = np.mean(amounts)
        std_amount = np.std(amounts)
        
        # Find anomalies
        anomalies = []
        for i, trans in enumerate(transactions):
            z_score = (float(trans.amount) - avg_amount) / std_amount if std_amount > 0 else 0
            if abs(z_score) > 3:
                anomalies.append({
                    "type": "amount_anomaly",
                    "transaction_index": i,
                    "amount": float(trans.amount),
                    "z_score": round(z_score, 2)
                })
        
        # Risk assessment
        risk_score = min(len(anomalies) * 15, 100)
        risk_factors = []
        
        if len(anomalies) > 0:
            risk_factors.append("Unusual transaction amounts")
        
        if len(transactions) > 10:
            risk_factors.append("High transaction volume")
        
        return {
            "fan_id": fan_id,
            "risk_score": risk_score,
            "anomaly_count": len(anomalies),
            "total_transactions": len(transactions),
            "total_spent": sum(amounts),
            "avg_transaction_amount": round(avg_amount, 2),
            "anomalies": anomalies[:5],  # Top 5
            "risk_factors": risk_factors,
            "recommendation": "Monitor closely" if risk_score > 40 else "Normal activity"
        }
    
    @staticmethod
    async def _analyze_model(
        db: AsyncSession,
        model_id: int,
        since: datetime
    ) -> Dict[str, Any]:
        """Analyze specific model for anomalies."""
        # Simplified implementation
        return {
            "model_id": model_id,
            "risk_score": 0,
            "anomaly_count": 0,
            "recommendation": "Normal activity"
        }
    
    @staticmethod
    def _extract_topics(texts: List[str]) -> List[str]:
        """Extract topics from texts (simplified)."""
        # In production, use proper NLP (TF-IDF, LDA, etc.)
        word_freq = defaultdict(int)
        
        for text in texts:
            words = text.lower().split()
            for word in words:
                if len(word) > 4:  # Filter short words
                    word_freq[word] += 1
        
        # Get top words as topics
        topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in topics[:10]]
    
    @staticmethod
    def _analyze_sentiment(text: str) -> float:
        """Analyze sentiment of text (simplified)."""
        # In production, use proper sentiment analysis
        positive_words = ["love", "great", "amazing", "wonderful", "excellent", "happy"]
        negative_words = ["hate", "bad", "terrible", "awful", "horrible", "sad"]
        
        text_lower = text.lower()
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count)
    
    @staticmethod
    def _calculate_engagement_score(
        message_count: int,
        avg_response_time: float,
        avg_message_length: float
    ) -> float:
        """Calculate engagement score (0-100)."""
        # Normalize metrics
        message_score = min(message_count / 50, 1) * 30  # Max 30 points
        response_score = max(0, 1 - avg_response_time / 3600) * 30  # Max 30 points
        length_score = min(avg_message_length / 100, 1) * 40  # Max 40 points
        
        return message_score + response_score + length_score
    
    @staticmethod
    def _generate_conversation_insights(
        engagement_score: float,
        sentiment: float,
        topics: List[str]
    ) -> List[str]:
        """Generate insights based on conversation analysis."""
        insights = []
        
        if engagement_score > 70:
            insights.append("High engagement level - conversation is very active")
        elif engagement_score < 30:
            insights.append("Low engagement - consider strategies to increase interaction")
        
        if sentiment > 0.5:
            insights.append("Very positive sentiment throughout conversation")
        elif sentiment < -0.5:
            insights.append("Negative sentiment detected - may need attention")
        
        if topics:
            insights.append(f"Main topics discussed: {', '.join(topics[:3])}")
        
        return insights