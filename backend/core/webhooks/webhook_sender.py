"""
Webhook HTTP sender with retry logic
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import time
import random

from core.logging import get_logger
from .webhook_models import Webhook, WebhookDelivery, DeliveryStatus

logger = get_logger(__name__)


class WebhookResponse:
    """Webhook HTTP response"""
    def __init__(
        self,
        status_code: int,
        headers: Dict[str, str],
        text: str,
        elapsed_ms: int
    ):
        self.status_code = status_code
        self.headers = headers
        self.text = text
        self.elapsed_ms = elapsed_ms


class WebhookSender:
    """Send webhooks over HTTP with exponential backoff retry"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Exponential backoff configuration
        self.base_delay = 1  # Initial delay in seconds
        self.max_delay = 300  # Maximum delay in seconds (5 minutes)
        self.multiplier = 2  # Exponential multiplier
        self.jitter = 0.1  # Jitter factor (10%)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100)
            )
        return self.session
    
    async def send(
        self,
        webhook: Webhook,
        payload: Dict[str, Any],
        timeout: int = 30
    ) -> WebhookResponse:
        """Send webhook payload"""
        session = await self._get_session()
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AgencyDark-Webhook/1.0",
            "X-Webhook-ID": webhook.id,
            "X-Webhook-Timestamp": str(int(datetime.utcnow().timestamp()))
        }
        
        # Add custom headers
        if webhook.custom_headers:
            headers.update(webhook.custom_headers)
        
        # Add signature
        from .webhook_manager import webhook_manager
        payload_str = json.dumps(payload, sort_keys=True)
        signature = webhook_manager.generate_signature(webhook, payload_str)
        headers["X-Webhook-Signature"] = signature
        
        # Send request
        start_time = time.time()
        
        try:
            async with session.post(
                webhook.url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=True  # Verify SSL certificates
            ) as response:
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Read response body (limited to prevent memory issues)
                text = await response.text()
                if len(text) > 10000:
                    text = text[:10000] + "... (truncated)"
                
                # Check status
                response.raise_for_status()
                
                return WebhookResponse(
                    status_code=response.status,
                    headers=dict(response.headers),
                    text=text,
                    elapsed_ms=elapsed_ms
                )
                
        except aiohttp.ClientResponseError as e:
            # HTTP error (4xx, 5xx)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            raise Exception(
                f"HTTP {e.status}: {e.message}. "
                f"Response: {e.history[0].text if e.history else 'N/A'}"
            )
            
        except aiohttp.ClientConnectorError as e:
            # Connection error
            raise Exception(f"Connection error: {e}")
            
        except asyncio.TimeoutError:
            # Timeout
            raise Exception(f"Request timeout after {timeout} seconds")
            
        except Exception as e:
            # Other errors
            raise Exception(f"Webhook delivery failed: {e}")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for exponential backoff with jitter
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = min(
            self.base_delay * (self.multiplier ** attempt),
            self.max_delay
        )
        
        # Add jitter to prevent thundering herd
        jitter_range = delay * self.jitter
        jitter = random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay + jitter)
    
    async def send_with_retry(
        self,
        webhook: Webhook,
        payload: Dict[str, Any],
        delivery: Optional[WebhookDelivery] = None,
        max_attempts: Optional[int] = None
    ) -> Tuple[WebhookResponse, int]:
        """
        Send webhook with exponential backoff retry
        
        Args:
            webhook: Webhook configuration
            payload: Payload to send
            delivery: Optional delivery record to update
            max_attempts: Maximum number of attempts (uses webhook config if not specified)
            
        Returns:
            Tuple of (response, attempts)
        """
        max_attempts = max_attempts or webhook.max_retries + 1
        attempts = 0
        last_error = None
        
        while attempts < max_attempts:
            try:
                response = await self.send(
                    webhook,
                    payload,
                    timeout=webhook.timeout_seconds
                )
                
                # Success!
                return response, attempts + 1
                
            except Exception as e:
                last_error = str(e)
                attempts += 1
                
                if attempts < max_attempts:
                    # Calculate delay for next attempt
                    delay = self.calculate_delay(attempts - 1)
                    
                    logger.warning(
                        f"Webhook {webhook.id} delivery failed (attempt {attempts}/{max_attempts}). "
                        f"Retrying in {delay:.1f}s. Error: {last_error}"
                    )
                    
                    # Update delivery record if provided
                    if delivery:
                        delivery.attempts = attempts
                        delivery.error_message = last_error
                        delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                else:
                    # Final failure
                    logger.error(
                        f"Webhook {webhook.id} delivery failed after {attempts} attempts. "
                        f"Error: {last_error}"
                    )
                    
                    raise Exception(f"Webhook delivery failed after {attempts} attempts: {last_error}")
    
    async def test_webhook(
        self,
        url: str,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """Test webhook endpoint"""
        session = await self._get_session()
        
        # Test payload
        test_payload = {
            "event": "webhook.test",
            "event_id": "test_" + str(int(datetime.utcnow().timestamp())),
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "message": "This is a test webhook from AgencyDark"
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AgencyDark-Webhook/1.0",
            "X-Webhook-Test": "true"
        }
        
        try:
            start_time = time.time()
            
            async with session.post(
                url,
                json=test_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                return {
                    "success": response.status < 400,
                    "status_code": response.status,
                    "response_time_ms": elapsed_ms,
                    "headers": dict(response.headers),
                    "body": await response.text()
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": None,
                "response_time_ms": None
            }
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()