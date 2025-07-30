"""Real-time dashboard updates via WebSocket."""

from fastapi import APIRouter, WebSocket, Depends, Query
from typing import Dict, Any, List
import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.sql import literal

from core.websocket import WebSocketHandler, manager, get_current_user_websocket
from models.user import User, UserRole
from core.database import AsyncSessionLocal
from sqlalchemy import select, func, and_
from models.financial import Transaction, TransactionStatus
from models.chat import Message, Conversation
from models.model import Model, ModelStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class DashboardWebSocketHandler(WebSocketHandler):
    """Handler for real-time dashboard updates."""
    
    def __init__(self, websocket: WebSocket, user: User):
        super().__init__(websocket, user)
        self.update_interval = 5  # seconds
        self.update_task = None
        
    async def handle(self):
        """Override to start dashboard updates."""
        # Start periodic updates task (but don't send anything yet)
        self.update_task = asyncio.create_task(self._start_updates_after_connection())
        
        try:
            # Call parent handle() which will accept the connection
            await super().handle()
        finally:
            # Cancel update task
            if self.update_task:
                self.update_task.cancel()
                
    async def _start_updates_after_connection(self):
        """Start updates after connection is established."""
        # Wait a moment for the connection to be fully established
        await asyncio.sleep(0.1)
        
        # Join appropriate dashboard room
        if self.user.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
            if self.user.agency_id:
                await manager.join_room(self.user.id, f"dashboard_agency_{self.user.agency_id}")
        elif self.user.role == UserRole.MODEL:
            await manager.join_room(self.user.id, f"dashboard_model_{self.user.id}")
            
        # Send initial stats
        await self.send_dashboard_stats()
        
        # Continue with periodic updates
        await self.send_periodic_updates()
                
    async def handle_custom_message(self, data: Dict[str, Any]):
        """Handle dashboard-specific messages."""
        message_type = data.get("type")
        
        if message_type == "set_update_interval":
            self.update_interval = max(1, min(60, data.get("interval", 5)))
        elif message_type == "get_dashboard_stats":
            await self.send_dashboard_stats()
        elif message_type == "get_live_activity":
            await self.send_live_activity()
            
    async def send_periodic_updates(self):
        """Send periodic dashboard updates."""
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                await self.send_dashboard_stats()
                await self.send_live_activity()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic updates: {e}")
                
    async def send_dashboard_stats(self):
        """Send current dashboard statistics."""
        async with AsyncSessionLocal() as db:
            if self.user.role in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
                stats = await self.get_agency_stats(db)
            else:
                stats = await self.get_model_stats(db)
                
            await self.websocket.send_json({
                "type": "dashboard_stats",
                "stats": stats,
                "timestamp": datetime.utcnow().isoformat()
            })
            
    async def get_agency_stats(self, db) -> Dict[str, Any]:
        """Get agency-level statistics."""
        # Base query filters
        agency_filter = True
        if self.user.agency_id:
            agency_filter = Model.agency_id == self.user.agency_id
            
        # Active models
        active_models_stmt = select(func.count(Model.id)).where(
            and_(Model.status == ModelStatus.ACTIVE, agency_filter)
        )
        active_models = await db.scalar(active_models_stmt) or 0
        
        # Today's revenue
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
            and_(
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.created_at >= today_start,
                Transaction.model.has(agency_filter)
            )
        )
        today_revenue = float(await db.scalar(revenue_stmt) or 0)
        
        # Messages today
        messages_stmt = select(func.count(Message.id)).where(
            and_(
                Message.created_at >= today_start,
                Message.conversation.has(Conversation.model.has(agency_filter))
            )
        )
        messages_today = await db.scalar(messages_stmt) or 0
        
        return {
            "active_models": active_models,
            "today_revenue": today_revenue,
            "messages_today": messages_today,
            "conversion_rate": 12.5,  # Would calculate actual rate
            "active_chats": 45  # Would count active chats
        }
        
    async def get_model_stats(self, db) -> Dict[str, Any]:
        """Get model-specific statistics."""
        model_id = self.user.id
        
        # Today's earnings
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        earnings_stmt = select(func.coalesce(func.sum(Transaction.gross_amount * literal(0.7)), 0)).where(
            and_(
                Transaction.model_id == model_id,
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.created_at >= today_start
            )
        )
        today_earnings = float(await db.scalar(earnings_stmt) or 0)
        
        # Messages sent
        messages_stmt = select(func.count(Message.id)).where(
            and_(
                Message.sender_id == model_id,
                Message.created_at >= today_start
            )
        )
        messages_sent = await db.scalar(messages_stmt) or 0
        
        return {
            "today_earnings": today_earnings,
            "messages_sent": messages_sent,
            "active_subscribers": 125,  # Would get actual count
            "new_subscribers": 5,  # Would calculate
            "response_rate": 95.2  # Would calculate
        }
        
    async def send_live_activity(self):
        """Send live activity feed."""
        # This would fetch recent activities
        activities = [
            {
                "type": "new_message",
                "description": "New message in chat",
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "type": "new_subscriber",
                "description": "New subscriber joined",
                "timestamp": (datetime.utcnow() - timedelta(minutes=2)).isoformat()
            }
        ]
        
        await self.websocket.send_json({
            "type": "live_activity",
            "activities": activities
        })


@router.websocket("/dashboard")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time dashboard updates."""
    try:
        user = await get_current_user_websocket(websocket, token)
        handler = DashboardWebSocketHandler(websocket, user)
        await handler.handle()
    except Exception as e:
        logger.error(f"Dashboard WebSocket error: {e}")


# Utility functions for triggering dashboard updates

async def notify_revenue_update(agency_id: int, amount: float):
    """Notify dashboard about revenue update."""
    await manager.send_to_room(f"dashboard_agency_{agency_id}", {
        "type": "revenue_update",
        "amount": amount,
        "timestamp": datetime.utcnow().isoformat()
    })


async def notify_new_message(model_id: int, chat_id: int):
    """Notify dashboard about new message."""
    await manager.send_to_room(f"dashboard_model_{model_id}", {
        "type": "new_message_notification",
        "chat_id": chat_id,
        "timestamp": datetime.utcnow().isoformat()
    })


async def notify_model_status_change(model_id: int, status: str):
    """Notify about model status change."""
    # Get model's agency
    async with AsyncSessionLocal() as db:
        stmt = select(Model.agency_id).where(Model.id == model_id)
        agency_id = await db.scalar(stmt)
        
        if agency_id:
            await manager.send_to_room(f"dashboard_agency_{agency_id}", {
                "type": "model_status_change",
                "model_id": model_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })