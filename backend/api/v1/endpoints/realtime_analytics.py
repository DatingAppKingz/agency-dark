"""Real-time analytics WebSocket endpoints."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from core.database import get_db
from core.dependencies import get_current_active_user
# from core.security_v2.authentication import get_current_user_from_websocket  # Not implemented yet
# from core.security_v2.authorization import check_permission  # Not implemented yet
from core.redis import redis_manager
from services.analytics.realtime_analytics_service import (
    RealtimeAnalyticsService,
    MetricType,
    TimeWindow,
    MetricUpdate
)
from models.user import User
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics/realtime")

# Global analytics service instance
analytics_service: Optional[RealtimeAnalyticsService] = None


async def get_analytics_service(
    db: AsyncSession = Depends(get_db)
) -> RealtimeAnalyticsService:
    """Get or create analytics service instance."""
    global analytics_service
    
    if analytics_service is None:
        redis = await redis_manager.connect()
        analytics_service = RealtimeAnalyticsService(redis, db)
        await analytics_service.start()
    
    return analytics_service


class ConnectionManager:
    """Manages WebSocket connections for real-time analytics."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_channels: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register a new connection."""
        await websocket.accept()
        
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        
        self.active_connections[channel].append(websocket)
        
        if websocket not in self.user_channels:
            self.user_channels[websocket] = []
        
        self.user_channels[websocket].append(channel)
        
        logger.info(f"WebSocket connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        # Remove from all channels
        if websocket in self.user_channels:
            for channel in self.user_channels[websocket]:
                if channel in self.active_connections:
                    self.active_connections[channel].remove(websocket)
                    if not self.active_connections[channel]:
                        del self.active_connections[channel]
            
            del self.user_channels[websocket]
        
        logger.info("WebSocket disconnected")
    
    async def send_to_channel(self, channel: str, message: dict):
        """Send message to all connections in a channel."""
        if channel in self.active_connections:
            # Send to all connections in parallel
            tasks = []
            for connection in self.active_connections[channel]:
                tasks.append(self._send_safe(connection, message))
            
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_safe(self, websocket: WebSocket, message: dict):
        """Safely send message to a websocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            # Connection might be closed, will be cleaned up later


manager = ConnectionManager()


@router.websocket("/ws/{agency_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    agency_id: str,
    model_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time analytics updates.
    
    Clients can subscribe to:
    - Agency-level metrics: /ws/{agency_id}
    - Model-specific metrics: /ws/{agency_id}?model_id={model_id}
    """
    try:
        # Authenticate user
        user = await get_current_user_from_websocket(websocket, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Check permissions
        if user.agency_id != agency_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Determine channel
        if model_id:
            channel = f"model:{model_id}"
        else:
            channel = f"agency:{agency_id}"
        
        # Connect
        await manager.connect(websocket, channel)
        
        # Get analytics service
        analytics_service = await get_analytics_service(db)
        
        # Create callback for updates
        async def send_updates(data: Dict[str, Any]):
            await manager.send_to_channel(channel, data)
        
        # Subscribe to analytics updates
        analytics_service.subscribe(channel, send_updates)
        
        # Send initial data
        initial_data = await analytics_service.get_metric_summary(
            agency_id,
            {"start": datetime.utcnow() - timedelta(hours=24), "end": datetime.utcnow()}
        )
        await websocket.send_json({
            "type": "initial",
            "data": initial_data
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_json()
                
                # Handle different message types
                if data.get("type") == "subscribe":
                    # Subscribe to additional metrics
                    metric_types = data.get("metrics", [])
                    logger.info(f"Client subscribing to metrics: {metric_types}")
                
                elif data.get("type") == "unsubscribe":
                    # Unsubscribe from metrics
                    metric_types = data.get("metrics", [])
                    logger.info(f"Client unsubscribing from metrics: {metric_types}")
                
                elif data.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        
    finally:
        # Cleanup
        if 'analytics_service' in locals() and 'send_updates' in locals():
            analytics_service.unsubscribe(channel, send_updates)
        
        manager.disconnect(websocket)


@router.get("/metrics")
async def get_realtime_metrics(
    metric_types: List[MetricType] = Query(...),
    window: TimeWindow = Query(TimeWindow.MINUTE),
    limit: int = Query(100, ge=1, le=1000),
    agency_id: Optional[str] = None,
    model_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    analytics_service: RealtimeAnalyticsService = Depends(get_analytics_service)
):
    """
    Get real-time metrics data.
    
    Returns recent metric values for the specified types and time window.
    """
    # Check permissions
    check_permission(current_user, "analytics", "read")
    
    # Build dimensions
    dimensions = {}
    if agency_id:
        if current_user.agency_id != agency_id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this agency's metrics"
            )
        dimensions["agency_id"] = agency_id
    else:
        dimensions["agency_id"] = current_user.agency_id
    
    if model_id:
        dimensions["model_id"] = model_id
    
    # Get metrics
    metrics = await analytics_service.get_realtime_metrics(
        metric_types=metric_types,
        dimensions=dimensions,
        window=window,
        limit=limit
    )
    
    return {
        "metrics": metrics,
        "window": window.value,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/summary")
async def get_analytics_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_active_user),
    analytics_service: RealtimeAnalyticsService = Depends(get_analytics_service)
):
    """
    Get analytics summary for the dashboard.
    
    Returns aggregated metrics for the specified time range.
    """
    # Check permissions
    check_permission(current_user, "analytics", "read")
    
    # Default time range
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=7)
    
    # Get summary
    summary = await analytics_service.get_metric_summary(
        agency_id=current_user.agency_id,
        time_range={"start": start_date, "end": end_date}
    )
    
    return summary


@router.post("/track")
async def track_metric(
    metric_type: MetricType,
    value: float,
    dimensions: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_active_user),
    analytics_service: RealtimeAnalyticsService = Depends(get_analytics_service)
):
    """
    Track a new metric value.
    
    This endpoint is used by internal services to report metrics.
    """
    # Check permissions
    check_permission(current_user, "analytics", "write")
    
    # Create metric update
    update = MetricUpdate(
        metric_type=metric_type,
        value=value,
        dimensions=dimensions or {},
        metadata=metadata or {}
    )
    
    # Add agency context
    if "agency_id" not in update.dimensions:
        update.dimensions["agency_id"] = current_user.agency_id
    
    # Track metric
    await analytics_service.track_metric(update)
    
    return {
        "success": True,
        "metric_type": metric_type.value,
        "value": value,
        "timestamp": update.timestamp.isoformat()
    }


@router.get("/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_active_user),
    analytics_service: RealtimeAnalyticsService = Depends(get_analytics_service)
):
    """
    Get performance metrics of the analytics system.
    
    Returns information about processing times, error rates, etc.
    """
    # Check permissions (admin only)
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    performance = await analytics_service._get_performance_summary()
    
    return performance


# Startup event to initialize analytics service
async def startup_analytics():
    """Initialize analytics service on startup."""
    db = await anext(get_db())
    redis = await redis_manager.connect()
    
    global analytics_service
    analytics_service = RealtimeAnalyticsService(redis, db)
    await analytics_service.start()
    
    logger.info("Real-time analytics service started")


# Shutdown event to cleanup
async def shutdown_analytics():
    """Cleanup analytics service on shutdown."""
    global analytics_service
    
    if analytics_service:
        await analytics_service.stop()
        analytics_service = None
    
    logger.info("Real-time analytics service stopped")