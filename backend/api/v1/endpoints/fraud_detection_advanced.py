"""
Fraud detection management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from core.domain.models import User, UserRole
from core.fraud_detection.models import (
    FraudRule, FraudScore, FraudEvent, FraudPattern,
    VelocityCheck, ReviewQueue, FraudWhitelist,
    RiskLevel, FraudType, ActionType
)
from core.fraud_detection.fraud_detector import fraud_detector
from core.domain.schemas import BaseResponse

router = APIRouter(prefix="/fraud-detection", tags=["fraud-detection"])


# Schemas
class FraudRuleCreate(BaseModel):
    """Create a new fraud rule."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    rule_type: str = Field(..., description="velocity, pattern, anomaly, etc.")
    fraud_type: FraudType
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    threshold_value: Optional[float] = None
    time_window_seconds: Optional[int] = None
    risk_score: int = Field(..., ge=0, le=100)
    auto_action: Optional[ActionType] = None
    notification_enabled: bool = True


class FraudPatternCreate(BaseModel):
    """Create a fraud pattern."""
    name: str = Field(..., min_length=1, max_length=100)
    pattern_type: str = Field(..., description="behavioral, transactional, etc.")
    fraud_type: FraudType
    pattern_data: Dict[str, Any] = Field(..., description="Pattern matching rules")
    confidence_threshold: float = Field(0.8, ge=0, le=1)
    risk_score: int = Field(..., ge=0, le=100)
    auto_block: bool = False


class VelocityCheckCreate(BaseModel):
    """Create a velocity check."""
    name: str = Field(..., min_length=1, max_length=100)
    check_type: str = Field(..., description="transaction_count, amount_sum, etc.")
    entity_type: str = Field(..., description="user, ip, card, etc.")
    time_window_seconds: int = Field(..., gt=0)
    max_count: Optional[int] = None
    max_amount: Optional[float] = None
    unique_constraint: Optional[str] = None
    risk_score: int = Field(..., ge=0, le=100)
    auto_action: Optional[ActionType] = None


class WhitelistCreate(BaseModel):
    """Add entity to whitelist."""
    entity_type: str = Field(..., description="user, ip, etc.")
    entity_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    whitelist_level: str = Field("full", description="full or partial")
    skip_checks: Optional[List[str]] = None
    valid_days: int = Field(30, ge=1, le=365)


class ReviewResolution(BaseModel):
    """Resolve a review queue item."""
    resolution: str = Field(..., description="approved, blocked, false_positive")
    resolution_notes: str = Field(..., min_length=1)


class ManualFraudCheck(BaseModel):
    """Manual fraud check request."""
    transaction_data: Dict[str, Any]
    user_id: UUID
    ip_address: Optional[str] = None


# Endpoints

@router.get("/dashboard")
async def get_fraud_dashboard(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get fraud detection dashboard data."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    # Get fraud event statistics
    event_stats = await db.execute(
        select(
            FraudEvent.risk_level,
            func.count(FraudEvent.id).label("count")
        )
        .where(FraudEvent.detected_at >= since)
        .group_by(FraudEvent.risk_level)
    )
    
    risk_distribution = {
        level.value: 0 for level in RiskLevel
    }
    for row in event_stats:
        risk_distribution[row.risk_level.value] = row.count
    
    # Get blocked transactions
    blocked_result = await db.execute(
        select(func.count(FraudEvent.id))
        .where(
            and_(
                FraudEvent.detected_at >= since,
                FraudEvent.blocked == True
            )
        )
    )
    blocked_count = blocked_result.scalar() or 0
    
    # Get review queue size
    queue_result = await db.execute(
        select(func.count(ReviewQueue.id))
        .where(ReviewQueue.status == "pending")
    )
    queue_size = queue_result.scalar() or 0
    
    # Get top fraud types
    fraud_types = await db.execute(
        select(
            FraudEvent.fraud_type,
            func.count(FraudEvent.id).label("count")
        )
        .where(FraudEvent.detected_at >= since)
        .group_by(FraudEvent.fraud_type)
        .order_by(func.count(FraudEvent.id).desc())
        .limit(5)
    )
    
    top_fraud_types = [
        {"type": row.fraud_type.value if row.fraud_type else "unknown", "count": row.count}
        for row in fraud_types
    ]
    
    return {
        "risk_distribution": risk_distribution,
        "blocked_transactions": blocked_count,
        "review_queue_size": queue_size,
        "top_fraud_types": top_fraud_types,
        "time_range_hours": hours
    }


@router.post("/rules", response_model=BaseResponse)
async def create_fraud_rule(
    rule: FraudRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Create a new fraud detection rule."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can create fraud rules")
    
    # Check if rule name exists
    existing = await db.execute(
        select(FraudRule).where(FraudRule.name == rule.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Rule name already exists")
    
    # Create rule
    new_rule = FraudRule(
        **rule.dict(),
        created_by_id=current_user.id
    )
    
    db.add(new_rule)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message=f"Fraud rule '{rule.name}' created successfully"
    )


@router.get("/rules")
async def get_fraud_rules(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get fraud detection rules."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = select(FraudRule)
    if active_only:
        query = query.where(FraudRule.is_active == True)
    
    result = await db.execute(query.order_by(FraudRule.priority.desc()))
    rules = result.scalars().all()
    
    return [
        {
            "id": str(rule.id),
            "name": rule.name,
            "description": rule.description,
            "rule_type": rule.rule_type,
            "fraud_type": rule.fraud_type.value,
            "risk_score": rule.risk_score,
            "auto_action": rule.auto_action.value if rule.auto_action else None,
            "is_active": rule.is_active,
            "priority": rule.priority
        }
        for rule in rules
    ]


@router.post("/patterns", response_model=BaseResponse)
async def create_fraud_pattern(
    pattern: FraudPatternCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Create a new fraud pattern."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can create fraud patterns")
    
    new_pattern = FraudPattern(**pattern.dict())
    db.add(new_pattern)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message=f"Fraud pattern '{pattern.name}' created successfully"
    )


@router.post("/velocity-checks", response_model=BaseResponse)
async def create_velocity_check(
    check: VelocityCheckCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Create a new velocity check."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can create velocity checks")
    
    new_check = VelocityCheck(**check.dict())
    db.add(new_check)
    await db.commit()
    
    return BaseResponse(
        success=True,
        message=f"Velocity check '{check.name}' created successfully"
    )


@router.get("/events")
async def get_fraud_events(
    user_id: Optional[UUID] = None,
    risk_level: Optional[RiskLevel] = None,
    fraud_type: Optional[FraudType] = None,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get recent fraud events."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = select(FraudEvent).where(FraudEvent.detected_at >= since)
    
    if user_id:
        query = query.where(FraudEvent.user_id == user_id)
    if risk_level:
        query = query.where(FraudEvent.risk_level == risk_level)
    if fraud_type:
        query = query.where(FraudEvent.fraud_type == fraud_type)
    
    # Agency filtering for non-super admins
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(FraudEvent.agency_id == current_user.agency_id)
    
    query = query.order_by(FraudEvent.detected_at.desc()).limit(limit)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "fraud_type": event.fraud_type.value if event.fraud_type else None,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level.value,
            "action_taken": event.action_taken.value if event.action_taken else None,
            "blocked": event.blocked,
            "reviewed": event.reviewed,
            "false_positive": event.false_positive,
            "detected_at": event.detected_at.isoformat(),
            "ip_address": event.ip_address,
            "amount": event.amount,
            "currency": event.currency
        }
        for event in events
    ]


@router.get("/scores/{entity_type}/{entity_id}")
async def get_fraud_score(
    entity_type: str,
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get fraud score for an entity."""
    result = await db.execute(
        select(FraudScore).where(
            and_(
                FraudScore.entity_type == entity_type,
                FraudScore.entity_id == entity_id
            )
        )
    )
    score = result.scalar_one_or_none()
    
    if not score:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "current_score": 0,
            "risk_level": RiskLevel.LOW.value,
            "is_blocked": False,
            "is_under_review": False
        }
    
    return {
        "entity_type": score.entity_type,
        "entity_id": score.entity_id,
        "current_score": score.current_score,
        "max_score": score.max_score,
        "risk_level": score.risk_level.value,
        "velocity_score": score.velocity_score,
        "pattern_score": score.pattern_score,
        "anomaly_score": score.anomaly_score,
        "history_score": score.history_score,
        "is_blocked": score.is_blocked,
        "is_under_review": score.is_under_review,
        "last_activity": score.last_activity.isoformat() if score.last_activity else None
    }


@router.get("/review-queue")
async def get_review_queue(
    status: str = Query("pending", description="pending, in_review, resolved"),
    assigned_to_me: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get items in review queue."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    query = select(ReviewQueue).where(ReviewQueue.status == status)
    
    if assigned_to_me:
        query = query.where(ReviewQueue.assigned_to_id == current_user.id)
    
    # Agency filtering
    if current_user.role != UserRole.SUPER_ADMIN:
        query = query.where(ReviewQueue.agency_id == current_user.agency_id)
    
    query = query.order_by(ReviewQueue.priority.desc(), ReviewQueue.created_at)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return [
        {
            "id": str(item.id),
            "priority": item.priority,
            "status": item.status,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "reason": item.reason,
            "risk_score": item.risk_score,
            "risk_level": item.risk_level.value if item.risk_level else None,
            "created_at": item.created_at.isoformat(),
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "assigned_to_id": str(item.assigned_to_id) if item.assigned_to_id else None
        }
        for item in items
    ]


@router.post("/review-queue/{review_id}/assign")
async def assign_review_item(
    review_id: UUID,
    assignee_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Assign a review queue item to a user."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get review item
    result = await db.execute(
        select(ReviewQueue).where(ReviewQueue.id == review_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    # Update assignment
    item.assigned_to_id = assignee_id
    item.assigned_at = datetime.utcnow()
    item.status = "in_review"
    
    await db.commit()
    
    return BaseResponse(
        success=True,
        message="Review item assigned successfully"
    )


@router.post("/review-queue/{review_id}/resolve")
async def resolve_review_item(
    review_id: UUID,
    resolution: ReviewResolution,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Resolve a review queue item."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get review item
    result = await db.execute(
        select(ReviewQueue).where(ReviewQueue.id == review_id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    
    # Update resolution
    item.resolution = resolution.resolution
    item.resolution_notes = resolution.resolution_notes
    item.resolved_at = datetime.utcnow()
    item.resolved_by_id = current_user.id
    item.status = "resolved"
    
    # Update related fraud event if it's a false positive
    if resolution.resolution == "false_positive" and item.fraud_event_id:
        result = await db.execute(
            select(FraudEvent).where(FraudEvent.id == item.fraud_event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.false_positive = True
            event.reviewed = True
            event.reviewed_at = datetime.utcnow()
            event.reviewed_by_id = current_user.id
    
    await db.commit()
    
    return BaseResponse(
        success=True,
        message="Review item resolved successfully"
    )


@router.post("/whitelist", response_model=BaseResponse)
async def add_to_whitelist(
    whitelist: WhitelistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """Add entity to fraud whitelist."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can manage whitelist")
    
    # Check if already whitelisted
    existing = await db.execute(
        select(FraudWhitelist).where(
            and_(
                FraudWhitelist.entity_type == whitelist.entity_type,
                FraudWhitelist.entity_id == whitelist.entity_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Entity already whitelisted")
    
    # Create whitelist entry
    new_whitelist = FraudWhitelist(
        entity_type=whitelist.entity_type,
        entity_id=whitelist.entity_id,
        reason=whitelist.reason,
        whitelist_level=whitelist.whitelist_level,
        skip_checks=whitelist.skip_checks,
        valid_until=datetime.utcnow() + timedelta(days=whitelist.valid_days),
        created_by_id=current_user.id,
        approved_by_id=current_user.id
    )
    
    db.add(new_whitelist)
    await db.commit()
    
    # Clear cache
    await fraud_detector.redis.delete(f"whitelist:{whitelist.entity_type}:{whitelist.entity_id}")
    
    return BaseResponse(
        success=True,
        message="Entity added to whitelist successfully"
    )


@router.post("/check", response_model=Dict[str, Any])
async def manual_fraud_check(
    check_request: ManualFraudCheck,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Manually run fraud check on transaction data."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Run fraud check
    result = await fraud_detector.check_transaction(
        transaction_data=check_request.transaction_data,
        user_id=str(check_request.user_id),
        ip_address=check_request.ip_address or "manual_check",
        session=db
    )
    
    return {
        "allowed": result["allowed"],
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"].value,
        "reasons": result["reasons"],
        "action": result["action"].value
    }


@router.get("/statistics")
async def get_fraud_statistics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get fraud detection statistics."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Total events
    total_result = await db.execute(
        select(func.count(FraudEvent.id))
        .where(FraudEvent.detected_at >= since)
    )
    total_events = total_result.scalar() or 0
    
    # False positives
    fp_result = await db.execute(
        select(func.count(FraudEvent.id))
        .where(
            and_(
                FraudEvent.detected_at >= since,
                FraudEvent.false_positive == True
            )
        )
    )
    false_positives = fp_result.scalar() or 0
    
    # Blocked transactions
    blocked_result = await db.execute(
        select(func.count(FraudEvent.id))
        .where(
            and_(
                FraudEvent.detected_at >= since,
                FraudEvent.blocked == True
            )
        )
    )
    blocked = blocked_result.scalar() or 0
    
    # Pattern matches
    pattern_result = await db.execute(
        select(
            FraudPattern.name,
            FraudPattern.match_count,
            FraudPattern.false_positive_count
        )
        .where(FraudPattern.is_active == True)
        .order_by(FraudPattern.match_count.desc())
        .limit(10)
    )
    
    top_patterns = [
        {
            "name": row.name,
            "matches": row.match_count,
            "false_positives": row.false_positive_count,
            "accuracy": (
                (row.match_count - row.false_positive_count) / row.match_count * 100
                if row.match_count > 0 else 0
            )
        }
        for row in pattern_result
    ]
    
    return {
        "total_events": total_events,
        "false_positives": false_positives,
        "false_positive_rate": (
            false_positives / total_events * 100 if total_events > 0 else 0
        ),
        "blocked_transactions": blocked,
        "block_rate": (
            blocked / total_events * 100 if total_events > 0 else 0
        ),
        "top_patterns": top_patterns,
        "time_range_days": days
    }