"""
Experiment Manager - Core orchestrator for A/B tests
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.redis import redis_client
from ..domain.models import (
    Experiment, ExperimentVariant, ExperimentParticipant,
    ExperimentEvent, ExperimentStatus, ExperimentType
)
from .traffic_splitter import TrafficSplitter
from .metrics_collector import MetricsCollector
from ..analysis.statistical_engine import StatisticalEngine

logger = get_logger(__name__)


class ExperimentManager:
    """Manages the lifecycle of A/B testing experiments"""
    
    def __init__(self):
        self.traffic_splitter = TrafficSplitter()
        self.metrics_collector = MetricsCollector()
        self.statistical_engine = StatisticalEngine()
        self._running_experiments_cache = {}
        
    async def create_experiment(
        self,
        agency_id: str,
        created_by: str,
        name: str,
        experiment_type: ExperimentType,
        config: Dict[str, Any],
        db: AsyncSession
    ) -> Experiment:
        """Create a new experiment"""
        # Validate configuration
        self._validate_experiment_config(experiment_type, config)
        
        # Create experiment
        experiment = Experiment(
            id=uuid4(),
            agency_id=agency_id,
            created_by=created_by,
            name=name,
            description=config.get("description"),
            hypothesis=config.get("hypothesis"),
            experiment_type=experiment_type.value,
            target_audience=config.get("target_audience", {}),
            model_ids=config.get("model_ids", []),
            primary_metric=config["primary_metric"],
            secondary_metrics=config.get("secondary_metrics", []),
            minimum_sample_size=config.get("minimum_sample_size", 100),
            allocation_method=config.get("allocation_method", "random"),
            allocation_config=config.get("allocation_config", {}),
            statistical_test=config.get("statistical_test", "t_test"),
            confidence_level=config.get("confidence_level", 0.95),
            minimum_detectable_effect=config.get("minimum_detectable_effect", 0.05)
        )
        
        db.add(experiment)
        
        # Create variants
        variants_config = config.get("variants", [])
        if not variants_config:
            raise ValueError("At least one variant is required")
            
        total_allocation = 0
        for variant_config in variants_config:
            variant = ExperimentVariant(
                id=uuid4(),
                experiment_id=experiment.id,
                name=variant_config["name"],
                description=variant_config.get("description"),
                is_control=variant_config.get("is_control", False),
                config=variant_config["config"],
                allocation_percentage=variant_config.get("allocation_percentage", 50.0)
            )
            total_allocation += variant.allocation_percentage
            db.add(variant)
            
        # Validate total allocation
        if abs(total_allocation - 100.0) > 0.01:
            raise ValueError(f"Total allocation must equal 100%, got {total_allocation}%")
            
        await db.commit()
        await db.refresh(experiment)
        
        logger.info(f"Created experiment {experiment.id} with {len(variants_config)} variants")
        
        return experiment
        
    async def start_experiment(
        self,
        experiment_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Start an experiment"""
        experiment = await db.get(Experiment, experiment_id)
        
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
            
        if experiment.status != ExperimentStatus.DRAFT.value:
            raise ValueError(f"Experiment must be in DRAFT status to start")
            
        # Validate experiment is ready
        await self._validate_experiment_ready(experiment, db)
        
        # Update status
        experiment.status = ExperimentStatus.RUNNING.value
        experiment.start_date = datetime.utcnow()
        
        # Calculate end date if duration specified
        if experiment.allocation_config and "duration_days" in experiment.allocation_config:
            experiment.end_date = experiment.start_date + timedelta(
                days=experiment.allocation_config["duration_days"]
            )
            
        await db.commit()
        
        # Cache running experiment
        await self._cache_running_experiment(experiment, db)
        
        # Start metrics collection
        asyncio.create_task(
            self.metrics_collector.start_collection(experiment_id)
        )
        
        logger.info(f"Started experiment {experiment_id}")
        
        return True
        
    async def pause_experiment(
        self,
        experiment_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Pause a running experiment"""
        experiment = await db.get(Experiment, experiment_id)
        
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
            
        if experiment.status != ExperimentStatus.RUNNING.value:
            raise ValueError("Can only pause running experiments")
            
        experiment.status = ExperimentStatus.PAUSED.value
        await db.commit()
        
        # Remove from cache
        await self._remove_from_cache(experiment_id)
        
        logger.info(f"Paused experiment {experiment_id}")
        
        return True
        
    async def complete_experiment(
        self,
        experiment_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Complete an experiment and analyze results"""
        experiment = await db.get(Experiment, experiment_id)
        
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
            
        if experiment.status not in [ExperimentStatus.RUNNING.value, ExperimentStatus.PAUSED.value]:
            raise ValueError("Can only complete running or paused experiments")
            
        # Run final analysis
        results = await self.analyze_experiment(experiment_id, db)
        
        # Determine winner
        winner_variant_id = self._determine_winner(results)
        
        # Update experiment
        experiment.status = ExperimentStatus.COMPLETED.value
        experiment.completed_at = datetime.utcnow()
        experiment.winner_variant_id = winner_variant_id
        experiment.results_summary = results
        
        await db.commit()
        
        # Remove from cache
        await self._remove_from_cache(experiment_id)
        
        # Stop metrics collection
        await self.metrics_collector.stop_collection(experiment_id)
        
        logger.info(f"Completed experiment {experiment_id} with winner {winner_variant_id}")
        
        return results
        
    async def assign_participant(
        self,
        experiment_id: UUID,
        participant_type: str,
        participant_id: str,
        context: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> Optional[ExperimentVariant]:
        """Assign a participant to an experiment variant"""
        # Check cache first
        cached_experiment = await self._get_cached_experiment(experiment_id)
        
        if not cached_experiment:
            if not db:
                return None
                
            # Load from database
            experiment = await self._load_experiment_with_variants(experiment_id, db)
            
            if not experiment or experiment.status != ExperimentStatus.RUNNING.value:
                return None
                
            cached_experiment = experiment
            
        # Check if already assigned
        existing_assignment = await self._get_existing_assignment(
            experiment_id, participant_type, participant_id
        )
        
        if existing_assignment:
            return existing_assignment
            
        # Check targeting criteria
        if not self._meets_targeting_criteria(
            cached_experiment, participant_type, participant_id, context
        ):
            return None
            
        # Assign to variant
        variant = await self.traffic_splitter.assign_variant(
            cached_experiment,
            participant_type,
            participant_id,
            context
        )
        
        if variant and db:
            # Record assignment
            participant = ExperimentParticipant(
                id=uuid4(),
                experiment_id=experiment_id,
                variant_id=variant.id,
                participant_type=participant_type,
                participant_id=participant_id,
                assignment_reason=f"Assigned by {cached_experiment.allocation_method}",
                metadata=context
            )
            
            db.add(participant)
            
            # Update variant participant count
            variant.participant_count += 1
            
            await db.commit()
            
            # Cache assignment
            await self._cache_assignment(
                experiment_id, participant_type, participant_id, variant
            )
            
        return variant
        
    async def track_event(
        self,
        experiment_id: UUID,
        participant_type: str,
        participant_id: str,
        event_type: str,
        event_value: Optional[float] = None,
        event_data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None
    ) -> bool:
        """Track an event for an experiment participant"""
        # Get participant assignment
        assignment = await self._get_existing_assignment(
            experiment_id, participant_type, participant_id
        )
        
        if not assignment:
            return False
            
        # Send to metrics collector
        await self.metrics_collector.track_event(
            experiment_id=experiment_id,
            participant_id=f"{participant_type}:{participant_id}",
            variant_id=assignment.id,
            event_type=event_type,
            event_value=event_value,
            event_data=event_data
        )
        
        if db:
            # Get participant record
            participant_query = select(ExperimentParticipant).where(
                and_(
                    ExperimentParticipant.experiment_id == experiment_id,
                    ExperimentParticipant.participant_type == participant_type,
                    ExperimentParticipant.participant_id == participant_id
                )
            )
            
            result = await db.execute(participant_query)
            participant = result.scalar_one_or_none()
            
            if participant:
                # Record event
                event = ExperimentEvent(
                    id=uuid4(),
                    experiment_id=experiment_id,
                    participant_id=participant.id,
                    event_type=event_type,
                    event_value=event_value,
                    event_data=event_data
                )
                
                db.add(event)
                
                # Update participant metrics
                participant.interaction_count += 1
                participant.last_interaction = datetime.utcnow()
                
                # Check for conversion
                if event_type == "conversion" or (event_data and event_data.get("is_conversion")):
                    participant.has_converted = True
                    participant.conversion_timestamp = datetime.utcnow()
                    participant.conversion_value = event_value
                    
                    # Update variant conversion metrics
                    variant = await db.get(ExperimentVariant, participant.variant_id)
                    if variant:
                        variant.conversion_count += 1
                        if variant.participant_count > 0:
                            variant.conversion_rate = (
                                variant.conversion_count / variant.participant_count
                            )
                            
                await db.commit()
                
        return True
        
    async def analyze_experiment(
        self,
        experiment_id: UUID,
        db: AsyncSession,
        segment_by: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze experiment results"""
        experiment = await self._load_experiment_with_data(experiment_id, db)
        
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
            
        # Collect metrics
        metrics = await self.metrics_collector.get_experiment_metrics(
            experiment_id,
            segment_by=segment_by
        )
        
        # Run statistical analysis
        analysis_results = await self.statistical_engine.analyze(
            experiment,
            metrics,
            confidence_level=experiment.confidence_level
        )
        
        return {
            "experiment_id": str(experiment_id),
            "status": experiment.status,
            "duration_days": (
                (datetime.utcnow() - experiment.start_date).days
                if experiment.start_date else 0
            ),
            "total_participants": metrics.get("total_participants", 0),
            "variants": analysis_results["variants"],
            "statistical_significance": analysis_results["statistical_significance"],
            "recommendations": analysis_results["recommendations"],
            "segments": analysis_results.get("segments", {}),
            "time_series": metrics.get("time_series", []),
            "metadata": {
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "confidence_level": experiment.confidence_level,
                "minimum_detectable_effect": experiment.minimum_detectable_effect
            }
        }
        
    async def get_active_experiments(
        self,
        agency_id: str,
        experiment_type: Optional[ExperimentType] = None,
        db: AsyncSession = None
    ) -> List[Experiment]:
        """Get all active experiments for an agency"""
        # Check cache first
        cache_key = f"active_experiments:{agency_id}"
        if experiment_type:
            cache_key += f":{experiment_type.value}"
            
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
            
        if not db:
            return []
            
        # Query database
        query = select(Experiment).where(
            and_(
                Experiment.agency_id == agency_id,
                Experiment.status == ExperimentStatus.RUNNING.value
            )
        )
        
        if experiment_type:
            query = query.where(Experiment.experiment_type == experiment_type.value)
            
        result = await db.execute(query)
        experiments = result.scalars().all()
        
        # Cache results
        await redis_client.setex(
            cache_key,
            300,  # 5 minutes
            json.dumps([e.dict() for e in experiments])
        )
        
        return experiments
        
    def _validate_experiment_config(
        self,
        experiment_type: ExperimentType,
        config: Dict[str, Any]
    ):
        """Validate experiment configuration"""
        # Required fields
        required_fields = ["primary_metric", "variants"]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
                
        # Type-specific validation
        if experiment_type == ExperimentType.MESSAGE_CONTENT:
            for variant in config["variants"]:
                if "message_template" not in variant.get("config", {}):
                    raise ValueError("Message content experiments require message_template in variant config")
                    
        elif experiment_type == ExperimentType.PRICING:
            for variant in config["variants"]:
                if "price" not in variant.get("config", {}):
                    raise ValueError("Pricing experiments require price in variant config")
                    
    async def _validate_experiment_ready(
        self,
        experiment: Experiment,
        db: AsyncSession
    ):
        """Validate experiment is ready to start"""
        # Check variants
        variants_query = select(ExperimentVariant).where(
            ExperimentVariant.experiment_id == experiment.id
        )
        result = await db.execute(variants_query)
        variants = result.scalars().all()
        
        if len(variants) < 2:
            raise ValueError("Experiment must have at least 2 variants")
            
        # Check control variant
        has_control = any(v.is_control for v in variants)
        if not has_control:
            raise ValueError("Experiment must have a control variant")
            
        # Check allocation
        total_allocation = sum(v.allocation_percentage for v in variants)
        if abs(total_allocation - 100.0) > 0.01:
            raise ValueError(f"Total allocation must equal 100%, got {total_allocation}%")
            
    async def _cache_running_experiment(
        self,
        experiment: Experiment,
        db: AsyncSession
    ):
        """Cache running experiment for fast lookups"""
        # Load variants
        variants_query = select(ExperimentVariant).where(
            ExperimentVariant.experiment_id == experiment.id
        )
        result = await db.execute(variants_query)
        variants = result.scalars().all()
        
        # Cache experiment data
        cache_data = {
            "experiment": experiment.dict(),
            "variants": [v.dict() for v in variants]
        }
        
        cache_key = f"running_experiment:{experiment.id}"
        await redis_client.setex(
            cache_key,
            3600,  # 1 hour
            json.dumps(cache_data)
        )
        
        # Add to running experiments set
        await redis_client.sadd(
            f"running_experiments:{experiment.agency_id}",
            str(experiment.id)
        )
        
    async def _remove_from_cache(self, experiment_id: UUID):
        """Remove experiment from cache"""
        cache_key = f"running_experiment:{experiment_id}"
        await redis_client.delete(cache_key)
        
        # Remove from running experiments set
        # Note: We'd need to get agency_id from experiment
        
    async def _get_cached_experiment(
        self,
        experiment_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get cached experiment data"""
        cache_key = f"running_experiment:{experiment_id}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        return None
        
    async def _get_existing_assignment(
        self,
        experiment_id: UUID,
        participant_type: str,
        participant_id: str
    ) -> Optional[ExperimentVariant]:
        """Check if participant is already assigned"""
        cache_key = f"assignment:{experiment_id}:{participant_type}:{participant_id}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            variant_data = json.loads(cached)
            # Convert to variant object
            variant = ExperimentVariant(**variant_data)
            return variant
            
        return None
        
    async def _cache_assignment(
        self,
        experiment_id: UUID,
        participant_type: str,
        participant_id: str,
        variant: ExperimentVariant
    ):
        """Cache participant assignment"""
        cache_key = f"assignment:{experiment_id}:{participant_type}:{participant_id}"
        await redis_client.setex(
            cache_key,
            86400 * 7,  # 7 days
            json.dumps(variant.dict())
        )
        
    def _meets_targeting_criteria(
        self,
        experiment: Dict[str, Any],
        participant_type: str,
        participant_id: str,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if participant meets targeting criteria"""
        target_audience = experiment.get("experiment", {}).get("target_audience", {})
        
        if not target_audience:
            return True  # No targeting criteria
            
        # Check participant type
        if "participant_types" in target_audience:
            if participant_type not in target_audience["participant_types"]:
                return False
                
        # Check model IDs
        if "model_ids" in experiment.get("experiment", {}):
            model_ids = experiment["experiment"]["model_ids"]
            if model_ids and context and context.get("model_id"):
                if str(context["model_id"]) not in model_ids:
                    return False
                    
        # Check custom criteria
        if context and "custom_criteria" in target_audience:
            for key, expected_value in target_audience["custom_criteria"].items():
                if context.get(key) != expected_value:
                    return False
                    
        return True
        
    def _determine_winner(
        self,
        results: Dict[str, Any]
    ) -> Optional[UUID]:
        """Determine winning variant from results"""
        variants = results.get("variants", [])
        
        if not variants:
            return None
            
        # Find variant with highest conversion rate and statistical significance
        best_variant = None
        best_conversion_rate = 0
        
        for variant in variants:
            if variant.get("is_statistically_significant", False):
                conversion_rate = variant.get("conversion_rate", 0)
                if conversion_rate > best_conversion_rate:
                    best_conversion_rate = conversion_rate
                    best_variant = variant
                    
        if best_variant:
            return UUID(best_variant["id"])
            
        return None
        
    async def _load_experiment_with_variants(
        self,
        experiment_id: UUID,
        db: AsyncSession
    ) -> Optional[Experiment]:
        """Load experiment with variants"""
        experiment = await db.get(Experiment, experiment_id)
        
        if experiment:
            # Eager load variants
            variants_query = select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id
            )
            result = await db.execute(variants_query)
            experiment.variants = result.scalars().all()
            
        return experiment
        
    async def _load_experiment_with_data(
        self,
        experiment_id: UUID,
        db: AsyncSession
    ) -> Optional[Experiment]:
        """Load experiment with all related data"""
        experiment = await db.get(Experiment, experiment_id)
        
        if experiment:
            # Load variants
            variants_query = select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id
            )
            variants_result = await db.execute(variants_query)
            experiment.variants = variants_result.scalars().all()
            
            # Load participants count
            participants_query = select(ExperimentParticipant).where(
                ExperimentParticipant.experiment_id == experiment_id
            )
            participants_result = await db.execute(participants_query)
            experiment.participants = participants_result.scalars().all()
            
        return experiment


# Global experiment manager instance
experiment_manager = ExperimentManager()
