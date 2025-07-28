"""
A/B Testing Integration for Pricing
"""
from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from modules.ab_testing.core.experiment_manager import experiment_manager
from modules.ab_testing.domain.models import ExperimentType

logger = get_logger(__name__)


class PricingExperimentIntegration:
    """Integrate A/B testing with pricing strategies"""
    
    async def get_pricing_variant(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        product_type: str,  # "subscription", "ppv", "tip", "custom"
        original_price: Decimal,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get pricing variant for A/B testing"""
        # Get active pricing experiments
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.PRICING,
            db=db
        )
        
        # Filter experiments for this product type
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            # Check if experiment targets this product type
            if target_audience.get("product_type") == product_type:
                # Check if model is included
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    # Assign fan to variant
                    context = {
                        "model_id": model_id,
                        "product_type": product_type,
                        "original_price": float(original_price)
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
                            "variant_name": variant.name,
                            "price": Decimal(str(variant.config.get("price", original_price))),
                            "discount_percentage": variant.config.get("discount_percentage", 0),
                            "bundle_items": variant.config.get("bundle_items", []),
                            "display_strategy": variant.config.get("display_strategy", "standard")
                        }
        
        return None
    
    async def get_dynamic_pricing(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        fan_data: Dict[str, Any],
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get dynamic pricing based on fan characteristics"""
        # Get active pricing experiments with dynamic pricing
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.PRICING,
            db=db
        )
        
        for exp in experiments:
            if exp.allocation_config and exp.allocation_config.get("dynamic_pricing"):
                # Check if model is included
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    # Assign based on fan characteristics
                    context = {
                        "model_id": model_id,
                        "fan_lifetime_value": fan_data.get("lifetime_value", 0),
                        "fan_engagement_score": fan_data.get("engagement_score", 0),
                        "fan_segment": fan_data.get("segment", "unknown")
                    }
                    
                    variant = await experiment_manager.assign_participant(
                        experiment_id=exp.id,
                        participant_type="fan",
                        participant_id=fan_id,
                        context=context,
                        db=db
                    )
                    
                    if variant:
                        # Calculate dynamic price based on variant rules
                        base_price = variant.config.get("base_price", 10)
                        multiplier = 1.0
                        
                        # Apply segment-based pricing
                        segment_multipliers = variant.config.get("segment_multipliers", {})
                        if fan_data.get("segment") in segment_multipliers:
                            multiplier *= segment_multipliers[fan_data["segment"]]
                        
                        # Apply LTV-based pricing
                        if fan_data.get("lifetime_value", 0) > 100:
                            multiplier *= variant.config.get("high_ltv_multiplier", 1.2)
                        
                        final_price = Decimal(str(base_price * multiplier))
                        
                        return {
                            "experiment_id": exp.id,
                            "variant_id": variant.id,
                            "price": final_price,
                            "pricing_strategy": "dynamic",
                            "applied_rules": ["segment", "ltv"] if multiplier != 1.0 else []
                        }
        
        return None
    
    async def track_pricing_conversion(
        self,
        experiment_id: UUID,
        fan_id: str,
        product_type: str,
        price: Decimal,
        converted: bool,
        db: Optional[AsyncSession] = None
    ):
        """Track pricing conversion events"""
        event_data = {
            "product_type": product_type,
            "price": float(price),
            "converted": converted,
            "is_conversion": converted
        }
        
        event_type = "pricing_conversion" if converted else "pricing_view"
        event_value = float(price) if converted else None
        
        await experiment_manager.track_event(
            experiment_id=experiment_id,
            participant_type="fan",
            participant_id=fan_id,
            event_type=event_type,
            event_value=event_value,
            event_data=event_data,
            db=db
        )
    
    async def get_bundle_variant(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        content_ids: List[str],
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get bundle pricing variant"""
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.PRICING,
            db=db
        )
        
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            if target_audience.get("product_type") == "bundle":
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    context = {
                        "model_id": model_id,
                        "content_count": len(content_ids),
                        "content_ids": content_ids
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
                            "bundle_price": Decimal(str(variant.config.get("bundle_price", 0))),
                            "discount_type": variant.config.get("discount_type", "percentage"),
                            "discount_value": variant.config.get("discount_value", 0),
                            "min_items": variant.config.get("min_items", 2),
                            "max_items": variant.config.get("max_items", 10)
                        }
        
        return None


# Global instance
pricing_experiments = PricingExperimentIntegration()