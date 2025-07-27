"""
Webhook handling for external APIs
"""
import hmac
import hashlib
import json
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import asyncio
from abc import ABC, abstractmethod

from fastapi import Request, HTTPException
from pydantic import BaseModel

from .logging import APILogger


class WebhookEvent(BaseModel):
    """Base webhook event model"""
    id: str
    type: str
    timestamp: datetime
    data: Dict[str, Any]
    raw_payload: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookHandler(ABC):
    """Abstract base class for webhook handlers"""
    
    def __init__(self, api_name: str, logger: Optional[APILogger] = None):
        self.api_name = api_name
        self.logger = logger or APILogger(f"{api_name}_webhooks")
        self.event_handlers: Dict[str, Callable[[WebhookEvent], Awaitable[None]]] = {}
        
    @abstractmethod
    async def verify_signature(
        self, 
        payload: bytes, 
        signature: str, 
        secret: str
    ) -> bool:
        """Verify webhook signature"""
        pass
        
    @abstractmethod
    def parse_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse webhook payload into event"""
        pass
        
    def register_handler(
        self, 
        event_type: str, 
        handler: Callable[[WebhookEvent], Awaitable[None]]
    ):
        """Register event handler"""
        self.event_handlers[event_type] = handler
        self.logger.logger.info(f"Registered handler for event type: {event_type}")
        
    async def handle_webhook(
        self, 
        request: Request, 
        secret: str
    ) -> Dict[str, Any]:
        """Handle incoming webhook request"""
        # Get request data
        body = await request.body()
        headers = dict(request.headers)
        
        # Log incoming webhook
        self.logger.log_request(
            "POST",
            str(request.url),
            data=None,  # Don't log raw body
            headers=headers
        )
        
        # Verify signature
        signature = self.get_signature_header(headers)
        if not signature:
            self.logger.log_error("POST", str(request.url), ValueError("Missing signature"))
            raise HTTPException(status_code=401, detail="Missing signature")
            
        try:
            is_valid = await self.verify_signature(body, signature, secret)
            if not is_valid:
                self.logger.log_error("POST", str(request.url), ValueError("Invalid signature"))
                raise HTTPException(status_code=401, detail="Invalid signature")
        except Exception as e:
            self.logger.log_error("POST", str(request.url), e)
            raise HTTPException(status_code=401, detail="Signature verification failed")
            
        # Parse payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            self.logger.log_error("POST", str(request.url), e)
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
            
        # Parse event
        try:
            event = self.parse_event(payload)
            event.raw_payload = body.decode('utf-8')
            event.headers = headers
        except Exception as e:
            self.logger.log_error("POST", str(request.url), e)
            raise HTTPException(status_code=400, detail="Invalid event format")
            
        # Log parsed event
        self.logger.logger.info(
            f"Webhook event received: {event.type}",
            event_id=event.id,
            event_type=event.type,
            api=self.api_name
        )
        
        # Handle event
        handler = self.event_handlers.get(event.type)
        if handler:
            try:
                await handler(event)
                self.logger.logger.info(
                    f"Webhook event processed: {event.type}",
                    event_id=event.id,
                    event_type=event.type,
                    api=self.api_name
                )
            except Exception as e:
                self.logger.log_error("POST", str(request.url), e)
                # Don't raise - acknowledge receipt even if processing fails
                self.logger.logger.error(
                    f"Webhook event processing failed: {event.type}",
                    event_id=event.id,
                    event_type=event.type,
                    api=self.api_name,
                    exc_info=True
                )
        else:
            self.logger.logger.warning(
                f"No handler for webhook event: {event.type}",
                event_id=event.id,
                event_type=event.type,
                api=self.api_name
            )
            
        # Return acknowledgment
        return {"status": "ok", "event_id": event.id}
        
    @abstractmethod
    def get_signature_header(self, headers: Dict[str, str]) -> Optional[str]:
        """Get signature from headers"""
        pass


class HMACWebhookHandler(WebhookHandler):
    """HMAC-based webhook handler"""
    
    def __init__(
        self, 
        api_name: str, 
        signature_header: str = "x-signature",
        hash_algorithm: str = "sha256",
        logger: Optional[APILogger] = None
    ):
        super().__init__(api_name, logger)
        self.signature_header = signature_header.lower()
        self.hash_algorithm = hash_algorithm
        
    async def verify_signature(
        self, 
        payload: bytes, 
        signature: str, 
        secret: str
    ) -> bool:
        """Verify HMAC signature"""
        # Compute expected signature
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            getattr(hashlib, self.hash_algorithm)
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(expected, signature)
        
    def get_signature_header(self, headers: Dict[str, str]) -> Optional[str]:
        """Get signature from headers"""
        # Convert headers to lowercase for comparison
        headers_lower = {k.lower(): v for k, v in headers.items()}
        return headers_lower.get(self.signature_header)


class WebhookProcessor:
    """Process webhooks asynchronously"""
    
    def __init__(self, max_workers: int = 10):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_workers = max_workers
        self.workers: list[asyncio.Task] = []
        self.running = False
        
    async def start(self):
        """Start webhook processors"""
        self.running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
            
    async def stop(self):
        """Stop webhook processors"""
        self.running = False
        
        # Wait for queue to be empty
        await self.queue.join()
        
        # Cancel workers
        for worker in self.workers:
            worker.cancel()
            
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
    async def _worker(self, name: str):
        """Worker to process webhooks"""
        while self.running:
            try:
                # Get webhook from queue
                handler, event = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=1.0
                )
                
                # Process webhook
                try:
                    await handler(event)
                except Exception as e:
                    # Log error but continue processing
                    print(f"Worker {name} error processing webhook: {e}")
                    
                # Mark as done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
                
    async def add_webhook(
        self, 
        handler: Callable[[WebhookEvent], Awaitable[None]], 
        event: WebhookEvent
    ):
        """Add webhook to processing queue"""
        await self.queue.put((handler, event))