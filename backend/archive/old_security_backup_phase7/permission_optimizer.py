"""
Permission evaluation optimization module.

Provides optimized permission evaluation, decision caching,
and fast permission resolution algorithms.
"""
import asyncio
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict
import bisect

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope,
    DataSensitivity, ExportFormat
)
from core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class PermissionDecision:
    """Optimized permission decision structure."""
    allowed: bool
    reason: Optional[str] = None
    permission_id: Optional[str] = None
    cache_key: Optional[str] = None
    evaluation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PermissionEvaluationStrategy(Enum):
    """Permission evaluation strategies."""
    FIRST_MATCH = "first_match"  # Stop at first definitive result
    MOST_PERMISSIVE = "most_permissive"  # Find most permissive permission
    MOST_RESTRICTIVE = "most_restrictive"  # Find most restrictive permission
    WEIGHTED = "weighted"  # Use weighted scoring


class OptimizedPermissionEvaluator:
    """Optimized permission evaluation engine."""
    
    def __init__(
        self,
        strategy: PermissionEvaluationStrategy = PermissionEvaluationStrategy.FIRST_MATCH
    ):
        self.strategy = strategy
        self.decision_cache = {}
        self.evaluation_metrics = defaultdict(int)
        
        # Pre-compiled permission rules for fast evaluation
        self.compiled_rules = {}
        
        # Permission priority index for fast lookup
        self.priority_index = defaultdict(list)
    
    async def evaluate_permissions(
        self,
        user: User,
        permissions: List[FeaturePermission],
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PermissionDecision:
        """Evaluate permissions using optimized algorithm."""
        start_time = time.time()
        
        # Check decision cache
        cache_key = self._generate_cache_key(user, action, context)
        if cache_key in self.decision_cache:
            self.evaluation_metrics["cache_hits"] += 1
            cached = self.decision_cache[cache_key]
            cached.evaluation_time_ms = (time.time() - start_time) * 1000
            return cached
        
        # Sort permissions by priority (already sorted in most cases)
        sorted_perms = self._sort_permissions_optimized(permissions)
        
        # Evaluate based on strategy
        if self.strategy == PermissionEvaluationStrategy.FIRST_MATCH:
            decision = await self._evaluate_first_match(
                user, sorted_perms, action, context
            )
        elif self.strategy == PermissionEvaluationStrategy.MOST_PERMISSIVE:
            decision = await self._evaluate_most_permissive(
                user, sorted_perms, action, context
            )
        elif self.strategy == PermissionEvaluationStrategy.MOST_RESTRICTIVE:
            decision = await self._evaluate_most_restrictive(
                user, sorted_perms, action, context
            )
        else:  # WEIGHTED
            decision = await self._evaluate_weighted(
                user, sorted_perms, action, context
            )
        
        # Record metrics
        evaluation_time = (time.time() - start_time) * 1000
        decision.evaluation_time_ms = evaluation_time
        self.evaluation_metrics["total_evaluations"] += 1
        self.evaluation_metrics["total_time_ms"] += evaluation_time
        
        # Cache decision
        self.decision_cache[cache_key] = decision
        
        return decision
    
    def _sort_permissions_optimized(
        self,
        permissions: List[FeaturePermission]
    ) -> List[FeaturePermission]:
        """Sort permissions using optimized algorithm."""
        # Use numpy for fast sorting if many permissions
        if len(permissions) > 100:
            priorities = np.array([p.priority for p in permissions])
            sorted_indices = np.argsort(priorities)[::-1]  # Descending
            return [permissions[i] for i in sorted_indices]
        else:
            # Use built-in sort for small lists
            return sorted(permissions, key=lambda p: p.priority, reverse=True)
    
    async def _evaluate_first_match(
        self,
        user: User,
        permissions: List[FeaturePermission],
        action: str,
        context: Optional[Dict[str, Any]]
    ) -> PermissionDecision:
        """Evaluate using first match strategy."""
        for perm in permissions:
            # Quick deny check
            if action in perm.denied_actions:
                return PermissionDecision(
                    allowed=False,
                    reason=f"Action explicitly denied by permission {perm.id}",
                    permission_id=str(perm.id)
                )
            
            # Quick allow check
            if action in perm.allowed_actions or "*" in perm.allowed_actions:
                # Check additional constraints
                if await self._check_constraints_optimized(user, perm, context):
                    return PermissionDecision(
                        allowed=True,
                        permission_id=str(perm.id)
                    )
        
        # No match found
        return PermissionDecision(
            allowed=False,
            reason="No matching permission found"
        )
    
    async def _evaluate_most_permissive(
        self,
        user: User,
        permissions: List[FeaturePermission],
        action: str,
        context: Optional[Dict[str, Any]]
    ) -> PermissionDecision:
        """Find most permissive permission."""
        allowed_permissions = []
        
        for perm in permissions:
            # Skip if explicitly denied
            if action in perm.denied_actions:
                continue
            
            # Check if allowed
            if action in perm.allowed_actions or "*" in perm.allowed_actions:
                if await self._check_constraints_optimized(user, perm, context):
                    allowed_permissions.append(perm)
        
        if allowed_permissions:
            # Find most permissive (e.g., highest limits, broadest scope)
            best_perm = self._find_most_permissive(allowed_permissions)
            return PermissionDecision(
                allowed=True,
                permission_id=str(best_perm.id),
                metadata={"permissions_evaluated": len(permissions)}
            )
        
        return PermissionDecision(
            allowed=False,
            reason="No permissive permission found"
        )
    
    async def _evaluate_most_restrictive(
        self,
        user: User,
        permissions: List[FeaturePermission],
        action: str,
        context: Optional[Dict[str, Any]]
    ) -> PermissionDecision:
        """Find most restrictive permission that still allows access."""
        # Check for any explicit denials first
        for perm in permissions:
            if action in perm.denied_actions:
                return PermissionDecision(
                    allowed=False,
                    reason=f"Action explicitly denied by permission {perm.id}",
                    permission_id=str(perm.id)
                )
        
        # Find allowed permissions
        allowed_permissions = []
        for perm in permissions:
            if action in perm.allowed_actions or "*" in perm.allowed_actions:
                if await self._check_constraints_optimized(user, perm, context):
                    allowed_permissions.append(perm)
        
        if allowed_permissions:
            # Find most restrictive
            most_restrictive = self._find_most_restrictive(allowed_permissions)
            return PermissionDecision(
                allowed=True,
                permission_id=str(most_restrictive.id),
                metadata={"restrictions_applied": True}
            )
        
        return PermissionDecision(
            allowed=False,
            reason="No permission allows this action"
        )
    
    async def _evaluate_weighted(
        self,
        user: User,
        permissions: List[FeaturePermission],
        action: str,
        context: Optional[Dict[str, Any]]
    ) -> PermissionDecision:
        """Evaluate using weighted scoring."""
        scores = []
        
        for perm in permissions:
            score = 0.0
            
            # Explicit deny is -100
            if action in perm.denied_actions:
                scores.append((perm, -100.0))
                continue
            
            # Base score for allow
            if action in perm.allowed_actions:
                score += 50.0
            elif "*" in perm.allowed_actions:
                score += 25.0
            else:
                continue
            
            # Priority weight
            score += perm.priority * 0.5
            
            # Constraint checks
            if await self._check_constraints_optimized(user, perm, context):
                score += 10.0
            else:
                score -= 20.0
            
            scores.append((perm, score))
        
        if not scores:
            return PermissionDecision(
                allowed=False,
                reason="No applicable permissions"
            )
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        best_perm, best_score = scores[0]
        
        if best_score > 0:
            return PermissionDecision(
                allowed=True,
                permission_id=str(best_perm.id),
                metadata={"score": best_score, "total_evaluated": len(scores)}
            )
        else:
            return PermissionDecision(
                allowed=False,
                reason="Permission score too low",
                metadata={"score": best_score}
            )
    
    async def _check_constraints_optimized(
        self,
        user: User,
        permission: FeaturePermission,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check permission constraints with optimizations."""
        # Time constraint check (fast)
        if not self._check_time_constraint_fast(permission):
            return False
        
        # Context-based checks
        if context:
            # Data sensitivity check
            if "data_sensitivity" in context:
                if not self._check_data_sensitivity_fast(
                    permission, context["data_sensitivity"]
                ):
                    return False
            
            # Scope check
            if "scope" in context:
                if not self._check_scope_fast(permission, context["scope"]):
                    return False
        
        # MFA check
        if permission.requires_mfa and context:
            if not context.get("mfa_verified", False):
                return False
        
        return True
    
    def _check_time_constraint_fast(self, permission: FeaturePermission) -> bool:
        """Fast time constraint check."""
        if not permission.access_start_time or not permission.access_end_time:
            return True
        
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Parse time strings (cached)
        start_hour, start_min = map(int, permission.access_start_time.split(":"))
        end_hour, end_min = map(int, permission.access_end_time.split(":"))
        
        current_minutes = current_hour * 60 + current_minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes <= end_minutes
        else:
            # Spans midnight
            return current_minutes >= start_minutes or current_minutes <= end_minutes
    
    def _check_data_sensitivity_fast(
        self,
        permission: FeaturePermission,
        required_sensitivity: DataSensitivity
    ) -> bool:
        """Fast data sensitivity check."""
        # Use numeric comparison for enum values
        perm_level = permission.max_data_sensitivity.value if permission.max_data_sensitivity else 100
        required_level = required_sensitivity.value
        
        return perm_level >= required_level
    
    def _check_scope_fast(
        self,
        permission: FeaturePermission,
        required_scope: AnalyticsScope
    ) -> bool:
        """Fast scope check."""
        if not hasattr(permission, 'analytics_scope'):
            return True
        
        # Scope hierarchy: GLOBAL > AGENCY > TEAM > OWN
        scope_hierarchy = {
            AnalyticsScope.OWN: 1,
            AnalyticsScope.TEAM: 2,
            AnalyticsScope.AGENCY: 3,
            AnalyticsScope.GLOBAL: 4
        }
        
        perm_level = scope_hierarchy.get(permission.analytics_scope, 0)
        required_level = scope_hierarchy.get(required_scope, 5)
        
        return perm_level >= required_level
    
    def _find_most_permissive(
        self,
        permissions: List[FeaturePermission]
    ) -> FeaturePermission:
        """Find most permissive permission from list."""
        best = permissions[0]
        best_score = self._calculate_permissiveness_score(best)
        
        for perm in permissions[1:]:
            score = self._calculate_permissiveness_score(perm)
            if score > best_score:
                best = perm
                best_score = score
        
        return best
    
    def _find_most_restrictive(
        self,
        permissions: List[FeaturePermission]
    ) -> FeaturePermission:
        """Find most restrictive permission from list."""
        best = permissions[0]
        best_score = self._calculate_permissiveness_score(best)
        
        for perm in permissions[1:]:
            score = self._calculate_permissiveness_score(perm)
            if score < best_score:
                best = perm
                best_score = score
        
        return best
    
    def _calculate_permissiveness_score(self, permission: FeaturePermission) -> float:
        """Calculate how permissive a permission is."""
        score = 0.0
        
        # More allowed actions = more permissive
        score += len(permission.allowed_actions) * 10
        
        # Wildcard is very permissive
        if "*" in permission.allowed_actions:
            score += 100
        
        # Less denied actions = more permissive
        score -= len(permission.denied_actions) * 5
        
        # Higher limits = more permissive
        if hasattr(permission, 'max_export_rows'):
            score += (permission.max_export_rows or 0) / 1000
        
        # Broader scope = more permissive
        if hasattr(permission, 'analytics_scope'):
            scope_scores = {
                AnalyticsScope.OWN: 10,
                AnalyticsScope.TEAM: 20,
                AnalyticsScope.AGENCY: 30,
                AnalyticsScope.GLOBAL: 40
            }
            score += scope_scores.get(permission.analytics_scope, 0)
        
        return score
    
    def _generate_cache_key(
        self,
        user: User,
        action: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for permission decision."""
        key_parts = [
            str(user.id),
            str(user.role.value),
            action
        ]
        
        if context:
            # Include relevant context in key
            for k in sorted(["scope", "data_sensitivity", "mfa_verified"]):
                if k in context:
                    key_parts.append(f"{k}:{context[k]}")
        
        return ":".join(key_parts)
    
    def get_evaluation_metrics(self) -> Dict[str, Any]:
        """Get evaluation performance metrics."""
        total_evals = self.evaluation_metrics["total_evaluations"]
        
        return {
            "total_evaluations": total_evals,
            "cache_hits": self.evaluation_metrics["cache_hits"],
            "cache_hit_rate": (
                self.evaluation_metrics["cache_hits"] / total_evals
                if total_evals > 0 else 0
            ),
            "avg_evaluation_time_ms": (
                self.evaluation_metrics["total_time_ms"] / total_evals
                if total_evals > 0 else 0
            ),
            "cache_size": len(self.decision_cache)
        }
    
    def clear_cache(self):
        """Clear decision cache."""
        self.decision_cache.clear()
        logger.info("Permission decision cache cleared")


class PermissionIndexer:
    """Fast permission indexing for quick lookups."""
    
    def __init__(self):
        self.action_index = defaultdict(list)
        self.feature_index = defaultdict(list)
        self.user_index = defaultdict(list)
        self.role_index = defaultdict(list)
        
        # Bitmap indexes for fast filtering
        self.active_bitmap = set()
        self.mfa_required_bitmap = set()
    
    def index_permissions(self, permissions: List[FeaturePermission]):
        """Build indexes for fast permission lookup."""
        for perm in permissions:
            perm_id = str(perm.id)
            
            # Action index
            for action in perm.allowed_actions:
                self.action_index[action].append(perm)
            
            # Feature index
            self.feature_index[perm.feature_type].append(perm)
            
            # User/Role index
            if perm.user_id:
                self.user_index[str(perm.user_id)].append(perm)
            if perm.role_id:
                self.role_index[str(perm.role_id)].append(perm)
            
            # Bitmap indexes
            if perm.is_active:
                self.active_bitmap.add(perm_id)
            if perm.requires_mfa:
                self.mfa_required_bitmap.add(perm_id)
    
    def find_permissions_for_action(
        self,
        action: str,
        user_id: Optional[str] = None,
        feature_type: Optional[FeatureType] = None
    ) -> List[FeaturePermission]:
        """Find permissions for a specific action using indexes."""
        # Start with action index
        candidates = set(self.action_index.get(action, []))
        
        # Add wildcard permissions
        candidates.update(self.action_index.get("*", []))
        
        # Filter by user if specified
        if user_id:
            user_perms = set(self.user_index.get(user_id, []))
            candidates = candidates.intersection(user_perms)
        
        # Filter by feature type if specified
        if feature_type:
            feature_perms = set(self.feature_index.get(feature_type, []))
            candidates = candidates.intersection(feature_perms)
        
        # Filter only active permissions
        candidates = [
            p for p in candidates
            if str(p.id) in self.active_bitmap
        ]
        
        return list(candidates)


# Global instances
permission_evaluator = OptimizedPermissionEvaluator(
    strategy=PermissionEvaluationStrategy.FIRST_MATCH
)
permission_indexer = PermissionIndexer()


# Helper functions for common patterns
async def check_permission_fast(
    user: User,
    feature_type: FeatureType,
    action: str,
    permissions: List[FeaturePermission],
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """Fast permission check using optimized evaluator."""
    decision = await permission_evaluator.evaluate_permissions(
        user, permissions, action, context
    )
    
    return decision.allowed, decision.reason


def precompile_permission_rules(permissions: List[FeaturePermission]):
    """Precompile permission rules for faster evaluation."""
    # Index permissions for fast lookup
    permission_indexer.index_permissions(permissions)
    
    # Pre-calculate permission scores
    for perm in permissions:
        perm._permissiveness_score = (
            permission_evaluator._calculate_permissiveness_score(perm)
        )
    
    logger.info(f"Precompiled {len(permissions)} permission rules")