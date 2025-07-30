"""Fraud detection endpoints for identifying suspicious activities."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.fraud_service import FraudService
from core.exceptions import ValidationError, NotFoundError

router = APIRouter()


# Request/Response schemas
class TransactionCheckRequest(BaseModel):
    """Transaction fraud check request."""
    fan_id: int
    amount: float = Field(..., gt=0)
    payment_method: str
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class FraudCheckResponse(BaseModel):
    """Fraud check response."""
    check_id: str
    risk_score: int
    risk_level: str
    recommended_action: str
    indicators: List[Dict[str, Any]]
    checked_at: str


class FraudAlertResponse(BaseModel):
    """Fraud alert response."""
    alert_id: str
    agency_id: int
    fan_id: int
    risk_level: str
    risk_score: int
    status: str
    created_at: str
    indicators: List[Dict[str, Any]]
    notes: Optional[str] = None


class AlertUpdateRequest(BaseModel):
    """Alert status update request."""
    status: str = Field(..., pattern="^(pending|reviewing|resolved|escalated)$")
    notes: Optional[str] = None


class RiskProfileResponse(BaseModel):
    """Risk profile response."""
    fan_id: int
    account_age_days: int
    total_transactions: int
    chargebacks: int
    chargeback_rate: float
    risk_indicators: Dict[str, bool]
    recent_alerts: List[Dict[str, Any]]
    overall_risk: str


@router.post("/check-transaction", response_model=FraudCheckResponse)
async def check_transaction(
    request: TransactionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FraudCheckResponse:
    """
    Check a transaction for fraud indicators.
    
    - Analyzes multiple risk factors
    - Returns risk score and recommended action
    - Creates alerts for high-risk transactions
    """
    try:
        # Add agency context
        transaction_data = request.dict()
        transaction_data["agency_id"] = current_user.agency_id
        transaction_data["checked_by"] = current_user.id
        
        result = await FraudService.check_transaction(
            db=db,
            transaction_data=transaction_data
        )
        
        return FraudCheckResponse(
            check_id=result["check_id"],
            risk_score=result["risk_score"],
            risk_level=result["risk_level"],
            recommended_action=result["recommended_action"],
            indicators=result["indicators"],
            checked_at=result["checked_at"]
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fraud check failed: {str(e)}")


@router.get("/alerts", response_model=List[FraudAlertResponse])
async def get_fraud_alerts(
    status: Optional[str] = Query(None, pattern="^(pending|reviewing|resolved|escalated)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[FraudAlertResponse]:
    """
    Get fraud alerts for the agency.
    
    - Filter by status
    - Shows recent suspicious activities
    - Requires manager access
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    alerts = await FraudService.get_alerts(
        db=db,
        agency_id=current_user.agency_id,
        status=status,
        limit=limit
    )
    
    return [
        FraudAlertResponse(
            alert_id=alert["alert_id"],
            agency_id=alert["agency_id"],
            fan_id=alert["fan_id"],
            risk_level=alert["risk_level"],
            risk_score=alert["risk_score"],
            status=alert["status"],
            created_at=alert["created_at"],
            indicators=alert["indicators"],
            notes=alert.get("notes")
        )
        for alert in alerts
    ]


@router.put("/alerts/{alert_id}")
async def update_alert_status(
    alert_id: str,
    request: AlertUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Update fraud alert status.
    
    - Mark as reviewing, resolved, or escalated
    - Add notes for future reference
    - Requires manager access
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        await FraudService.update_alert_status(
            db=db,
            alert_id=alert_id,
            status=request.status,
            notes=request.notes
        )
        
        return {"message": "Alert updated successfully", "status": request.status}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/risk-profile/{fan_id}", response_model=RiskProfileResponse)
async def get_risk_profile(
    fan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RiskProfileResponse:
    """
    Get comprehensive risk profile for a fan.
    
    - Shows transaction history and patterns
    - Calculates chargeback rate
    - Lists recent alerts
    """
    try:
        profile = await FraudService.get_risk_profile(
            db=db,
            fan_id=fan_id
        )
        
        return RiskProfileResponse(**profile)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/statistics")
async def get_fraud_statistics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get fraud detection statistics.
    
    - Alert counts by risk level
    - Detection rate trends
    - Top risk indicators
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all alerts for the period
    alerts = await FraudService.get_alerts(
        db=db,
        agency_id=current_user.agency_id,
        limit=1000
    )
    
    # Calculate statistics
    stats = {
        "total_alerts": len(alerts),
        "by_risk_level": {},
        "by_status": {},
        "top_indicators": {}
    }
    
    for alert in alerts:
        # Count by risk level
        risk_level = alert.get("risk_level", "unknown")
        stats["by_risk_level"][risk_level] = stats["by_risk_level"].get(risk_level, 0) + 1
        
        # Count by status
        status = alert.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        # Count indicators
        for indicator in alert.get("indicators", []):
            ind_type = indicator.get("type", "unknown")
            stats["top_indicators"][ind_type] = stats["top_indicators"].get(ind_type, 0) + 1
    
    return {
        "period_days": days,
        "statistics": stats,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/rules")
async def get_fraud_rules(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get configured fraud detection rules."""
    return {
        "indicators": FraudService.FRAUD_INDICATORS,
        "thresholds": {
            "low": FraudService.RISK_THRESHOLD_LOW,
            "medium": FraudService.RISK_THRESHOLD_MEDIUM,
            "high": FraudService.RISK_THRESHOLD_HIGH
        },
        "actions": {
            "minimal": "allow",
            "low": "monitor",
            "medium": "review",
            "high": "block"
        }
    }


@router.post("/test")
async def test_fraud_detection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test fraud detection with sample data.
    
    - For testing and demonstration
    - Uses synthetic transaction data
    """
    # Create test transaction
    test_transaction = {
        "fan_id": 1,
        "amount": 500.00,
        "payment_method": "credit_card",
        "ip_address": "192.168.1.1",
        "agency_id": current_user.agency_id,
        "checked_by": current_user.id
    }
    
    try:
        result = await FraudService.check_transaction(
            db=db,
            transaction_data=test_transaction
        )
        
        return {
            "test_data": test_transaction,
            "result": result
        }
    except Exception as e:
        return {
            "test_data": test_transaction,
            "error": str(e)
        }