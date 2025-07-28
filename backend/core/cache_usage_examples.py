"""
Examples of using caching strategies in API endpoints
"""
from typing import List, Optional
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db, get_read_db
from core.cache import (
    cache_result, 
    invalidate_cache,
    query_cache,
    user_cache,
    list_cache
)
from core.domain.models import User, Agency, ModelProfile


# Example 1: Simple function result caching
@cache_result(ttl=600, key_prefix="agency_stats")
async def get_agency_statistics(agency_id: str, db: AsyncSession) -> dict:
    """Get agency statistics with caching"""
    # Expensive query that benefits from caching
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id)
    )
    agency = result.scalar_one_or_none()
    
    if not agency:
        return {}
    
    # Calculate statistics
    stats = {
        "total_models": len(agency.models),
        "total_revenue": sum(m.total_revenue for m in agency.models),
        "active_subscriptions": sum(m.active_subscriptions for m in agency.models)
    }
    
    return stats


# Example 2: Query caching with invalidation
class ModelService:
    """Service with query caching"""
    
    async def get_model_profiles(
        self, 
        agency_id: str, 
        db: AsyncSession
    ) -> List[ModelProfile]:
        """Get model profiles with query caching"""
        cache_key = f"models:agency:{agency_id}"
        
        async def fetch_models():
            result = await db.execute(
                select(ModelProfile)
                .where(ModelProfile.agency_id == agency_id)
                .order_by(ModelProfile.created_at.desc())
            )
            return [m.dict() for m in result.scalars().all()]
        
        # Use query cache with 5 minute TTL
        return await query_cache.get_or_set(
            cache_key,
            fetch_models,
            ttl=300
        )
    
    @invalidate_cache("query:models:agency:*")
    async def create_model_profile(
        self,
        model_data: dict,
        db: AsyncSession
    ) -> ModelProfile:
        """Create model profile and invalidate cache"""
        model = ModelProfile(**model_data)
        db.add(model)
        await db.commit()
        return model


# Example 3: User-specific caching
class UserService:
    """Service with user-specific caching"""
    
    async def get_user_preferences(
        self,
        user_id: str,
        db: AsyncSession
    ) -> dict:
        """Get user preferences with caching"""
        # Check cache first
        cached = await user_cache.get_user_data(user_id, "preferences")
        if cached:
            return cached
        
        # Fetch from database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            preferences = {
                "theme": user.preferences.get("theme", "light"),
                "notifications": user.preferences.get("notifications", True),
                "language": user.preferences.get("language", "en")
            }
            
            # Cache for 10 minutes
            await user_cache.set_user_data(
                user_id, 
                "preferences", 
                preferences, 
                ttl=600
            )
            
            return preferences
        
        return {}
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: dict,
        db: AsyncSession
    ) -> dict:
        """Update user preferences and invalidate cache"""
        # Update in database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.preferences = preferences
            await db.commit()
            
            # Invalidate user cache
            await user_cache.invalidate_user(user_id)
            
            return preferences
        
        return {}


# Example 4: List caching for feeds
class FeedService:
    """Service for cached feeds"""
    
    async def get_user_feed(
        self,
        user_id: str,
        db: AsyncSession,
        limit: int = 50
    ) -> List[dict]:
        """Get user feed with list caching"""
        cache_key = f"feed:{user_id}"
        
        # Try cache first
        cached_feed = await list_cache.get_list(cache_key)
        if cached_feed:
            return cached_feed[:limit]
        
        # Generate feed (expensive operation)
        feed_items = await self._generate_feed(user_id, db, limit)
        
        # Cache the feed for 5 minutes
        await list_cache.set_list(cache_key, feed_items, ttl=300)
        
        return feed_items
    
    async def _generate_feed(
        self,
        user_id: str,
        db: AsyncSession,
        limit: int
    ) -> List[dict]:
        """Generate user feed (expensive operation)"""
        # Complex query to generate personalized feed
        # This is just a placeholder
        return [
            {"id": i, "type": "post", "content": f"Item {i}"}
            for i in range(limit)
        ]
    
    async def add_to_feed(
        self,
        user_id: str,
        item: dict
    ) -> bool:
        """Add item to user's cached feed"""
        cache_key = f"feed:{user_id}"
        
        # Append to cached list
        return await list_cache.append_to_list(cache_key, item)


# Example 5: Cache warming strategy
class CacheWarmer:
    """Warm up cache for frequently accessed data"""
    
    async def warm_agency_cache(self, db: AsyncSession):
        """Pre-populate cache with agency data"""
        # Get all active agencies
        result = await db.execute(
            select(Agency).where(Agency.is_active == True)
        )
        agencies = result.scalars().all()
        
        # Warm up statistics for each agency
        for agency in agencies:
            await get_agency_statistics(str(agency.id), db)
    
    async def warm_user_cache(self, db: AsyncSession):
        """Pre-populate cache with active user data"""
        # Get recently active users
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        result = await db.execute(
            select(User).where(User.last_login > cutoff)
        )
        users = result.scalars().all()
        
        # Warm up preferences for active users
        service = UserService()
        for user in users:
            await service.get_user_preferences(str(user.id), db)


# Example 6: Cache-aside pattern for complex queries
async def get_analytics_data(
    agency_id: str,
    start_date: str,
    end_date: str,
    db: AsyncSession
) -> dict:
    """Get analytics data with cache-aside pattern"""
    # Generate cache key
    cache_key = f"analytics:{agency_id}:{start_date}:{end_date}"
    
    # Check cache
    if query_cache:
        cached = await query_cache.get(cache_key)
        if cached:
            return cached
    
    # Perform expensive analytics query
    analytics_data = {
        "revenue": await calculate_revenue(agency_id, start_date, end_date, db),
        "subscribers": await count_subscribers(agency_id, start_date, end_date, db),
        "engagement": await calculate_engagement(agency_id, start_date, end_date, db)
    }
    
    # Cache results for 1 hour
    if query_cache:
        await query_cache.set(cache_key, analytics_data, ttl=3600)
    
    return analytics_data


# Helper functions (placeholders)
async def calculate_revenue(agency_id: str, start: str, end: str, db: AsyncSession) -> float:
    return 0.0

async def count_subscribers(agency_id: str, start: str, end: str, db: AsyncSession) -> int:
    return 0

async def calculate_engagement(agency_id: str, start: str, end: str, db: AsyncSession) -> dict:
    return {}