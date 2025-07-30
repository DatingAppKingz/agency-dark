"""Bulk operations endpoints for processing multiple items efficiently."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.bulk_service import BulkService
from core.exceptions import NotFoundError, ValidationError, PermissionError

router = APIRouter()


# Request/Response schemas
class BulkMessageRequest(BaseModel):
    """Bulk message sending request."""
    conversation_ids: List[int] = Field(..., min_items=1, max_items=1000)
    content: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    scheduled_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BulkTagRequest(BaseModel):
    """Bulk tag operation request."""
    conversation_ids: List[int] = Field(..., min_items=1, max_items=1000)
    add_tags: List[str] = Field(default_factory=list)
    remove_tags: List[str] = Field(default_factory=list)


class BulkStatusRequest(BaseModel):
    """Bulk status update request."""
    conversation_ids: List[int] = Field(..., min_items=1, max_items=1000)
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=10)


class BulkAssignRequest(BaseModel):
    """Bulk conversation assignment request."""
    conversation_ids: List[int] = Field(..., min_items=1, max_items=1000)
    chatter_id: int


class BulkDeleteRequest(BaseModel):
    """Bulk message deletion request."""
    message_ids: List[int] = Field(..., min_items=1, max_items=10000)


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    status: str
    task_id: Optional[str] = None
    sent_count: Optional[int] = None
    updated_count: Optional[int] = None
    deleted_count: Optional[int] = None
    failed_count: Optional[int] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@router.post("/messages/send", response_model=BulkOperationResponse)
async def send_bulk_messages(
    request: BulkMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """
    Send messages to multiple conversations.
    
    - Can send to up to 1000 conversations at once
    - Supports text content and media attachments
    - Can be scheduled for future delivery
    - Returns task ID for scheduled messages
    """
    try:
        result = await BulkService.send_bulk_messages(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            message_data=request.dict()
        )
        
        return BulkOperationResponse(
            status=result["status"],
            task_id=result.get("task_id"),
            sent_count=result.get("sent_count"),
            failed_count=result.get("failed_count"),
            details={
                "message_ids": result.get("message_ids", []),
                "failed_conversations": result.get("failed_conversations", [])
            }
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk send failed: {str(e)}")


@router.post("/conversations/tags", response_model=BulkOperationResponse)
async def bulk_tag_conversations(
    request: BulkTagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """
    Add or remove tags from multiple conversations.
    
    - Can update up to 1000 conversations at once
    - Supports both adding and removing tags in one operation
    - Tags are case-sensitive
    """
    try:
        result = await BulkService.bulk_tag_conversations(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            tag_data=request.dict()
        )
        
        return BulkOperationResponse(
            status=result["status"],
            updated_count=result.get("updated_count"),
            failed_count=result.get("failed_count"),
            details={
                "failed_updates": result.get("failed_updates", [])
            }
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk tag update failed: {str(e)}")


@router.post("/conversations/status", response_model=BulkOperationResponse)
async def bulk_update_status(
    request: BulkStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """
    Update status or priority for multiple conversations.
    
    - Can update up to 1000 conversations at once
    - Can update status, priority, or both
    - Priority range: 0 (lowest) to 10 (highest)
    """
    try:
        result = await BulkService.bulk_update_conversation_status(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            status_data=request.dict()
        )
        
        return BulkOperationResponse(
            status=result["status"],
            updated_count=result.get("updated_count"),
            message=f"Updated {result.get('updated_count', 0)} conversations"
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk status update failed: {str(e)}")


@router.post("/conversations/assign", response_model=BulkOperationResponse)
async def bulk_assign_conversations(
    request: BulkAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """
    Assign multiple conversations to a chatter.
    
    - Can assign up to 1000 conversations at once
    - Chatter must be active and belong to the same agency
    - Updates assignment immediately
    """
    try:
        result = await BulkService.bulk_assign_conversations(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            assign_data=request.dict()
        )
        
        return BulkOperationResponse(
            status=result["status"],
            updated_count=result.get("assigned_count"),
            message=f"Assigned {result.get('assigned_count', 0)} conversations to chatter {request.chatter_id}"
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk assignment failed: {str(e)}")


@router.delete("/messages", response_model=BulkOperationResponse)
async def bulk_delete_messages(
    request: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkOperationResponse:
    """
    Delete multiple messages.
    
    - Can delete up to 10000 messages at once
    - Requires admin or manager role
    - Permanent deletion - cannot be undone
    """
    try:
        result = await BulkService.bulk_delete_messages(
            db=db,
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            delete_data=request.dict()
        )
        
        return BulkOperationResponse(
            status=result["status"],
            deleted_count=result.get("deleted_count"),
            message=f"Deleted {result.get('deleted_count', 0)} messages from {result.get('affected_conversations', 0)} conversations"
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk deletion failed: {str(e)}")


@router.get("/status/{task_id}", response_model=Dict[str, Any])
async def get_bulk_operation_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get status of a bulk operation task.
    
    Returns the current status of a scheduled or long-running bulk operation.
    """
    try:
        result = await BulkService.get_bulk_operation_status(
            db=db,
            task_id=task_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


# Additional utility endpoints

@router.get("/limits")
async def get_bulk_operation_limits(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get bulk operation limits for the current user."""
    return {
        "max_conversations_per_operation": 1000,
        "max_messages_per_deletion": 10000,
        "max_tags_per_operation": 50,
        "rate_limit_per_hour": 100,
        "concurrent_operations": 5
    }


@router.get("/history")
async def get_bulk_operation_history(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get history of bulk operations performed by the user."""
    # This would typically query a bulk_operations table
    # For now, return a placeholder
    return {
        "operations": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }