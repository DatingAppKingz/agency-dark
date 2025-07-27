"""
Socket.IO namespace for notifications and real-time analytics.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import asyncio

from socketio import AsyncNamespace
from sqlalchemy import select, and_, func

from core.database import AsyncSessionLocal
from core.redis import redis_client
from core.domain.models import User, ModelProfile, Agency, UserRole


logger = logging.getLogger(__name__)


class NotificationNamespace(AsyncNamespace):
    """Socket.IO namespace for notifications and live updates."""
    
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.active_subscriptions = {}  # Track active metric subscriptions
        self._subscription_tasks = {}  # Track running tasks
    
    async def on_connect(self, sid: str, environ: dict):
        """Handle namespace connection."""
        session = await self.get_session(sid)
        if not session:
            return False
        
        logger.info(f"User {session['username']} connected to notifications namespace")
        
        # Start listening to Redis notifications for this user's agency
        if session['agency_id']:
            asyncio.create_task(
                self._listen_to_notifications(sid, session['agency_id'])
            )
        
        return True
    
    async def on_disconnect(self, sid: str):
        """Handle disconnection."""
        # Cancel any active subscriptions
        if sid in self._subscription_tasks:
            for task in self._subscription_tasks[sid].values():
                task.cancel()
            del self._subscription_tasks[sid]
        
        if sid in self.active_subscriptions:
            del self.active_subscriptions[sid]
    
    async def on_subscribe_metrics(self, sid: str, data: Dict[str, Any]):
        """Subscribe to real-time metrics updates."""
        session = await self.get_session(sid)
        if not session:
            return
        
        model_id = data.get('model_id')
        metrics = data.get('metrics', [])  # List of metric types to subscribe to
        interval = data.get('interval', 5)  # Update interval in seconds
        
        if not model_id or not metrics:
            await self.emit('error', {
                'message': 'Model ID and metrics list required'
            }, room=sid)
            return
        
        # Verify access to model
        async with AsyncSessionLocal() as db:
            model = await db.get(ModelProfile, model_id)
            if not model:
                await self.emit('error', {
                    'message': 'Model not found'
                }, room=sid)
                return
            
            # Check permissions
            user = await db.get(User, session['user_id'])
            if not self._has_model_access(user, model):
                await self.emit('error', {
                    'message': 'Access denied to this model'
                }, room=sid)
                return
        
        # Store subscription
        if sid not in self.active_subscriptions:
            self.active_subscriptions[sid] = {}
            self._subscription_tasks[sid] = {}
        
        self.active_subscriptions[sid][model_id] = {
            'metrics': metrics,
            'interval': interval
        }
        
        # Start metric streaming task
        task_key = f"{model_id}_metrics"
        if task_key in self._subscription_tasks[sid]:
            self._subscription_tasks[sid][task_key].cancel()
        
        self._subscription_tasks[sid][task_key] = asyncio.create_task(
            self._stream_metrics(sid, model_id, metrics, interval)
        )
        
        await self.emit('subscribed_metrics', {
            'model_id': model_id,
            'metrics': metrics,
            'interval': interval
        }, room=sid)
    
    async def on_unsubscribe_metrics(self, sid: str, data: Dict[str, Any]):
        """Unsubscribe from metrics updates."""
        model_id = data.get('model_id')
        
        if sid in self.active_subscriptions and model_id in self.active_subscriptions[sid]:
            del self.active_subscriptions[sid][model_id]
            
            # Cancel streaming task
            task_key = f"{model_id}_metrics"
            if sid in self._subscription_tasks and task_key in self._subscription_tasks[sid]:
                self._subscription_tasks[sid][task_key].cancel()
                del self._subscription_tasks[sid][task_key]
            
            await self.emit('unsubscribed_metrics', {
                'model_id': model_id
            }, room=sid)
    
    async def on_subscribe_events(self, sid: str, data: Dict[str, Any]):
        """Subscribe to real-time events (tips, new subscribers, etc.)."""
        session = await self.get_session(sid)
        if not session:
            return
        
        event_types = data.get('event_types', [])
        model_ids = data.get('model_ids', [])  # Optional: specific models
        
        if not event_types:
            await self.emit('error', {
                'message': 'Event types required'
            }, room=sid)
            return
        
        # Join event rooms based on permissions
        if session['role'] == UserRole.SUPER_ADMIN:
            # Super admin gets all events
            self.enter_room(sid, 'events:all')
        elif session['agency_id']:
            # Agency members get agency events
            self.enter_room(sid, f"events:agency:{session['agency_id']}")
            
            # Join specific model event rooms if requested
            if model_ids:
                for model_id in model_ids:
                    # Verify model belongs to agency
                    async with AsyncSessionLocal() as db:
                        model = await db.get(ModelProfile, model_id)
                        if model and str(model.agency_id) == session['agency_id']:
                            self.enter_room(sid, f"events:model:{model_id}")
        
        await self.emit('subscribed_events', {
            'event_types': event_types,
            'model_ids': model_ids
        }, room=sid)
    
    async def _stream_metrics(
        self,
        sid: str,
        model_id: str,
        metrics: List[str],
        interval: int
    ):
        """Stream real-time metrics for a model."""
        try:
            while True:
                # Get current metrics
                metric_data = await self._get_live_metrics(model_id, metrics)
                
                # Send to client
                await self.emit('metrics_update', {
                    'model_id': model_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'data': metric_data
                }, room=sid)
                
                # Wait for next interval
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Metric streaming cancelled for {sid}")
        except Exception as e:
            logger.error(f"Error streaming metrics: {e}")
            await self.emit('error', {
                'message': 'Metric streaming error'
            }, room=sid)
    
    async def _get_live_metrics(
        self,
        model_id: str,
        metrics: List[str]
    ) -> Dict[str, Any]:
        """Get live metrics for a model."""
        metric_data = {}
        
        async with AsyncSessionLocal() as db:
            model = await db.get(ModelProfile, model_id)
            if not model:
                return metric_data
            
            # Get metrics based on requested types
            if 'revenue_today' in metrics:
                # Get today's revenue from cache or calculate
                cache_key = f"metrics:revenue_today:{model_id}"
                cached = await redis_client.get(cache_key)
                
                if cached:
                    metric_data['revenue_today'] = float(cached)
                else:
                    # Calculate from database
                    # This is a placeholder - would query actual transaction data
                    metric_data['revenue_today'] = 0.0
                    
                    # Cache for 5 minutes
                    await redis_client.setex(cache_key, 300, str(metric_data['revenue_today']))
            
            if 'active_subscribers' in metrics:
                from core.domain.models import Fan
                result = await db.execute(
                    select(func.count(Fan.id)).where(
                        and_(
                            Fan.model_id == model_id,
                            Fan.is_subscriber == True,
                            Fan.is_paying == True
                        )
                    )
                )
                metric_data['active_subscribers'] = result.scalar()
            
            if 'messages_today' in metrics:
                # Get today's message count
                cache_key = f"metrics:messages_today:{model_id}"
                cached = await redis_client.get(cache_key)
                
                if cached:
                    metric_data['messages_today'] = int(cached)
                else:
                    # This would query actual message data
                    metric_data['messages_today'] = 0
                    await redis_client.setex(cache_key, 300, str(metric_data['messages_today']))
            
            if 'online_chatters' in metrics:
                # Count online chatters for this model
                # This would check active Socket.IO connections
                metric_data['online_chatters'] = 0
            
            if 'unclaimed_fans' in metrics:
                from core.domain.models import Fan, FanClaim
                # Count fans without active claims
                result = await db.execute(
                    select(func.count(Fan.id)).where(
                        and_(
                            Fan.model_id == model_id,
                            Fan.is_subscriber == True,
                            ~Fan.id.in_(
                                select(FanClaim.fan_id).where(
                                    FanClaim.is_active == True
                                )
                            )
                        )
                    )
                )
                metric_data['unclaimed_fans'] = result.scalar()
        
        return metric_data
    
    async def _listen_to_notifications(self, sid: str, agency_id: str):
        """Listen to Redis pub/sub for notifications."""
        try:
            # Subscribe to agency notification channel
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"notifications:{agency_id}")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        notification = json.loads(message['data'])
                        
                        # Send to client based on notification type
                        if notification['type'] == 'new_subscriber':
                            await self.emit('new_subscriber', notification, room=sid)
                        elif notification['type'] == 'tip_received':
                            await self.emit('tip_received', notification, room=sid)
                        elif notification['type'] == 'new_message':
                            await self.emit('new_message_notification', notification, room=sid)
                        elif notification['type'] == 'subscriber_expired':
                            await self.emit('subscriber_expired', notification, room=sid)
                        elif notification['type'] == 'post_purchased':
                            await self.emit('post_purchased', notification, room=sid)
                        
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse notification: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error processing notification: {e}")
                        
        except asyncio.CancelledError:
            await pubsub.unsubscribe(f"notifications:{agency_id}")
            await pubsub.close()
        except Exception as e:
            logger.error(f"Error in notification listener: {e}")
    
    def _has_model_access(self, user: User, model: ModelProfile) -> bool:
        """Check if user has access to a model."""
        if user.role == UserRole.SUPER_ADMIN:
            return True
        elif user.role == UserRole.AGENCY_OWNER:
            return model.agency_id == user.agency_id
        elif user.role == UserRole.MODEL:
            return model.user_id == user.id
        elif user.role in [UserRole.AGENCY_MEMBER, UserRole.CHATTER, UserRole.AGENCY_MEMBER]:
            return model.agency_id == user.agency_id
        return False


class DashboardNamespace(AsyncNamespace):
    """Socket.IO namespace for dashboard-specific updates."""
    
    async def on_connect(self, sid: str, environ: dict):
        """Handle dashboard connection."""
        session = await self.get_session(sid)
        if not session:
            return False
        
        logger.info(f"User {session['username']} connected to dashboard")
        
        # Join dashboard room based on role
        if session['role'] == UserRole.SUPER_ADMIN:
            self.enter_room(sid, 'dashboard:super_admin')
        elif session['agency_id']:
            self.enter_room(sid, f"dashboard:agency:{session['agency_id']}")
        
        return True
    
    async def on_request_summary(self, sid: str, data: Dict[str, Any]):
        """Request dashboard summary data."""
        session = await self.get_session(sid)
        if not session:
            return
        
        period = data.get('period', 'today')  # today, week, month
        
        summary_data = await self._get_dashboard_summary(
            session['user_id'],
            session['agency_id'],
            session['role'],
            period
        )
        
        await self.emit('dashboard_summary', summary_data, room=sid)
    
    async def _get_dashboard_summary(
        self,
        user_id: str,
        agency_id: Optional[str],
        role: str,
        period: str
    ) -> Dict[str, Any]:
        """Get dashboard summary data."""
        summary = {
            'period': period,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        async with AsyncSessionLocal() as db:
            if role == UserRole.SUPER_ADMIN:
                # Get platform-wide stats
                from core.domain.models import Agency, ModelProfile, Fan
                
                agencies_count = await db.execute(select(func.count(Agency.id)))
                models_count = await db.execute(select(func.count(ModelProfile.id)))
                fans_count = await db.execute(select(func.count(Fan.id)))
                
                summary.update({
                    'total_agencies': agencies_count.scalar(),
                    'total_models': models_count.scalar(),
                    'total_fans': fans_count.scalar(),
                    'platform_revenue': 0.0  # TODO: Calculate
                })
                
            elif agency_id:
                # Get agency-specific stats
                from core.domain.models import ModelProfile, Fan
                
                models_count = await db.execute(
                    select(func.count(ModelProfile.id)).where(
                        ModelProfile.agency_id == agency_id
                    )
                )
                
                # Get total fans across all agency models
                fans_count = await db.execute(
                    select(func.count(Fan.id)).where(
                        Fan.model_id.in_(
                            select(ModelProfile.id).where(
                                ModelProfile.agency_id == agency_id
                            )
                        )
                    )
                )
                
                summary.update({
                    'total_models': models_count.scalar(),
                    'total_fans': fans_count.scalar(),
                    'agency_revenue': 0.0,  # TODO: Calculate
                    'active_chatters': 0  # TODO: Count active chatters
                })
        
        return summary


async def send_notification(event_type: str, data: Dict[str, Any]):
    """
    Send a notification via Redis pub/sub.
    
    This is a helper function for other modules to send notifications.
    """
    try:
        # Determine channel based on data
        channel = None
        if 'agency_id' in data:
            channel = f"notifications:{data['agency_id']}"
        elif 'model_id' in data:
            # Look up agency_id from model_id
            async with AsyncSessionLocal() as db:
                model = await db.get(ModelProfile, data['model_id'])
                if model:
                    channel = f"notifications:{model.agency_id}"
        
        if channel:
            notification = {
                'type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                **data
            }
            await redis_client.publish(channel, json.dumps(notification))
            logger.info(f"Sent notification: {event_type} to {channel}")
        else:
            logger.warning(f"Could not determine channel for notification: {event_type}")
            
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")