"""
Traffic Splitter - Assigns participants to experiment variants
"""
import hashlib
import random
from typing import Dict, List, Any, Optional
from uuid import UUID

from core.logging import get_logger
from ..domain.models import ExperimentVariant, AllocationMethod

logger = get_logger(__name__)


class TrafficSplitter:
    """Handles participant assignment to experiment variants"""
    
    def __init__(self):
        self._allocation_methods = {
            AllocationMethod.RANDOM.value: self._random_allocation,
            AllocationMethod.DETERMINISTIC.value: self._deterministic_allocation,
            AllocationMethod.WEIGHTED.value: self._weighted_allocation,
            AllocationMethod.SEQUENTIAL.value: self._sequential_allocation
        }
        self._sequence_counters = {}
        
    async def assign_variant(
        self,
        experiment_data: Dict[str, Any],
        participant_type: str,
        participant_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[ExperimentVariant]:
        """Assign a participant to a variant"""
        experiment = experiment_data.get("experiment", {})
        variants = experiment_data.get("variants", [])
        
        if not variants:
            logger.error("No variants available for assignment")
            return None
            
        allocation_method = experiment.get("allocation_method", AllocationMethod.RANDOM.value)
        allocation_config = experiment.get("allocation_config", {})
        
        # Get allocation function
        allocation_func = self._allocation_methods.get(allocation_method)
        
        if not allocation_func:
            logger.error(f"Unknown allocation method: {allocation_method}")
            return self._random_allocation(variants, participant_type, participant_id, allocation_config)
            
        # Convert variant data to objects
        variant_objects = [ExperimentVariant(**v) for v in variants]
        
        # Assign variant
        selected_variant = allocation_func(
            variant_objects,
            participant_type,
            participant_id,
            allocation_config
        )
        
        if selected_variant:
            logger.info(
                f"Assigned {participant_type}:{participant_id} to variant "
                f"{selected_variant.name} using {allocation_method}"
            )
            
        return selected_variant
        
    def _random_allocation(
        self,
        variants: List[ExperimentVariant],
        participant_type: str,
        participant_id: str,
        config: Dict[str, Any]
    ) -> Optional[ExperimentVariant]:
        """Random allocation based on percentages"""
        # Use weighted random if percentages don't match
        if not all(v.allocation_percentage == variants[0].allocation_percentage for v in variants):
            return self._weighted_allocation(variants, participant_type, participant_id, config)
            
        # Equal probability random
        return random.choice(variants)
        
    def _deterministic_allocation(
        self,
        variants: List[ExperimentVariant],
        participant_type: str,
        participant_id: str,
        config: Dict[str, Any]
    ) -> Optional[ExperimentVariant]:
        """Deterministic allocation based on participant ID hash"""
        # Create stable hash
        hash_input = f"{participant_type}:{participant_id}"
        
        # Add salt if configured
        salt = config.get("salt", "")
        if salt:
            hash_input += f":{salt}"
            
        # Generate hash
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Convert to number between 0 and 1
        hash_number = int(hash_value[:8], 16) / 0xFFFFFFFF
        
        # Assign based on allocation percentages
        cumulative = 0.0
        
        for variant in variants:
            cumulative += variant.allocation_percentage / 100.0
            if hash_number <= cumulative:
                return variant
                
        # Fallback to last variant
        return variants[-1] if variants else None
        
    def _weighted_allocation(
        self,
        variants: List[ExperimentVariant],
        participant_type: str,
        participant_id: str,
        config: Dict[str, Any]
    ) -> Optional[ExperimentVariant]:
        """Weighted random allocation based on percentages"""
        # Create weighted list
        weights = [v.allocation_percentage for v in variants]
        
        # Normalize weights if they don't sum to 100
        total_weight = sum(weights)
        if total_weight != 100:
            weights = [w * 100 / total_weight for w in weights]
            
        # Select variant
        return random.choices(variants, weights=weights)[0]
        
    def _sequential_allocation(
        self,
        variants: List[ExperimentVariant],
        participant_type: str,
        participant_id: str,
        config: Dict[str, Any]
    ) -> Optional[ExperimentVariant]:
        """Sequential round-robin allocation"""
        experiment_id = config.get("experiment_id", "default")
        
        # Get or initialize counter
        if experiment_id not in self._sequence_counters:
            self._sequence_counters[experiment_id] = 0
            
        # Get current index
        current_index = self._sequence_counters[experiment_id]
        
        # Select variant
        selected_variant = variants[current_index % len(variants)]
        
        # Increment counter
        self._sequence_counters[experiment_id] += 1
        
        return selected_variant
        
    def calculate_required_sample_size(
        self,
        baseline_conversion_rate: float,
        minimum_detectable_effect: float,
        confidence_level: float = 0.95,
        power: float = 0.8,
        variants_count: int = 2
    ) -> int:
        """Calculate required sample size for statistical significance"""
        from scipy import stats
        import numpy as np
        
        # Z-scores for confidence level and power
        alpha = 1 - confidence_level
        z_alpha = stats.norm.ppf(1 - alpha / 2)  # Two-tailed test
        z_beta = stats.norm.ppf(power)
        
        # Calculate effect size
        p1 = baseline_conversion_rate
        p2 = baseline_conversion_rate * (1 + minimum_detectable_effect)
        
        # Pooled probability
        p_pooled = (p1 + p2) / 2
        
        # Sample size per variant
        n_per_variant = (
            (z_alpha + z_beta) ** 2 * 
            (p1 * (1 - p1) + p2 * (1 - p2)) / 
            (p1 - p2) ** 2
        )
        
        # Total sample size
        total_sample_size = int(np.ceil(n_per_variant * variants_count))
        
        return total_sample_size
        
    def estimate_experiment_duration(
        self,
        required_sample_size: int,
        daily_traffic: int,
        allocation_percentage: float = 100.0
    ) -> int:
        """Estimate how many days needed to reach sample size"""
        if daily_traffic <= 0:
            return 0
            
        # Adjust for allocation percentage
        effective_daily_traffic = daily_traffic * (allocation_percentage / 100.0)
        
        if effective_daily_traffic <= 0:
            return 0
            
        # Calculate days needed
        days_needed = required_sample_size / effective_daily_traffic
        
        # Round up
        return int(days_needed + 0.5)
        
    def validate_allocation_config(
        self,
        variants: List[Dict[str, Any]],
        allocation_method: str
    ) -> Dict[str, Any]:
        """Validate allocation configuration"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check total allocation
        total_allocation = sum(v.get("allocation_percentage", 0) for v in variants)
        
        if abs(total_allocation - 100.0) > 0.01:
            result["valid"] = False
            result["errors"].append(
                f"Total allocation must equal 100%, got {total_allocation:.2f}%"
            )
            
        # Check minimum allocation
        for variant in variants:
            allocation = variant.get("allocation_percentage", 0)
            if allocation < 5:
                result["warnings"].append(
                    f"Variant '{variant.get('name')}' has low allocation ({allocation}%), "
                    "may take longer to reach statistical significance"
                )
                
        # Method-specific validation
        if allocation_method == AllocationMethod.SEQUENTIAL.value:
            if len(variants) > 10:
                result["warnings"].append(
                    "Sequential allocation with many variants may create uneven distribution "
                    "if experiment is stopped early"
                )
                
        return result
