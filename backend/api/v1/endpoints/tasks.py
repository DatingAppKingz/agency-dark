"""Task management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from datetime import datetime

from core.celery_app import celery_app, get_task_info, cancel_task
from models.user import User, UserRole
from api.v1.endpoints.auth_simple import get_current_user
from tasks.analytics import calculate_model_engagement, generate_revenue_report
from tasks.financial import process_pending_payouts, check_subscription_expirations


router = APIRouter()


@router.post("/trigger/{task_name}")
async def trigger_task(
    task_name: str,
    params: Dict[str, Any] = {},
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Trigger a background task."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Map task names to actual tasks
    task_map = {
        "calculate_engagement": calculate_model_engagement,
        "generate_revenue_report": generate_revenue_report,
        "process_payouts": process_pending_payouts,
        "check_subscriptions": check_subscription_expirations,
    }
    
    if task_name not in task_map:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
    
    # Trigger the task
    task = task_map[task_name]
    
    # Apply appropriate parameters based on task
    if task_name == "calculate_engagement":
        result = task.delay(
            model_id=params.get("model_id", 1),
            period_days=params.get("period_days", 30)
        )
    elif task_name == "generate_revenue_report":
        result = task.delay(
            agency_id=current_user.agency_id or 1,
            start_date=params.get("start_date", "2025-01-01"),
            end_date=params.get("end_date", "2025-07-30")
        )
    else:
        result = task.delay()
    
    return {
        "task_id": result.id,
        "task_name": task_name,
        "status": "PENDING",
        "message": f"Task '{task_name}' has been queued",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get the status of a background task."""
    try:
        task_info = get_task_info(task_id)
        return task_info
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")


@router.post("/cancel/{task_id}")
async def cancel_background_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Cancel a running background task."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        cancel_task(task_id)
        return {
            "task_id": task_id,
            "status": "CANCELLED",
            "message": "Task cancellation requested",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to cancel task: {str(e)}")


@router.get("/active")
async def list_active_tasks(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """List all active tasks."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get active tasks from Celery
    active_tasks = []
    inspect = celery_app.control.inspect()
    
    # Get active tasks
    active = inspect.active()
    if active:
        for worker, tasks in active.items():
            for task in tasks:
                active_tasks.append({
                    "worker": worker,
                    "task_id": task["id"],
                    "name": task["name"],
                    "args": task.get("args", []),
                    "kwargs": task.get("kwargs", {}),
                    "time_start": task.get("time_start")
                })
    
    return active_tasks


@router.get("/scheduled")
async def list_scheduled_tasks(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all scheduled periodic tasks."""
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get scheduled tasks from beat schedule
    scheduled_tasks = []
    for name, config in celery_app.conf.beat_schedule.items():
        scheduled_tasks.append({
            "name": name,
            "task": config["task"],
            "schedule": str(config["schedule"]),
            "options": config.get("options", {})
        })
    
    return {
        "scheduled_tasks": scheduled_tasks,
        "total": len(scheduled_tasks)
    }