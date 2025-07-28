"""
Enhanced external API clients with circuit breakers
"""
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from core.resilience import circuit_breaker, DistributedCircuitBreaker
from core.logging import logger
from core.config import settings


class EnhancedOnlyFansClient:
    """OnlyFans API client with circuit breaker protection"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://onlyfans.com/api/v2"
        
        # Create circuit breaker for this client
        self.circuit_breaker = DistributedCircuitBreaker(
            name="onlyfans_api",
            failure_threshold=3,
            recovery_timeout=120,  # 2 minutes
            expected_exception=aiohttp.ClientError,
            success_threshold=2
        )
    
    @circuit_breaker(name="onlyfans_transactions", failure_threshold=5, recovery_timeout=300)
    async def get_transactions(self, since: datetime, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get transactions with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-API-Secret": self.api_secret
            }
            
            params = {
                "since": since.isoformat(),
                "limit": limit
            }
            
            async with session.get(
                f"{self.base_url}/transactions",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("transactions", [])
    
    @circuit_breaker(name="onlyfans_messages", failure_threshold=3, recovery_timeout=180)
    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get messages with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-API-Secret": self.api_secret
            }
            
            async with session.get(
                f"{self.base_url}/chats/{conversation_id}/messages",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("messages", [])
    
    async def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for monitoring"""
        from core.resilience import CircuitBreakerRegistry
        
        status = {}
        for name, breaker in CircuitBreakerRegistry.get_all().items():
            if name.startswith("onlyfans"):
                status[name] = breaker.get_metrics()
        
        return status


class EnhancedInflowClient:
    """Inflow API client with circuit breaker protection"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.inflow.com/v1"
    
    @circuit_breaker(
        name="inflow_transactions",
        failure_threshold=4,
        recovery_timeout=240,
        expected_exception=(aiohttp.ClientError, asyncio.TimeoutError)
    )
    async def get_recent_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent transactions with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }
            
            async with session.get(
                f"{self.base_url}/transactions",
                headers=headers,
                params={"limit": limit, "sort": "created_desc"},
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("data", [])
    
    @circuit_breaker(
        name="inflow_webhooks",
        failure_threshold=2,
        recovery_timeout=60
    )
    async def register_webhook(self, url: str, events: List[str]) -> Dict[str, Any]:
        """
        Register webhook with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "url": url,
                "events": events
            }
            
            async with session.post(
                f"{self.base_url}/webhooks",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response.raise_for_status()
                return await response.json()


class EnhancedStripeClient:
    """Stripe API client with circuit breaker protection"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.stripe.com/v1"
    
    @circuit_breaker(
        name="stripe_charges",
        failure_threshold=5,
        recovery_timeout=180,
        success_threshold=3
    )
    async def list_charges(self, created: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """
        List charges with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Stripe-Version": "2023-10-16"
            }
            
            params = {}
            if created:
                params["created"] = created
            
            async with session.get(
                f"{self.base_url}/charges",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("data", [])
    
    @circuit_breaker(
        name="stripe_customers",
        failure_threshold=3,
        recovery_timeout=120
    )
    async def list_customers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List customers with circuit breaker protection
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Stripe-Version": "2023-10-16"
            }
            
            async with session.get(
                f"{self.base_url}/customers",
                headers=headers,
                params={"limit": limit},
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("data", [])


# Factory functions with fallback support
async def create_onlyfans_client_with_fallback(
    api_key: str,
    api_secret: str,
    fallback_url: Optional[str] = None
) -> EnhancedOnlyFansClient:
    """
    Create OnlyFans client with fallback configuration
    """
    client = EnhancedOnlyFansClient(api_key, api_secret)
    
    if fallback_url:
        # Configure fallback URL
        client.fallback_url = fallback_url
    
    return client


# Circuit breaker monitoring
class CircuitBreakerMonitor:
    """Monitor all API circuit breakers"""
    
    @staticmethod
    async def get_all_statuses() -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        from core.resilience import CircuitBreakerRegistry
        
        statuses = {}
        metrics = CircuitBreakerRegistry.get_metrics()
        
        for name, metric in metrics.items():
            statuses[name] = {
                'state': metric['state'],
                'success_rate': metric['success_rate'],
                'failure_count': metric['failure_count'],
                'last_state_change': metric['state_changes'][-1] if metric['state_changes'] else None
            }
        
        return statuses
    
    @staticmethod
    async def reset_circuit_breaker(name: str) -> bool:
        """Reset a specific circuit breaker"""
        from core.resilience import CircuitBreakerRegistry
        
        breaker = CircuitBreakerRegistry.get(name)
        if breaker:
            await breaker.reset()
            return True
        return False
    
    @staticmethod
    async def get_health_report() -> Dict[str, Any]:
        """Get health report for all external APIs"""
        statuses = await CircuitBreakerMonitor.get_all_statuses()
        
        # Calculate overall health
        total_apis = len(statuses)
        healthy_apis = sum(1 for s in statuses.values() if s['state'] == 'closed')
        degraded_apis = sum(1 for s in statuses.values() if s['state'] == 'half_open')
        down_apis = sum(1 for s in statuses.values() if s['state'] == 'open')
        
        overall_health = 'healthy'
        if down_apis > 0:
            overall_health = 'degraded' if down_apis < total_apis else 'critical'
        elif degraded_apis > 0:
            overall_health = 'warning'
        
        return {
            'overall_health': overall_health,
            'total_apis': total_apis,
            'healthy_apis': healthy_apis,
            'degraded_apis': degraded_apis,
            'down_apis': down_apis,
            'api_statuses': statuses,
            'timestamp': datetime.utcnow().isoformat()
        }