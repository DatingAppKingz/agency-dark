"""
Fan claiming mechanism for exclusive chatter communication.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from backend.core.redis import redis_client
from backend.core.database import AsyncSessionLocal
from backend.core.domain.models import Fan, FanClaim, User, ModelProfile


logger = logging.getLogger(__name__)


class ClaimManager:
    """Manages fan claiming for exclusive communication."""
    
    CLAIM_DURATION_HOURS = 2  # Default claim duration
    CLAIM_KEY_PREFIX = "fan_claim:"
    ACTIVE_CLAIMS_KEY = "active_claims:"
    
    async def claim_fan(
        self,
        fan_id: str,
        chatter_id: str,
        model_id: str,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Claim a fan for exclusive communication.
        
        Returns:
            Dict with claim details or error information
        """
        duration = duration_hours or self.CLAIM_DURATION_HOURS
        
        async with AsyncSessionLocal() as db:
            # Check if fan exists
            fan = await db.get(Fan, fan_id)
            if not fan or str(fan.model_id) != model_id:
                return {
                    'success': False,
                    'error': 'Fan not found or belongs to different model'
                }
            
            # Check for existing active claim
            existing_claim = await db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.fan_id == fan_id,
                        FanClaim.is_active == True
                    )
                )
            )
            existing = existing_claim.scalar_one_or_none()
            
            if existing:
                if str(existing.chatter_id) == chatter_id:
                    # Extend existing claim
                    existing.expires_at = datetime.utcnow() + timedelta(hours=duration)
                    await db.commit()
                    
                    # Update Redis
                    await self._update_redis_claim(fan_id, chatter_id, existing.expires_at)
                    
                    return {
                        'success': True,
                        'claim_id': str(existing.id),
                        'expires_at': existing.expires_at.isoformat(),
                        'extended': True
                    }
                else:
                    # Fan already claimed by someone else
                    chatter = await db.get(User, existing.chatter_id)
                    return {
                        'success': False,
                        'error': 'Fan already claimed',
                        'claimed_by': chatter.username if chatter else 'Unknown',
                        'expires_at': existing.expires_at.isoformat()
                    }
            
            # Create new claim
            new_claim = FanClaim(
                fan_id=fan_id,
                chatter_id=chatter_id,
                model_id=model_id,
                claimed_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=duration),
                is_active=True,
                claimed_by_model=False
            )
            db.add(new_claim)
            await db.commit()
            
            # Update Redis
            await self._update_redis_claim(fan_id, chatter_id, new_claim.expires_at)
            
            # Notify other chatters
            await self._notify_claim_change(
                model_id,
                fan_id,
                chatter_id,
                'claimed'
            )
            
            return {
                'success': True,
                'claim_id': str(new_claim.id),
                'expires_at': new_claim.expires_at.isoformat(),
                'extended': False
            }
    
    async def release_claim(
        self,
        fan_id: str,
        chatter_id: str
    ) -> Dict[str, Any]:
        """Release a fan claim."""
        async with AsyncSessionLocal() as db:
            # Find active claim
            result = await db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.fan_id == fan_id,
                        FanClaim.chatter_id == chatter_id,
                        FanClaim.is_active == True
                    )
                )
            )
            claim = result.scalar_one_or_none()
            
            if not claim:
                return {
                    'success': False,
                    'error': 'No active claim found'
                }
            
            # Release the claim
            claim.is_active = False
            claim.released_at = datetime.utcnow()
            await db.commit()
            
            # Remove from Redis
            await self._remove_redis_claim(fan_id)
            
            # Notify other chatters
            await self._notify_claim_change(
                str(claim.model_id),
                fan_id,
                chatter_id,
                'released'
            )
            
            return {
                'success': True,
                'released_at': claim.released_at.isoformat()
            }
    
    async def get_active_claims(
        self,
        model_id: str,
        chatter_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all active claims for a model or specific chatter."""
        async with AsyncSessionLocal() as db:
            query = select(FanClaim).where(
                and_(
                    FanClaim.model_id == model_id,
                    FanClaim.is_active == True
                )
            )
            
            if chatter_id:
                query = query.where(FanClaim.chatter_id == chatter_id)
            
            result = await db.execute(query)
            claims = result.scalars().all()
            
            claim_list = []
            for claim in claims:
                # Get fan details
                fan = await db.get(Fan, claim.fan_id)
                chatter = await db.get(User, claim.chatter_id)
                
                claim_list.append({
                    'claim_id': str(claim.id),
                    'fan_id': str(claim.fan_id),
                    'fan_username': fan.username if fan else 'Unknown',
                    'chatter_id': str(claim.chatter_id),
                    'chatter_username': chatter.username if chatter else 'Unknown',
                    'claimed_at': claim.claimed_at.isoformat(),
                    'expires_at': claim.expires_at.isoformat(),
                    'is_expired': claim.expires_at < datetime.utcnow()
                })
            
            return claim_list
    
    async def check_claim_status(
        self,
        fan_id: str
    ) -> Dict[str, Any]:
        """Check if a fan is currently claimed."""
        # First check Redis for quick lookup
        redis_key = f"{self.CLAIM_KEY_PREFIX}{fan_id}"
        claim_data = await redis_client.get(redis_key)
        
        if claim_data:
            claim = json.loads(claim_data)
            if datetime.fromisoformat(claim['expires_at']) > datetime.utcnow():
                return {
                    'is_claimed': True,
                    'chatter_id': claim['chatter_id'],
                    'expires_at': claim['expires_at']
                }
        
        # Fallback to database
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.fan_id == fan_id,
                        FanClaim.is_active == True,
                        FanClaim.expires_at > datetime.utcnow()
                    )
                )
            )
            claim = result.scalar_one_or_none()
            
            if claim:
                # Update Redis
                await self._update_redis_claim(
                    fan_id,
                    str(claim.chatter_id),
                    claim.expires_at
                )
                
                return {
                    'is_claimed': True,
                    'chatter_id': str(claim.chatter_id),
                    'expires_at': claim.expires_at.isoformat()
                }
            
            return {
                'is_claimed': False
            }
    
    async def release_expired_claims(self):
        """Release all expired claims (called periodically)."""
        async with AsyncSessionLocal() as db:
            # Find expired claims
            result = await db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.is_active == True,
                        FanClaim.expires_at < datetime.utcnow()
                    )
                )
            )
            expired_claims = result.scalars().all()
            
            for claim in expired_claims:
                claim.is_active = False
                claim.released_at = datetime.utcnow()
                
                # Remove from Redis
                await self._remove_redis_claim(str(claim.fan_id))
                
                # Notify
                await self._notify_claim_change(
                    str(claim.model_id),
                    str(claim.fan_id),
                    str(claim.chatter_id),
                    'expired'
                )
            
            await db.commit()
            
            logger.info(f"Released {len(expired_claims)} expired claims")
    
    async def release_all_claims(self, chatter_id: str):
        """Release all claims for a chatter (e.g., on disconnect)."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FanClaim).where(
                    and_(
                        FanClaim.chatter_id == chatter_id,
                        FanClaim.is_active == True
                    )
                )
            )
            claims = result.scalars().all()
            
            for claim in claims:
                claim.is_active = False
                claim.released_at = datetime.utcnow()
                
                # Remove from Redis
                await self._remove_redis_claim(str(claim.fan_id))
                
                # Notify
                await self._notify_claim_change(
                    str(claim.model_id),
                    str(claim.fan_id),
                    chatter_id,
                    'released'
                )
            
            await db.commit()
            
            logger.info(f"Released {len(claims)} claims for chatter {chatter_id}")
    
    async def _update_redis_claim(
        self,
        fan_id: str,
        chatter_id: str,
        expires_at: datetime
    ):
        """Update claim in Redis for fast lookup."""
        redis_key = f"{self.CLAIM_KEY_PREFIX}{fan_id}"
        claim_data = {
            'chatter_id': chatter_id,
            'expires_at': expires_at.isoformat()
        }
        
        # Set with expiration
        ttl = int((expires_at - datetime.utcnow()).total_seconds())
        if ttl > 0:
            await redis_client.setex(
                redis_key,
                ttl,
                json.dumps(claim_data)
            )
            
            # Add to chatter's active claims set
            active_key = f"{self.ACTIVE_CLAIMS_KEY}{chatter_id}"
            await redis_client.sadd(active_key, fan_id)
            await redis_client.expire(active_key, ttl)
    
    async def _remove_redis_claim(self, fan_id: str):
        """Remove claim from Redis."""
        redis_key = f"{self.CLAIM_KEY_PREFIX}{fan_id}"
        
        # Get claim data to find chatter
        claim_data = await redis_client.get(redis_key)
        if claim_data:
            claim = json.loads(claim_data)
            chatter_id = claim['chatter_id']
            
            # Remove from chatter's active claims
            active_key = f"{self.ACTIVE_CLAIMS_KEY}{chatter_id}"
            await redis_client.srem(active_key, fan_id)
        
        # Remove claim
        await redis_client.delete(redis_key)
    
    async def _notify_claim_change(
        self,
        model_id: str,
        fan_id: str,
        chatter_id: str,
        action: str
    ):
        """Notify about claim status change via Redis pub/sub."""
        notification = {
            'type': 'claim_change',
            'model_id': model_id,
            'fan_id': fan_id,
            'chatter_id': chatter_id,
            'action': action,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Publish to model-specific channel
        channel = f"claims:{model_id}"
        await redis_client.publish(channel, json.dumps(notification))