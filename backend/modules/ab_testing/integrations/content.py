"""
A/B Testing Integration for Content Recommendations
"""
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from modules.ab_testing.core.experiment_manager import experiment_manager
from modules.ab_testing.domain.models import ExperimentType

logger = get_logger(__name__)


class ContentExperimentIntegration:
    """Integrate A/B testing with content recommendations"""
    
    async def get_recommendation_variant(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        content_type: str,  # "feed", "explore", "similar"
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get content recommendation variant"""
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.CONTENT_RECOMMENDATION,
            db=db
        )
        
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            if target_audience.get("content_type") == content_type:
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    context = {
                        "model_id": model_id,
                        "content_type": content_type
                    }
                    
                    variant = await experiment_manager.assign_participant(
                        experiment_id=exp.id,
                        participant_type="fan",
                        participant_id=fan_id,
                        context=context,
                        db=db
                    )
                    
                    if variant:
                        return {
                            "experiment_id": exp.id,
                            "variant_id": variant.id,
                            "algorithm": variant.config.get("algorithm", "collaborative"),
                            "boost_recent": variant.config.get("boost_recent", False),
                            "personalization_weight": variant.config.get("personalization_weight", 0.7),
                            "diversity_factor": variant.config.get("diversity_factor", 0.3),
                            "max_items": variant.config.get("max_items", 20)
                        }
        
        return None
    
    async def get_ui_variant(
        self,
        agency_id: str,
        user_id: str,
        element_type: str,  # "layout", "button", "modal", "navigation"
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get UI element variant"""
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.UI_ELEMENT,
            db=db
        )
        
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            if target_audience.get("element_type") == element_type:
                context = {"element_type": element_type}
                
                variant = await experiment_manager.assign_participant(
                    experiment_id=exp.id,
                    participant_type="user",
                    participant_id=user_id,
                    context=context,
                    db=db
                )
                
                if variant:
                    return {
                        "experiment_id": exp.id,
                        "variant_id": variant.id,
                        "variant_name": variant.name,
                        "config": variant.config
                    }
        
        return None
    
    async def track_content_interaction(
        self,
        experiment_id: UUID,
        fan_id: str,
        content_id: str,
        interaction_type: str,  # "view", "like", "purchase", "share"
        interaction_time: Optional[float] = None,
        db: Optional[AsyncSession] = None
    ):
        """Track content interaction events"""
        event_data = {
            "content_id": content_id,
            "interaction_type": interaction_type
        }
        
        if interaction_time:
            event_data["interaction_time"] = interaction_time
        
        # Mark purchases as conversions
        if interaction_type == "purchase":
            event_data["is_conversion"] = True
        
        await experiment_manager.track_event(
            experiment_id=experiment_id,
            participant_type="fan",
            participant_id=fan_id,
            event_type=f"content_{interaction_type}",
            event_value=interaction_time,
            event_data=event_data,
            db=db
        )
    
    async def get_engagement_strategy_variant(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        fan_segment: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get engagement strategy variant"""
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.ENGAGEMENT_STRATEGY,
            db=db
        )
        
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            # Check if experiment targets this segment
            target_segments = target_audience.get("segments", [])
            if not target_segments or fan_segment in target_segments:
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    context = {
                        "model_id": model_id,
                        "fan_segment": fan_segment
                    }
                    
                    variant = await experiment_manager.assign_participant(
                        experiment_id=exp.id,
                        participant_type="fan",
                        participant_id=fan_id,
                        context=context,
                        db=db
                    )
                    
                    if variant:
                        return {
                            "experiment_id": exp.id,
                            "variant_id": variant.id,
                            "strategy_name": variant.config.get("strategy_name"),
                            "message_frequency": variant.config.get("message_frequency", "normal"),
                            "content_mix": variant.config.get("content_mix", {}),
                            "incentives": variant.config.get("incentives", []),
                            "personalization_level": variant.config.get("personalization_level", "medium")
                        }
        
        return None
    
    async def rank_content_variants(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        content_items: List[Dict[str, Any]],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Apply A/B test variant to content ranking"""
        variant = await self.get_recommendation_variant(
            agency_id, model_id, fan_id, "feed", db
        )
        
        if not variant:
            return content_items
        
        # Apply variant-specific ranking
        algorithm = variant.get("algorithm", "collaborative")
        
        if algorithm == "chronological":
            # Sort by timestamp
            return sorted(
                content_items,
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
        
        elif algorithm == "engagement":
            # Sort by engagement metrics
            return sorted(
                content_items,
                key=lambda x: x.get("engagement_score", 0),
                reverse=True
            )
        
        elif algorithm == "personalized":
            # Apply personalization weight
            weight = variant.get("personalization_weight", 0.7)
            
            for item in content_items:
                personal_score = item.get("personal_relevance", 0)
                global_score = item.get("global_popularity", 0)
                item["final_score"] = (
                    personal_score * weight + 
                    global_score * (1 - weight)
                )
            
            return sorted(
                content_items,
                key=lambda x: x.get("final_score", 0),
                reverse=True
            )
        
        return content_items


# Global instance
content_experiments = ContentExperimentIntegration()