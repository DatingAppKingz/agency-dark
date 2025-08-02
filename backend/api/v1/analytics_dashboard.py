"""
Analytics dashboard API endpoints
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta
import json

from core.database import get_db
from core.auth import get_current_user
from models.user import User
from modules.analytics.dashboard.dashboard_service import dashboard_service
from modules.analytics.dashboard.models import (
    DashboardWidget, DashboardLayout, WidgetType
)
from modules.analytics.realtime.engine import realtime_engine

router = APIRouter(prefix="/analytics/dashboard", tags=["analytics-dashboard"])


@router.get("")
async def get_dashboard(
    model_id: Optional[UUID] = None,
    period: str = Query("week", pattern="^(day|week|month|quarter|year|custom)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete dashboard data
    """
    # Determine time range
    if period == "custom" and start_date and end_date:
        time_range = {
            "period": "custom",
            "start_date": start_date,
            "end_date": end_date
        }
    else:
        end_date = date.today()
        if period == "day":
            start_date = end_date
        elif period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        elif period == "quarter":
            start_date = end_date - timedelta(days=90)
        elif period == "year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=7)
            
        time_range = {
            "period": period,
            "start_date": start_date,
            "end_date": end_date
        }
        
    # Verify access
    if model_id and not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    # Get dashboard data
    dashboard_data = await dashboard_service.get_dashboard_data(
        agency_id=UUID(current_user.agency_id),
        user_id=current_user.id,
        model_id=model_id,
        time_range=time_range,
        db=db
    )
    
    return dashboard_data


