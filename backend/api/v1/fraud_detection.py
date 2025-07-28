"""
Fraud Detection Management API Endpoints

Provides endpoints for:
- Viewing fraud scores and risk assessments
- Managing fraud detection rules
- Reviewing blocked transactions
- Fraud analytics and reporting
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.security.fraud_detector import (
    fraud_detector, FraudRiskLevel, FraudIndicator, 
    FraudScore, VelocityRule
)
from core.security import get_current_user, require_admin
from core.database import get_db
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/fraud-detection")


class FraudCheckRequest(BaseModel):
    """Request for manual fraud check"""
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    action: str
    amount: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class FraudScoreResponse(BaseModel):
    """Fraud score response"""
    score: float
    risk_level: str
    indicators: List[Dict[str, Any]]
    confidence: float
    recommendations: List[str]
    block_transaction: bool
    require_verification: bool


class VelocityRuleResponse(BaseModel):
    """Velocity rule configuration"""
    name: str
    window_seconds: int
    max_count: int
    action: str
    weight: float


class FraudAnalyticsResponse(BaseModel):
    """Fraud analytics summary"""
    total_checks: int
    blocked_transactions: int
    risk_distribution: Dict[str, int]
    top_indicators: List[Dict[str, Any]]
    recent_high_risk: List[Dict[str, Any]]


@router.post("/check", response_model=FraudScoreResponse)
async def manual_fraud_check(
    request: FraudCheckRequest,
    current_user: dict = Depends(require_admin)
):
    """Perform manual fraud check (admin only)"""
    
    try:
        fraud_score = await fraud_detector.check_fraud(
            user_id=request.user_id,
            ip_address=request.ip_address,
            action=request.action,
            amount=request.amount,
            metadata=request.metadata
        )
        
        return FraudScoreResponse(
            score=fraud_score.score,
            risk_level=fraud_score.risk_level.value,
            indicators=fraud_score.indicators,
            confidence=fraud_score.confidence,
            recommendations=fraud_score.recommendations,
            block_transaction=fraud_score.block_transaction,
            require_verification=fraud_score.require_verification
        )
        
    except Exception as e:
        logger.error(f"Manual fraud check error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to perform fraud check"
        )


@router.get("/my-score")
async def get_my_fraud_score(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's fraud risk profile"""
    
    user_id = current_user["user_id"]
    
    try:
        # Get recent fraud checks for user
        result = await db.execute(text("""
            SELECT 
                score,
                risk_level,
                indicators,
                created_at
            FROM fraud_checks
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 10
        """), {"user_id": user_id})
        
        recent_checks = []
        for row in result:
            recent_checks.append({
                "score": row.score,
                "risk_level": row.risk_level,
                "indicators": row.indicators,
                "timestamp": row.created_at.isoformat()
            })
        
        # Calculate average score
        if recent_checks:
            avg_score = sum(c["score"] for c in recent_checks) / len(recent_checks)
            current_risk = fraud_detector._calculate_risk_level(avg_score).value
        else:
            avg_score = 0
            current_risk = FraudRiskLevel.LOW.value
        
        return {
            "user_id": user_id,
            "current_risk_level": current_risk,
            "average_score": round(avg_score, 2),
            "recent_checks": recent_checks
        }
        
    except Exception as e:
        logger.error(f"Error getting user fraud score: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve fraud score"
        )


@router.get("/velocity-rules", response_model=List[VelocityRuleResponse])
async def get_velocity_rules(
    current_user: dict = Depends(require_admin)
):
    """Get all velocity rules (admin only)"""
    
    rules = []
    for name, rule in fraud_detector.velocity_rules.items():
        rules.append(VelocityRuleResponse(
            name=rule.name,
            window_seconds=rule.window_seconds,
            max_count=rule.max_count,
            action=rule.action,
            weight=rule.weight
        ))
    
    return rules


@router.get("/blocked-transactions")
async def get_blocked_transactions(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    risk_level: Optional[FraudRiskLevel] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get recently blocked transactions (admin only)"""
    
    try:
        # Build query
        query_parts = ["score >= 90"]  # Blocked threshold
        params = {"limit": limit}
        
        if start_date:
            query_parts.append("created_at >= :start_date")
            params["start_date"] = start_date
        else:
            # Default to last 7 days
            query_parts.append("created_at >= :start_date")
            params["start_date"] = datetime.now() - timedelta(days=7)
        
        if end_date:
            query_parts.append("created_at <= :end_date")
            params["end_date"] = end_date
        
        if risk_level:
            query_parts.append("risk_level = :risk_level")
            params["risk_level"] = risk_level.value
        
        where_clause = " AND ".join(query_parts)
        
        result = await db.execute(text(f"""
            SELECT 
                fc.id,
                fc.user_id,
                fc.ip_address,
                fc.action,
                fc.score,
                fc.risk_level,
                fc.indicators,
                fc.created_at,
                u.email as user_email
            FROM fraud_checks fc
            LEFT JOIN users u ON fc.user_id = u.id::text
            WHERE {where_clause}
            ORDER BY fc.created_at DESC
            LIMIT :limit
        """), params)
        
        blocked = []
        for row in result:
            blocked.append({
                "id": row.id,
                "user_id": row.user_id,
                "user_email": row.user_email,
                "ip_address": row.ip_address,
                "action": row.action,
                "score": row.score,
                "risk_level": row.risk_level,
                "indicators": row.indicators,
                "timestamp": row.created_at.isoformat()
            })
        
        return {
            "total": len(blocked),
            "blocked_transactions": blocked
        }
        
    except Exception as e:
        logger.error(f"Error getting blocked transactions: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve blocked transactions"
        )


@router.get("/analytics", response_model=FraudAnalyticsResponse)
async def get_fraud_analytics(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get fraud detection analytics (admin only)"""
    
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # Get total checks and blocks
        result = await db.execute(text("""
            SELECT 
                COUNT(*) as total_checks,
                COUNT(CASE WHEN score >= 90 THEN 1 END) as blocked_count,
                COUNT(CASE WHEN risk_level = 'low' THEN 1 END) as low_risk,
                COUNT(CASE WHEN risk_level = 'medium' THEN 1 END) as medium_risk,
                COUNT(CASE WHEN risk_level = 'high' THEN 1 END) as high_risk,
                COUNT(CASE WHEN risk_level = 'critical' THEN 1 END) as critical_risk
            FROM fraud_checks
            WHERE created_at >= :start_date
        """), {"start_date": start_date})
        
        stats = result.fetchone()
        
        # Get top fraud indicators
        result = await db.execute(text("""
            SELECT 
                jsonb_array_elements(indicators)->>'type' as indicator_type,
                COUNT(*) as count,
                AVG((jsonb_array_elements(indicators)->>'score')::float) as avg_score
            FROM fraud_checks
            WHERE created_at >= :start_date
                AND jsonb_array_length(indicators) > 0
            GROUP BY indicator_type
            ORDER BY count DESC
            LIMIT 10
        """), {"start_date": start_date})
        
        top_indicators = []
        for row in result:
            top_indicators.append({
                "type": row.indicator_type,
                "count": row.count,
                "average_score": round(row.avg_score, 2) if row.avg_score else 0
            })
        
        # Get recent high risk activities
        result = await db.execute(text("""
            SELECT 
                fc.user_id,
                fc.action,
                fc.score,
                fc.risk_level,
                fc.created_at,
                u.email as user_email
            FROM fraud_checks fc
            LEFT JOIN users u ON fc.user_id = u.id::text
            WHERE fc.created_at >= :start_date
                AND fc.risk_level IN ('high', 'critical')
            ORDER BY fc.created_at DESC
            LIMIT 20
        """), {"start_date": start_date})
        
        recent_high_risk = []
        for row in result:
            recent_high_risk.append({
                "user_id": row.user_id,
                "user_email": row.user_email,
                "action": row.action,
                "score": row.score,
                "risk_level": row.risk_level,
                "timestamp": row.created_at.isoformat()
            })
        
        return FraudAnalyticsResponse(
            total_checks=stats.total_checks,
            blocked_transactions=stats.blocked_count,
            risk_distribution={
                "low": stats.low_risk,
                "medium": stats.medium_risk,
                "high": stats.high_risk,
                "critical": stats.critical_risk
            },
            top_indicators=top_indicators,
            recent_high_risk=recent_high_risk
        )
        
    except Exception as e:
        logger.error(f"Error getting fraud analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve fraud analytics"
        )


@router.post("/whitelist/{user_id}")
async def whitelist_user(
    user_id: str = Path(..., description="User ID to whitelist"),
    duration_hours: int = Query(24, ge=1, le=168),
    reason: str = Query(..., description="Reason for whitelisting"),
    current_user: dict = Depends(require_admin)
):
    """Temporarily whitelist a user from fraud checks (admin only)"""
    
    try:
        from core.redis import redis_client
        
        # Add to whitelist
        whitelist_key = f"fraud_whitelist:{user_id}"
        await redis_client.setex(
            whitelist_key,
            duration_hours * 3600,
            json.dumps({
                "admin_id": current_user["user_id"],
                "reason": reason,
                "expires_at": (datetime.now() + timedelta(hours=duration_hours)).isoformat()
            })
        )
        
        logger.info(
            f"User {user_id} whitelisted by {current_user['email']} "
            f"for {duration_hours} hours. Reason: {reason}"
        )
        
        return {
            "message": "User whitelisted successfully",
            "user_id": user_id,
            "duration_hours": duration_hours,
            "expires_at": (datetime.now() + timedelta(hours=duration_hours)).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error whitelisting user: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to whitelist user"
        )


@router.delete("/whitelist/{user_id}")
async def remove_whitelist(
    user_id: str = Path(..., description="User ID to remove from whitelist"),
    current_user: dict = Depends(require_admin)
):
    """Remove user from whitelist (admin only)"""
    
    try:
        from core.redis import redis_client
        
        whitelist_key = f"fraud_whitelist:{user_id}"
        removed = await redis_client.delete(whitelist_key)
        
        if removed:
            logger.info(f"User {user_id} removed from whitelist by {current_user['email']}")
            return {"message": "User removed from whitelist"}
        else:
            raise HTTPException(
                status_code=404,
                detail="User not found in whitelist"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing whitelist: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to remove whitelist"
        )