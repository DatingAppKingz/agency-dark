"""
Webhook HTTP sender with retry logic
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
import time

from core.logging import get_logger
from .webhook_models import Webhook

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
    """Send webhooks over HTTP"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
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