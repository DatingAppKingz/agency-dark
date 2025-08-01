"""Model-specific conflict resolution implementation."""

from typing import Dict, Any, Optional, List
from datetime import datetime

from services.sync.conflict_resolver import (
    FieldLevelConflictResolver,
    BusinessRuleConflictResolver,
    CompositeConflictResolver,
    ConflictInfo,
    ConflictType
)
from models.model import Model
from core.logger import get_logger

logger = get_logger(__name__)


class ModelFieldConflictResolver(FieldLevelConflictResolver[Model]):
    """Field-level conflict resolver for Model entities."""
    
    def __init__(self):
        # Define field-specific rules
        field_rules = {
            # For earnings, always take the higher value (more conservative)
            "total_earnings": lambda local, remote: max(local or 0, remote or 0),
            
            # For subscriber count, take the latest (remote) value
            "subscriber_count": lambda local, remote: remote,
            
            # For sensitive fields, prefer local unless explicitly updated
            "bank_account": lambda local, remote: local if local else remote,
            
            # Concatenate tags instead of replacing
            "tags": lambda local, remote: list(set((local or []) + (remote or [])))
        }
        
        # Priority fields that should always use remote value
        priority_fields = [
            "is_active",
            "is_verified",
            "subscription_price",
            "platform_status"
        ]
        
        # Merge strategies for specific fields
        merge_strategies = {
            "bio": "remote",  # Always use latest bio
            "display_name": "remote",  # Always use latest display name
            "profile_pic": "remote",  # Always use latest profile pic
            "about": "concat",  # Concatenate if different
            "commission_rate": "max",  # Use higher commission rate
        }
        
        super().__init__(
            field_rules=field_rules,
            priority_fields=priority_fields,
            merge_strategies=merge_strategies
        )
    
    def _to_dict(self, item: Model) -> Dict[str, Any]:
        """Convert Model to dictionary."""
        return {
            "id": str(item.id),
            "username": item.username,
            "display_name": item.display_name,
            "bio": item.bio,
            "about": item.about,
            "profile_pic": item.profile_pic,
            "is_active": item.is_active,
            "is_verified": item.is_verified,
            "subscriber_count": item.subscriber_count,
            "total_earnings": item.total_earnings,
            "subscription_price": item.subscription_price,
            "commission_rate": item.commission_rate,
            "tags": item.tags,
            "bank_account": item.bank_account,
            "platform_status": item.platform_status,
            "inflow_id": item.inflow_id,
            "onlyfans_id": item.onlyfans_id,
            "updated_at": item.updated_at
        }
    
    def _from_dict(self, data: Dict[str, Any], template: Model) -> Model:
        """Create Model from dictionary."""
        # Create a copy of the template and update with merged data
        for key, value in data.items():
            if hasattr(template, key) and key not in ["id", "created_at"]:
                setattr(template, key, value)
        return template
    
    def _get_id(self, item: Model) -> str:
        """Get Model ID."""
        return str(item.id)
    
    def _get_timestamp(self, item: Model) -> Optional[datetime]:
        """Get Model timestamp."""
        return item.updated_at


class ModelBusinessRuleResolver(BusinessRuleConflictResolver[Model]):
    """Business rule conflict resolver for Model entities."""
    
    def __init__(self):
        rules = [
            self._check_commission_rate_change,
            self._check_earnings_discrepancy,
            self._check_verification_status,
            self._check_platform_status_consistency
        ]
        super().__init__(rules)
    
    def _check_commission_rate_change(self, local: Model, remote: Model):
        """Check if commission rate change exceeds threshold."""
        if local.commission_rate and remote.commission_rate:
            diff = abs(local.commission_rate - remote.commission_rate)
            if diff > 10:  # More than 10% change
                return True, f"Commission rate change exceeds 10%: {local.commission_rate}% -> {remote.commission_rate}%"
        return False, None
    
    def _check_earnings_discrepancy(self, local: Model, remote: Model):
        """Check for significant earnings discrepancy."""
        if local.total_earnings and remote.total_earnings:
            diff = abs(local.total_earnings - remote.total_earnings)
            if diff > 1000:  # More than $1000 difference
                return True, f"Earnings discrepancy exceeds $1000: ${local.total_earnings} vs ${remote.total_earnings}"
        return False, None
    
    def _check_verification_status(self, local: Model, remote: Model):
        """Check if verification status is being downgraded."""
        if local.is_verified and not remote.is_verified:
            return True, "Model verification status is being downgraded"
        return False, None
    
    def _check_platform_status_consistency(self, local: Model, remote: Model):
        """Check for platform status consistency."""
        if local.platform_status == "active" and remote.platform_status == "banned":
            return True, "Model status changed from active to banned"
        return False, None
    
    def _get_id(self, item: Model) -> str:
        """Get Model ID."""
        return str(item.id)


class ModelSyncConflictResolver(CompositeConflictResolver[Model]):
    """Complete conflict resolver for Model sync operations."""
    
    def __init__(self):
        resolvers = [
            ModelFieldConflictResolver(),
            ModelBusinessRuleResolver()
        ]
        super().__init__(resolvers)
    
    async def resolve_conflicts_batch(
        self,
        conflicts: List[tuple[Model, Model, ConflictInfo]],
        strategy: str = "auto"
    ) -> Dict[str, Any]:
        """Resolve multiple conflicts in a batch."""
        results = {
            "resolved": [],
            "manual_review": [],
            "skipped": [],
            "errors": []
        }
        
        for local_item, remote_item, conflict in conflicts:
            try:
                resolution = await self.resolve_conflict(
                    conflict, local_item, remote_item, strategy
                )
                
                if resolution.manual_review_required:
                    results["manual_review"].append({
                        "local_id": conflict.local_id,
                        "remote_id": conflict.remote_id,
                        "conflict": conflict,
                        "resolution": resolution
                    })
                elif resolution.action.value == "skip":
                    results["skipped"].append(conflict.local_id)
                else:
                    results["resolved"].append({
                        "id": conflict.local_id,
                        "action": resolution.action.value,
                        "data": resolution.resolved_data
                    })
                    
            except Exception as e:
                logger.error(f"Failed to resolve conflict for {conflict.local_id}: {e}")
                results["errors"].append({
                    "id": conflict.local_id,
                    "error": str(e)
                })
        
        return results


def create_default_model_resolver():
    """Create a default model conflict resolver with standard configuration."""
    return ModelSyncConflictResolver()