@router.post("/widgets")
async def create_widget(
    widget_type: str,
    title: str,
    config: Dict[str, Any],
    position: Dict[str, int] = {"x": 0, "y": 0},
    size: Dict[str, int] = {"width": 4, "height": 4},
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new dashboard widget
    """
    widget = await dashboard_service.widget_manager.create_widget(
        agency_id=UUID(current_user.agency_id),
        widget_type=widget_type,
        config={
            "title": title,
            "position": position,
            "size": size,
            **config
        },
        db=db
    )
    
    return {
        "id": widget.id,
        "type": widget.widget_type,
        "title": widget.title,
        "position": widget.position,
        "size": widget.size,
        "config": widget.config
    }


@router.put("/widgets/{widget_id}")
async def update_widget(
    widget_id: str,
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update widget configuration
    """
    # Verify widget ownership
    widget = await db.get(DashboardWidget, widget_id)
    if not widget or widget.agency_id != current_user.agency_id:
        raise HTTPException(status_code=404, detail="Widget not found")
        
    updated_widget = await dashboard_service.widget_manager.update_widget(
        widget_id=widget_id,
        updates=updates,
        db=db
    )
    
    return {
        "id": updated_widget.id,
        "type": updated_widget.widget_type,
        "title": updated_widget.title,
        "position": updated_widget.position,
        "size": updated_widget.size,
        "config": updated_widget.config
    }


@router.delete("/widgets/{widget_id}")
async def delete_widget(
    widget_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a widget
    """
    # Verify widget ownership
    widget = await db.get(DashboardWidget, widget_id)
    if not widget or widget.agency_id != current_user.agency_id:
        raise HTTPException(status_code=404, detail="Widget not found")
        
    success = await dashboard_service.widget_manager.delete_widget(
        widget_id=widget_id,
        db=db
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete widget")
        
    return {"message": "Widget deleted successfully"}


@router.get("/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: str,
    period: str = Query("week", pattern="^(day|week|month|quarter|year)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed data for a specific widget
    """
    # Verify widget ownership
    widget = await db.get(DashboardWidget, widget_id)
    if not widget or widget.agency_id != current_user.agency_id:
        raise HTTPException(status_code=404, detail="Widget not found")
        
    # Determine time range
    end_date = date.today()
    if period == "day":
        start_date = end_date
    elif period == "week":
        start_date = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    elif period == "quarter":
        start_date = end_date - timedelta(days=90)
    else:  # year
        start_date = end_date - timedelta(days=365)
        
    time_range = {
        "period": period,
        "start_date": start_date,
        "end_date": end_date
    }
    
    widget_data = await dashboard_service.get_widget_detail(
        widget_id=widget_id,
        time_range=time_range,
        db=db
    )
    
    return widget_data


@router.post("/layouts")
async def save_layout(
    name: str,
    widgets: List[Dict[str, Any]],
    is_default: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save dashboard layout
    """
    layout = await dashboard_service.widget_manager.save_layout(
        agency_id=UUID(current_user.agency_id),
        user_id=current_user.id,
        layout_name=name,
        widgets=widgets,
        db=db
    )
    
    if is_default:
        layout.is_default = True
        await db.commit()
        
    return {
        "id": layout.id,
        "name": layout.name,
        "widgets": layout.widgets,
        "is_default": layout.is_default,
        "created_at": layout.created_at
    }


@router.get("/layouts")
async def list_layouts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's saved layouts
    """
    from sqlalchemy import select, and_
    
    query = select(DashboardLayout).where(
        and_(
            DashboardLayout.agency_id == current_user.agency_id,
            DashboardLayout.user_id == str(current_user.id)
        )
    )
    
    result = await db.execute(query)
    layouts = result.scalars().all()
    
    return [
        {
            "id": layout.id,
            "name": layout.name,
            "is_default": layout.is_default,
            "is_shared": layout.is_shared,
            "created_at": layout.created_at,
            "updated_at": layout.updated_at
        }
        for layout in layouts
    ]


@router.delete("/layouts/{layout_id}")
async def delete_layout(
    layout_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a saved layout
    """
    layout = await db.get(DashboardLayout, layout_id)
    
    if not layout or layout.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Layout not found")
        
    if layout.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default layout")
        
    await db.delete(layout)
    await db.commit()
    
    return {"message": "Layout deleted successfully"}


@router.post("/export")
async def export_dashboard(
    format: str = Query(..., pattern="^(pdf|excel|json)$"),
    model_id: Optional[UUID] = None,
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export dashboard to specified format
    """
    # Verify access
    if model_id and not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    export_data = await dashboard_service.export_dashboard(
        agency_id=UUID(current_user.agency_id),
        user_id=current_user.id,
        format=format,
        db=db
    )
    
    # Return appropriate response based on format
    if format == "json":
        return json.loads(export_data)
    else:
        # For PDF and Excel, return file download
        from fastapi.responses import StreamingResponse
        import io
        
        file_extension = "pdf" if format == "pdf" else "xlsx"
        filename = f"analytics_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        
        return StreamingResponse(
            io.BytesIO(export_data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


@router.websocket("/realtime")
async def realtime_updates(
    websocket: WebSocket,
    model_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time dashboard updates
    """
    await websocket.accept()
    
    # Authenticate user
    try:
        # Get auth token from query params or headers
        token = websocket.query_params.get("token") or \
                websocket.headers.get("Authorization", "").replace("Bearer ", "")
                
        if not token:
            await websocket.close(code=1008, reason="Missing authentication")
            return
            
        # Verify token and get user
        from core.security import decode_access_token
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
            
        # Get user
        from models.user import User
        user = await db.get(User, UUID(user_id))
        
        if not user or not user.agency_id:
            await websocket.close(code=1008, reason="Invalid user")
            return
            
        # Verify model access if specified
        if model_id and not await _user_has_model_access(user, UUID(model_id), db):
            await websocket.close(code=1008, reason="Access denied")
            return
            
        # Subscribe to real-time updates
        client_id = f"ws_{user.id}_{datetime.utcnow().timestamp()}"
        await realtime_engine.subscribe_to_updates(
            client_id=client_id,
            agency_id=user.agency_id,
            model_id=model_id
        )
        
        # Send initial data
        initial_data = await realtime_engine.get_realtime_metrics(
            agency_id=user.agency_id,
            model_id=model_id,
            time_range=300  # Last 5 minutes
        )
        
        await websocket.send_json({
            "type": "initial",
            "data": initial_data
        })
        
        # Listen for updates
        from core.redis import redis_client
        pubsub = redis_client.pubsub()
        channel = f"analytics:updates:{user.agency_id}:{model_id or 'all'}"
        await pubsub.subscribe(channel)
        
        try:
            while True:
                # Check for Redis updates
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                
                if message and message['type'] == 'message':
                    update_data = json.loads(message['data'])
                    await websocket.send_json({
                        "type": "update",
                        "data": update_data
                    })
                    
                # Also handle incoming messages from client
                try:
                    client_message = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=0.1
                    )
                    
                    # Handle client requests (e.g., change time range)
                    if client_message.get("action") == "change_range":
                        time_range = client_message.get("time_range", 300)
                        data = await realtime_engine.get_realtime_metrics(
                            agency_id=user.agency_id,
                            model_id=model_id,
                            time_range=time_range
                        )
                        await websocket.send_json({
                            "type": "range_update",
                            "data": data
                        })
                        
                except asyncio.TimeoutError:
                    pass
                    
                await asyncio.sleep(0.1)
                
        except WebSocketDisconnect:
            pass
        finally:
            # Cleanup
            await realtime_engine.unsubscribe_from_updates(
                client_id=client_id,
                agency_id=user.agency_id,
                model_id=model_id
            )
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


@router.get("/insights")
async def get_ai_insights(
    model_id: Optional[UUID] = None,
    period: str = Query("month", pattern="^(week|month|quarter)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered insights and recommendations
    """
    # Verify access
    if model_id and not await _user_has_model_access(current_user, model_id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    # Determine time range
    end_date = date.today()
    if period == "week":
        start_date = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    else:  # quarter
        start_date = end_date - timedelta(days=90)
        
    time_range = {
        "period": period,
        "start_date": start_date,
        "end_date": end_date
    }
    
    # Get insights
    from modules.analytics.ai.insights_generator import InsightsGenerator
    
    generator = InsightsGenerator()
    insights = await generator.generate_insights(
        agency_id=UUID(current_user.agency_id),
        model_id=model_id,
        time_range=time_range,
        db=db
    )
    
    return insights


@router.get("/widgets/types")
async def get_widget_types():
    """
    Get available widget types and their configurations
    """
    widget_configs = dashboard_service.widget_manager._widget_configs
    
    return [
        {
            "type": widget_type,
            "title": config["title"],
            "description": config["description"],
            "category": config.get("type", "chart"),
            "default_size": config["default_size"],
            "min_size": config["min_size"],
            "supports_models": config.get("data_source") != "agency_only",
            "refresh_interval": config["refresh_interval"],
            "configurable_options": config.get("configurable_options", [])
        }
        for widget_type, config in widget_configs.items()
    ]


async def _user_has_model_access(
    user: User,
    model_id: UUID,
    db: AsyncSession
) -> bool:
    """Check if user has access to model"""
    from modules.models.domain.models import Model
    
    model = await db.get(Model, model_id)
    if not model:
        return False
        
    return (
        user.agency_id == model.agency_id or
        user.id == model.user_id
    )
