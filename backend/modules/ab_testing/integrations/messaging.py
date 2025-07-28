"""
A/B Testing Integration for Messaging
"""
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from modules.ab_testing.core.experiment_manager import experiment_manager
from modules.ab_testing.domain.models import ExperimentType

logger = get_logger(__name__)


class MessagingExperimentIntegration:
    """Integrate A/B testing with messaging system"""
    
    async def get_message_variant(
        self,
        agency_id: str,
        model_id: str,
        fan_id: str,
        message_type: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get message variant for A/B testing"""
        # Get active message content experiments
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.MESSAGE_CONTENT,
            db=db
        )
        
        # Filter experiments for this message type
        relevant_experiments = []
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            # Check if experiment targets this message type
            if target_audience.get("message_type") == message_type:
                # Check if model is included
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    relevant_experiments.append(exp)
        
        if not relevant_experiments:
            return None
        
        # For now, use the first relevant experiment
        experiment = relevant_experiments[0]
        
        # Assign fan to variant
        context = {
            "model_id": model_id,
            "message_type": message_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        variant = await experiment_manager.assign_participant(
            experiment_id=experiment.id,
            participant_type="fan",
            participant_id=fan_id,
            context=context,
            db=db
        )
        
        if not variant:
            return None
        
        # Return variant configuration
        return {
            "experiment_id": experiment.id,
            "variant_id": variant.id,
            "variant_name": variant.name,
            "message_template": variant.config.get("message_template"),
            "personalization": variant.config.get("personalization", {}),
            "tone": variant.config.get("tone", "default")
        }
    
    async def track_message_event(
        self,
        experiment_id: UUID,
        fan_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ):
        """Track message-related events"""
        # Map message events to experiment events
        experiment_event_type = event_type
        
        # Determine if this is a conversion event
        conversion_events = ["purchase", "tip", "subscription", "ppv_purchase"]
        if event_type in conversion_events:
            if not event_data:
                event_data = {}
            event_data["is_conversion"] = True
        
        # Track the event
        await experiment_manager.track_event(
            experiment_id=experiment_id,
            participant_type="fan",
            participant_id=fan_id,
            event_type=experiment_event_type,
            event_value=event_data.get("value") if event_data else None,
            event_data=event_data,
            db=db
        )
    
    async def get_timing_variant(
        self,
        agency_id: str,
        model_id: str,
        message_type: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get message timing variant for A/B testing"""
        # Get active timing experiments
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            experiment_type=ExperimentType.MESSAGE_TIMING,
            db=db
        )
        
        for exp in experiments:
            target_audience = exp.target_audience or {}
            
            if target_audience.get("message_type") == message_type:
                if not exp.model_ids or str(model_id) in exp.model_ids:
                    # Use model as participant for timing experiments
                    variant = await experiment_manager.assign_participant(
                        experiment_id=exp.id,
                        participant_type="model",
                        participant_id=model_id,
                        context={"message_type": message_type},
                        db=db
                    )
                    
                    if variant:
                        return {
                            "experiment_id": exp.id,
                            "variant_id": variant.id,
                            "send_time": variant.config.get("send_time"),
                            "delay_minutes": variant.config.get("delay_minutes", 0),
                            "batch_size": variant.config.get("batch_size", 100)
                        }
        
        return None


# Global instance
messaging_experiments = MessagingExperimentIntegration()