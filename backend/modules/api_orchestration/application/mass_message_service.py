"""
Mass messaging service with intelligent batching and rate limit management.

Handles sending messages to large numbers of fans while respecting API rate limits
and ensuring reliable delivery.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from core.redis import redis_client
from core.domain.models import ModelProfile, Fan, User, FanClaim
from core.external_api import APIRateLimitError
from modules.analytics.domain.models import AnalyticsEvent

from .orchestrator_v2 import EnhancedAPIOrchestrator
from .routing_service import IntelligentRouter
from ..domain.schemas import (
    DataSource,
    MassMessageRequest,
    MessageRequest,
    MassMessageStatus,
    MassMessageResult
)


logger = logging.getLogger(__name__)


class MessagePriority(str, Enum):
    """Message priority levels for queue management."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class MessageQueueItem:
    """Represents a message in the queue."""
    def __init__(
        self,
        campaign_id: str,
        fan_id: str,
        message_request: MessageRequest,
        priority: MessagePriority = MessagePriority.NORMAL,
        retry_count: int = 0
    ):
        self.id = str(uuid.uuid4())
        self.campaign_id = campaign_id
        self.fan_id = fan_id
        self.message_request = message_request
        self.priority = priority
        self.retry_count = retry_count
        self.created_at = datetime.utcnow()
        self.last_attempt_at: Optional[datetime] = None
        self.error: Optional[str] = None
        

