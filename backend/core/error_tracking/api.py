"""
API endpoints for error tracking and reporting
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timedelta

from .error_tracker import error_tracker, ErrorSeverity, ErrorCategory
from core.auth.dependencies import get_current_user, require_admin
from core.models import User

router = APIRouter(prefix="/api/v1/errors", tags=["error-tracking"])


@router.get("/report")
async def get_error_report(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user: User = Depends(require_admin)
):
    """
    Get error report for the specified time range
    
    Requires admin privileges
    """
    # Parse filters
    category_enum = ErrorCategory(category) if category else None
    severity_enum = ErrorSeverity(severity) if severity else None
    
    # Get report
    report = await error_tracker.get_error_report(
        time_range=timedelta(hours=hours),
        category=category_enum,
        severity=severity_enum
    )
    
    return report


@router.get("/details/{error_id}")
async def get_error_details(
    error_id: str,
    current_user: User = Depends(require_admin)
):
    """
    Get detailed information about a specific error
    
    Requires admin privileges
    """
    details = await error_tracker.get_error_details(error_id)
    
    if not details:
        raise HTTPException(status_code=404, detail="Error not found")
    
    return details


@router.get("/trend/{fingerprint}")
async def get_error_trend(
    fingerprint: str,
    days: int = Query(7, ge=1, le=30, description="Number of days"),
    current_user: User = Depends(require_admin)
):
    """
    Get trend data for a specific error
    
    Requires admin privileges
    """
    trend = await error_tracker.get_error_trend(fingerprint, days)
    return trend


@router.get("/categories")
async def list_error_categories(
    current_user: User = Depends(get_current_user)
):
    """
    List all error categories
    """
    return [
        {
            "value": category.value,
            "name": category.name,
            "description": category.value.replace("_", " ").title()
        }
        for category in ErrorCategory
    ]


@router.get("/severities")
async def list_error_severities(
    current_user: User = Depends(get_current_user)
):
    """
    List all error severity levels
    """
    return [
        {
            "value": severity.value,
            "name": severity.name,
            "description": severity.value.title()
        }
        for severity in ErrorSeverity
    ]


@router.get("/dashboard")
async def get_error_dashboard(
    current_user: User = Depends(require_admin)
):
    """
    Get error tracking dashboard data
    
    Requires admin privileges
    """
    # Get reports for different time ranges
    last_hour = await error_tracker.get_error_report(timedelta(hours=1))
    last_24h = await error_tracker.get_error_report(timedelta(hours=24))
    last_week = await error_tracker.get_error_report(timedelta(days=7))
    
    # Get critical errors
    critical_errors = await error_tracker.get_error_report(
        timedelta(hours=24),
        severity=ErrorSeverity.CRITICAL
    )
    
    return {
        "overview": {
            "last_hour": {
                "total_errors": last_hour['summary']['total_errors'],
                "error_rate": last_hour['summary']['error_rate'],
                "affected_users": last_hour['summary']['affected_users']
            },
            "last_24h": {
                "total_errors": last_24h['summary']['total_errors'],
                "unique_errors": last_24h['summary']['unique_errors'],
                "affected_users": last_24h['summary']['affected_users']
            },
            "last_week": {
                "total_errors": last_week['summary']['total_errors'],
                "unique_errors": last_week['summary']['unique_errors'],
                "affected_users": last_week['summary']['affected_users']
            }
        },
        "by_severity": last_24h['by_severity'],
        "by_category": last_24h['by_category'],
        "top_errors": last_24h['top_errors'][:5],
        "critical_errors": critical_errors['top_errors'],
        "recent_critical": critical_errors['recent_critical'],
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/test")
async def test_error_tracking(
    severity: str = Query("medium", description="Error severity to test"),
    current_user: User = Depends(require_admin)
):
    """
    Test error tracking by generating a test error
    
    Requires admin privileges
    """
    # Generate test error
    try:
        if severity == "critical":
            raise Exception("Test critical error: Database connection lost")
        elif severity == "high":
            raise Exception("Test high severity error: Authentication failed")
        elif severity == "medium":
            raise Exception("Test medium severity error: Validation failed")
        else:
            raise Exception("Test low severity error: Resource not found")
    except Exception as exc:
        error_id = await error_tracker.track_error(
            error=exc,
            operation="test_error_tracking",
            user_id=str(current_user.id),
            metadata={"test": True, "requested_severity": severity}
        )
        
        return {
            "message": "Test error tracked successfully",
            "error_id": error_id,
            "severity": severity
        }


# WebSocket endpoint for real-time error monitoring
from fastapi import WebSocket, WebSocketDisconnect
import asyncio


@router.websocket("/live")
async def error_monitoring_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token")
):
    """
    WebSocket endpoint for real-time error monitoring
    """
    # Verify token and check admin privileges
    # (Implementation depends on your auth system)
    
    await websocket.accept()
    
    try:
        # Send initial data
        initial_report = await error_tracker.get_error_report(timedelta(hours=1))
        await websocket.send_json({
            "type": "initial",
            "data": initial_report
        })
        
        # Subscribe to error updates
        while True:
            # Check for new errors every 5 seconds
            await asyncio.sleep(5)
            
            # Get latest errors
            latest_report = await error_tracker.get_error_report(timedelta(minutes=5))
            
            if latest_report['summary']['total_errors'] > 0:
                await websocket.send_json({
                    "type": "update",
                    "data": {
                        "recent_errors": latest_report['top_errors'][:5],
                        "error_rate": latest_report['summary']['error_rate']
                    }
                })
    
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.close(code=1000, reason=str(exc))