class MassMessageService:
    """Service for handling mass message campaigns."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = EnhancedAPIOrchestrator(db)
        self.router = IntelligentRouter(db)
        self._message_queues: Dict[str, asyncio.Queue] = {}
        self._active_campaigns: Dict[str, MassMessageStatus] = {}
        self._worker_tasks: Dict[str, List[asyncio.Task]] = {}
        
    async def send_mass_message(
        self,
        model_profile: ModelProfile,
        request: MassMessageRequest,
        user: User
    ) -> MassMessageStatus:
        """Initialize and start a mass messaging campaign."""
        campaign_id = str(uuid.uuid4())
        
        # Get target fans based on criteria
        fans = await self._get_target_fans(model_profile, request)
        
        if not fans:
            return MassMessageStatus(
                campaign_id=campaign_id,
                total_recipients=0,
                sent=0,
                failed=0,
                pending=0,
                status="completed",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            
        # Initialize campaign status
        status = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=len(fans),
            sent=0,
            failed=0,
            pending=len(fans),
            status="running",
            created_at=datetime.utcnow()
        )
        
        self._active_campaigns[campaign_id] = status
        
        # Store campaign in Redis for persistence
        await self._store_campaign_status(campaign_id, status)
        
        # Create message queue for this campaign
        queue = asyncio.Queue()
        self._message_queues[campaign_id] = queue
        
        # Enqueue messages with intelligent routing
        for fan in fans:
            # Determine best source for this fan
            source = await self.router.determine_best_source(
                model_profile,
                operation_type="message",
                fan=fan,
                payload_size=len(request.text or "") + len(request.media_ids or []) * 1000,
                features_required=["ppv_messages"] if request.price else None
            )
            
            # Create individual message request
            message_request = MessageRequest(
                fan_id=str(fan.id),
                text=request.text,
                media_ids=request.media_ids,
                price=request.price,
                campaign_id=campaign_id,
                preferred_source=source,
                fallback_enabled=request.fallback_enabled
            )
            
            # Determine priority based on fan value
            priority = self._calculate_message_priority(fan)
            
            # Create queue item
            item = MessageQueueItem(
                campaign_id=campaign_id,
                fan_id=str(fan.id),
                message_request=message_request,
                priority=priority
            )
            
            await queue.put(item)
            
        # Start worker tasks based on rate limits
        await self._start_campaign_workers(campaign_id, model_profile, user)
        
        # Create analytics event
        analytics_event = AnalyticsEvent(
            event_type="mass_message_started",
            user_id=str(user.id),
            metadata={
                "campaign_id": campaign_id,
                "model_id": str(model_profile.id),
                "total_recipients": len(fans),
                "has_price": bool(request.price),
                "price": float(request.price) if request.price else None,
                "criteria": request.recipient_criteria
            },
            timestamp=datetime.utcnow()
        )
        self.db.add(analytics_event)
        await self.db.commit()
        
        return status
        
    async def _get_target_fans(
        self,
        model_profile: ModelProfile,
        request: MassMessageRequest
    ) -> List[Fan]:
        """Get fans matching the targeting criteria."""
        query = select(Fan).where(Fan.model_id == model_profile.id)
        
        # Apply filters based on criteria
        if request.recipient_criteria:
            criteria = request.recipient_criteria
            
            # Subscription status
            if criteria.get("subscription_status"):
                if criteria["subscription_status"] == "active":
                    query = query.where(Fan.is_subscriber == True)
                elif criteria["subscription_status"] == "expired":
                    query = query.where(
                        and_(
                            Fan.is_subscriber == False,
                            Fan.subscribed_at.isnot(None)
                        )
                    )
                    
            # Spending range
            if criteria.get("min_spent") is not None:
                query = query.where(Fan.total_spent >= criteria["min_spent"])
            if criteria.get("max_spent") is not None:
                query = query.where(Fan.total_spent <= criteria["max_spent"])
                
            # Activity
            if criteria.get("last_active_days"):
                cutoff = datetime.utcnow() - timedelta(days=criteria["last_active_days"])
                query = query.where(Fan.last_active_at >= cutoff)
                
            # Segment
            if criteria.get("segment"):
                segment = criteria["segment"]
                if segment == "whales":
                    query = query.where(Fan.total_spent >= 1000)
                elif segment == "engaged":
                    query = query.where(Fan.message_count >= 10)
                elif segment == "new":
                    cutoff = datetime.utcnow() - timedelta(days=30)
                    query = query.where(Fan.created_at >= cutoff)
                    
            # Custom list
            if criteria.get("fan_list_id"):
                # Would need to join with FanList table
                pass
                
        # Limit for safety
        if request.limit:
            query = query.limit(request.limit)
        else:
            query = query.limit(10000)  # Hard limit
            
        result = await self.db.execute(query)
        return list(result.scalars().all())
        
    def _calculate_message_priority(self, fan: Fan) -> MessagePriority:
        """Calculate message priority based on fan value."""
        if fan.total_spent >= 1000:  # Whale
            return MessagePriority.HIGH
        elif fan.total_spent >= 100 or fan.message_count >= 20:  # Engaged
            return MessagePriority.HIGH
        elif fan.is_subscriber:
            return MessagePriority.NORMAL
        else:
            return MessagePriority.LOW
            
    async def _start_campaign_workers(
        self,
        campaign_id: str,
        model_profile: ModelProfile,
        user: User
    ):
        """Start worker tasks for processing campaign messages."""
        # Determine number of workers based on API limits
        # OnlyFans: 60/min, Inflow: 60/min
        # With 2 APIs, we can theoretically send 120/min
        # But we'll be conservative and use 2-4 workers
        
        num_workers = 3
        if model_profile.onlyfans_api_key and model_profile.inflow_api_key:
            num_workers = 4  # More workers if both APIs available
            
        workers = []
        for i in range(num_workers):
            worker = asyncio.create_task(
                self._message_worker(campaign_id, model_profile, user, i)
            )
            workers.append(worker)
            
        self._worker_tasks[campaign_id] = workers
        
    async def _message_worker(
        self,
        campaign_id: str,
        model_profile: ModelProfile,
        user: User,
        worker_id: int
    ):
        """Worker task for processing messages from queue."""
        queue = self._message_queues.get(campaign_id)
        if not queue:
            return
            
        logger.info(f"Worker {worker_id} started for campaign {campaign_id}")
        
        while True:
            try:
                # Check if campaign is still active
                status = self._active_campaigns.get(campaign_id)
                if not status or status.status in ["completed", "cancelled", "failed"]:
                    break
                    
                # Get next message from queue (with timeout)
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Check if queue is empty and campaign should complete
                    if queue.empty() and status.pending == 0:
                        await self._complete_campaign(campaign_id)
                        break
                    continue
                    
                # Process the message
                success = await self._send_single_message(
                    model_profile, item, user
                )
                
                # Update campaign status
                status.pending -= 1
                if success:
                    status.sent += 1
                else:
                    status.failed += 1
                    
                    # Retry logic
                    if item.retry_count < 3:
                        item.retry_count += 1
                        item.last_attempt_at = datetime.utcnow()
                        # Re-queue with lower priority
                        await queue.put(item)
                        status.pending += 1
                        
                # Update status in Redis
                await self._store_campaign_status(campaign_id, status)
                
                # Rate limiting - simple delay between messages
                # Adjust based on available APIs and current rate limit status
                delay = await self._calculate_send_delay(model_profile)
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error in campaign {campaign_id}: {e}")
                
        logger.info(f"Worker {worker_id} finished for campaign {campaign_id}")
        
    async def _send_single_message(
        self,
        model_profile: ModelProfile,
        item: MessageQueueItem,
        user: User
    ) -> bool:
        """Send a single message and return success status."""
        try:
            # Use orchestrator with failover
            result = await self.orchestrator.send_message_with_failover(
                model_profile,
                item.message_request,
                user
            )
            
            # Log successful delivery
            logger.info(
                f"Message sent to fan {item.fan_id} via {result.get('source')} "
                f"in campaign {item.campaign_id}"
            )
            
            return True
            
        except APIRateLimitError as e:
            logger.warning(f"Rate limit hit for fan {item.fan_id}: {e}")
            item.error = f"Rate limit: {str(e)}"
            return False
            
        except Exception as e:
            logger.error(f"Failed to send message to fan {item.fan_id}: {e}")
            item.error = str(e)
            return False
            
    async def _calculate_send_delay(self, model_profile: ModelProfile) -> float:
        """Calculate delay between messages based on rate limits."""
        # Check current rate limit usage
        delays = []
        
        if model_profile.onlyfans_api_key:
            of_usage = await self._get_rate_limit_usage(
                model_profile.id, DataSource.ONLYFANS
            )
            # OnlyFans: 60/min
            if of_usage > 50:  # Getting close to limit
                delays.append(2.0)
            elif of_usage > 40:
                delays.append(1.5)
            else:
                delays.append(1.0)
                
        if model_profile.inflow_api_key:
            if_usage = await self._get_rate_limit_usage(
                model_profile.id, DataSource.INFLOW
            )
            # Inflow: 60/min
            if if_usage > 50:
                delays.append(2.0)
            elif if_usage > 40:
                delays.append(1.5)
            else:
                delays.append(1.0)
                
        # Use the maximum delay to be safe
        return max(delays) if delays else 1.0
        
    async def _get_rate_limit_usage(
        self,
        model_id: str,
        source: DataSource
    ) -> int:
        """Get current rate limit usage for a source."""
        rate_key = f"rate_limit:{source.value}:{model_id}"
        usage = await redis_client.get(rate_key)
        return int(usage) if usage else 0
        
    async def _complete_campaign(self, campaign_id: str):
        """Mark campaign as completed."""
        status = self._active_campaigns.get(campaign_id)
        if status:
            status.status = "completed"
            status.completed_at = datetime.utcnow()
            
            # Store final status
            await self._store_campaign_status(campaign_id, status)
            
            # Create analytics event
            analytics_event = AnalyticsEvent(
                event_type="mass_message_completed",
                metadata={
                    "campaign_id": campaign_id,
                    "total_recipients": status.total_recipients,
                    "sent": status.sent,
                    "failed": status.failed,
                    "duration_seconds": (
                        status.completed_at - status.created_at
                    ).total_seconds()
                },
                timestamp=datetime.utcnow()
            )
            self.db.add(analytics_event)
            await self.db.commit()
            
            # Clean up
            if campaign_id in self._message_queues:
                del self._message_queues[campaign_id]
            if campaign_id in self._worker_tasks:
                # Cancel any remaining workers
                for task in self._worker_tasks[campaign_id]:
                    if not task.done():
                        task.cancel()
                del self._worker_tasks[campaign_id]
                
            logger.info(
                f"Campaign {campaign_id} completed: "
                f"{status.sent} sent, {status.failed} failed"
            )
            
    async def get_campaign_status(self, campaign_id: str) -> Optional[MassMessageStatus]:
        """Get current status of a campaign."""
        # Check active campaigns first
        if campaign_id in self._active_campaigns:
            return self._active_campaigns[campaign_id]
            
        # Check Redis for completed campaigns
        cache_key = f"mass_message_campaign:{campaign_id}"
        data = await redis_client.get(cache_key)
        if data:
            import json
            status_data = json.loads(data)
            return MassMessageStatus(**status_data)
            
        return None
        
    async def cancel_campaign(self, campaign_id: str) -> bool:
        """Cancel an active campaign."""
        status = self._active_campaigns.get(campaign_id)
        if not status or status.status != "running":
            return False
            
        status.status = "cancelled"
        status.completed_at = datetime.utcnow()
        
        # Store status
        await self._store_campaign_status(campaign_id, status)
        
        # Cancel workers
        if campaign_id in self._worker_tasks:
            for task in self._worker_tasks[campaign_id]:
                if not task.done():
                    task.cancel()
                    
        # Clear queue
        if campaign_id in self._message_queues:
            queue = self._message_queues[campaign_id]
            # Count remaining messages
            remaining = 0
            while not queue.empty():
                try:
                    await queue.get_nowait()
                    remaining += 1
                except asyncio.QueueEmpty:
                    break
                    
            status.pending = 0
            status.failed += remaining
            
        logger.info(f"Campaign {campaign_id} cancelled")
        return True
        
    async def _store_campaign_status(self, campaign_id: str, status: MassMessageStatus):
        """Store campaign status in Redis."""
        cache_key = f"mass_message_campaign:{campaign_id}"
        data = status.model_dump()
        # Convert datetime to ISO format
        for key in ["created_at", "completed_at"]:
            if data.get(key):
                data[key] = data[key].isoformat()
                
        import json
        await redis_client.setex(
            cache_key,
            86400,  # 24 hour TTL
            json.dumps(data)
        )
        
    async def get_campaign_history(
        self,
        model_profile: ModelProfile,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get history of mass message campaigns for a model."""
        result = await self.db.execute(
            select(AnalyticsEvent).where(
                and_(
                    AnalyticsEvent.event_type.in_([
                        "mass_message_started",
                        "mass_message_completed"
                    ]),
                    AnalyticsEvent.metadata["model_id"].astext == str(model_profile.id)
                )
            ).order_by(AnalyticsEvent.timestamp.desc()).limit(limit * 2)
        )
        
        events = result.scalars().all()
        
        # Group by campaign_id
        campaigns = {}
        for event in events:
            campaign_id = event.metadata.get("campaign_id")
            if not campaign_id:
                continue
                
            if campaign_id not in campaigns:
                campaigns[campaign_id] = {}
                
            if event.event_type == "mass_message_started":
                campaigns[campaign_id]["started"] = event
            else:
                campaigns[campaign_id]["completed"] = event
                
        # Build history
        history = []
        for campaign_id, events in campaigns.items():
            started = events.get("started")
            completed = events.get("completed")
            
            if started:
                item = {
                    "campaign_id": campaign_id,
                    "created_at": started.timestamp,
                    "total_recipients": started.metadata.get("total_recipients", 0),
                    "has_price": started.metadata.get("has_price", False),
                    "price": started.metadata.get("price"),
                    "status": "completed" if completed else "running"
                }
                
                if completed:
                    item.update({
                        "completed_at": completed.timestamp,
                        "sent": completed.metadata.get("sent", 0),
                        "failed": completed.metadata.get("failed", 0),
                        "duration_seconds": completed.metadata.get("duration_seconds", 0)
                    })
                    
                history.append(item)
                
        # Sort by created_at desc and limit
        history.sort(key=lambda x: x["created_at"], reverse=True)
        return history[:limit]