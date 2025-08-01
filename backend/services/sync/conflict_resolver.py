"""Enhanced conflict resolution for sync operations."""

from typing import Any, Dict, List, Optional, Tuple, TypeVar, Generic, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import hashlib
import json

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ConflictType(Enum):
    """Types of conflicts that can occur during sync."""
    CONCURRENT_UPDATE = "concurrent_update"
    SCHEMA_MISMATCH = "schema_mismatch"
    DATA_VALIDATION = "data_validation"
    BUSINESS_RULE = "business_rule"
    DELETE_MODIFIED = "delete_modified"
    DUPLICATE_KEY = "duplicate_key"


class ResolutionAction(Enum):
    """Actions to take when resolving conflicts."""
    KEEP_LOCAL = "keep_local"
    KEEP_REMOTE = "keep_remote"
    MERGE = "merge"
    MANUAL = "manual"
    SKIP = "skip"
    RETRY = "retry"


@dataclass
class ConflictInfo:
    """Detailed information about a conflict."""
    conflict_type: ConflictType
    local_id: str
    remote_id: str
    field_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    local_timestamp: Optional[datetime] = None
    remote_timestamp: Optional[datetime] = None
    local_version: Optional[int] = None
    remote_version: Optional[int] = None
    local_checksum: Optional[str] = None
    remote_checksum: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    action: ResolutionAction
    resolved_data: Optional[Any] = None
    merge_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    manual_review_required: bool = False
    retry_after: Optional[int] = None
    notes: Optional[str] = None


class ConflictResolver(ABC, Generic[T]):
    """Base class for conflict resolution strategies."""
    
    @abstractmethod
    async def detect_conflicts(
        self,
        local_item: T,
        remote_item: T
    ) -> List[ConflictInfo]:
        """Detect all conflicts between local and remote items."""
        pass
    
    @abstractmethod
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        local_item: T,
        remote_item: T,
        strategy: str = "auto"
    ) -> ResolutionResult:
        """Resolve a specific conflict."""
        pass
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for conflict detection."""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(sorted_data.encode()).hexdigest()


class FieldLevelConflictResolver(ConflictResolver[T]):
    """Resolves conflicts at the field level with custom rules."""
    
    def __init__(
        self,
        field_rules: Optional[Dict[str, Callable]] = None,
        priority_fields: Optional[List[str]] = None,
        merge_strategies: Optional[Dict[str, str]] = None
    ):
        self.field_rules = field_rules or {}
        self.priority_fields = priority_fields or []
        self.merge_strategies = merge_strategies or {}
    
    async def detect_conflicts(
        self,
        local_item: T,
        remote_item: T
    ) -> List[ConflictInfo]:
        """Detect field-level conflicts."""
        conflicts = []
        
        local_dict = self._to_dict(local_item)
        remote_dict = self._to_dict(remote_item)
        
        # Track field differences
        field_conflicts = []
        for field in set(local_dict.keys()) | set(remote_dict.keys()):
            local_val = local_dict.get(field)
            remote_val = remote_dict.get(field)
            
            if local_val != remote_val:
                field_conflicts.append({
                    "field": field,
                    "local_value": local_val,
                    "remote_value": remote_val,
                    "is_priority": field in self.priority_fields
                })
        
        if field_conflicts:
            conflict = ConflictInfo(
                conflict_type=ConflictType.CONCURRENT_UPDATE,
                local_id=self._get_id(local_item),
                remote_id=self._get_id(remote_item),
                field_conflicts=field_conflicts,
                local_timestamp=self._get_timestamp(local_item),
                remote_timestamp=self._get_timestamp(remote_item),
                local_checksum=self.calculate_checksum(local_dict),
                remote_checksum=self.calculate_checksum(remote_dict)
            )
            conflicts.append(conflict)
        
        return conflicts
    
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        local_item: T,
        remote_item: T,
        strategy: str = "auto"
    ) -> ResolutionResult:
        """Resolve field-level conflicts using configured rules."""
        
        if strategy == "local":
            return ResolutionResult(
                action=ResolutionAction.KEEP_LOCAL,
                resolved_data=local_item
            )
        elif strategy == "remote":
            return ResolutionResult(
                action=ResolutionAction.KEEP_REMOTE,
                resolved_data=remote_item
            )
        
        # Auto resolution with field-level rules
        local_dict = self._to_dict(local_item)
        remote_dict = self._to_dict(remote_item)
        merged_dict = {}
        merge_conflicts = []
        
        for field_conflict in conflict.field_conflicts:
            field = field_conflict["field"]
            local_val = field_conflict["local_value"]
            remote_val = field_conflict["remote_value"]
            
            # Apply custom field rule if exists
            if field in self.field_rules:
                try:
                    resolved_val = self.field_rules[field](local_val, remote_val)
                    merged_dict[field] = resolved_val
                except Exception as e:
                    logger.warning(f"Field rule failed for {field}: {e}")
                    merge_conflicts.append({
                        "field": field,
                        "error": str(e),
                        "local_value": local_val,
                        "remote_value": remote_val
                    })
            
            # Apply merge strategy
            elif field in self.merge_strategies:
                strategy = self.merge_strategies[field]
                if strategy == "concat":
                    merged_dict[field] = f"{local_val} {remote_val}"
                elif strategy == "max":
                    merged_dict[field] = max(local_val, remote_val)
                elif strategy == "min":
                    merged_dict[field] = min(local_val, remote_val)
                elif strategy == "local":
                    merged_dict[field] = local_val
                elif strategy == "remote":
                    merged_dict[field] = remote_val
                else:
                    merge_conflicts.append({
                        "field": field,
                        "reason": f"Unknown strategy: {strategy}"
                    })
            
            # Use timestamp-based resolution
            elif conflict.local_timestamp and conflict.remote_timestamp:
                if conflict.remote_timestamp > conflict.local_timestamp:
                    merged_dict[field] = remote_val
                else:
                    merged_dict[field] = local_val
            
            # Priority fields always take remote value
            elif field in self.priority_fields:
                merged_dict[field] = remote_val
            
            # Default to remote value
            else:
                merged_dict[field] = remote_val
        
        # Add non-conflicting fields
        for field in set(local_dict.keys()) | set(remote_dict.keys()):
            if field not in merged_dict:
                merged_dict[field] = remote_dict.get(field, local_dict.get(field))
        
        # Create resolved item
        resolved_item = self._from_dict(merged_dict, local_item)
        
        return ResolutionResult(
            action=ResolutionAction.MERGE if not merge_conflicts else ResolutionAction.MANUAL,
            resolved_data=resolved_item,
            merge_conflicts=merge_conflicts,
            manual_review_required=bool(merge_conflicts)
        )
    
    @abstractmethod
    def _to_dict(self, item: T) -> Dict[str, Any]:
        """Convert item to dictionary for comparison."""
        pass
    
    @abstractmethod
    def _from_dict(self, data: Dict[str, Any], template: T) -> T:
        """Create item from dictionary."""
        pass
    
    @abstractmethod
    def _get_id(self, item: T) -> str:
        """Get item ID."""
        pass
    
    @abstractmethod
    def _get_timestamp(self, item: T) -> Optional[datetime]:
        """Get item timestamp."""
        pass


class BusinessRuleConflictResolver(ConflictResolver[T]):
    """Resolves conflicts based on business rules."""
    
    def __init__(self, rules: List[Callable[[T, T], Tuple[bool, Optional[str]]]]):
        self.rules = rules
    
    async def detect_conflicts(
        self,
        local_item: T,
        remote_item: T
    ) -> List[ConflictInfo]:
        """Detect business rule violations."""
        conflicts = []
        
        for rule in self.rules:
            try:
                is_conflict, reason = rule(local_item, remote_item)
                if is_conflict:
                    conflict = ConflictInfo(
                        conflict_type=ConflictType.BUSINESS_RULE,
                        local_id=self._get_id(local_item),
                        remote_id=self._get_id(remote_item),
                        additional_context={"reason": reason or "Business rule violation"}
                    )
                    conflicts.append(conflict)
            except Exception as e:
                logger.error(f"Business rule check failed: {e}")
        
        return conflicts
    
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        local_item: T,
        remote_item: T,
        strategy: str = "auto"
    ) -> ResolutionResult:
        """Business rule conflicts typically require manual resolution."""
        return ResolutionResult(
            action=ResolutionAction.MANUAL,
            manual_review_required=True,
            notes=conflict.additional_context.get("reason", "Business rule violation")
        )
    
    @abstractmethod
    def _get_id(self, item: T) -> str:
        """Get item ID."""
        pass


class CompositeConflictResolver(ConflictResolver[T]):
    """Combines multiple conflict resolvers."""
    
    def __init__(self, resolvers: List[ConflictResolver[T]]):
        self.resolvers = resolvers
    
    async def detect_conflicts(
        self,
        local_item: T,
        remote_item: T
    ) -> List[ConflictInfo]:
        """Detect conflicts using all resolvers."""
        all_conflicts = []
        
        for resolver in self.resolvers:
            conflicts = await resolver.detect_conflicts(local_item, remote_item)
            all_conflicts.extend(conflicts)
        
        return all_conflicts
    
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        local_item: T,
        remote_item: T,
        strategy: str = "auto"
    ) -> ResolutionResult:
        """Resolve conflict using the appropriate resolver."""
        # Find the resolver that can handle this conflict type
        for resolver in self.resolvers:
            conflicts = await resolver.detect_conflicts(local_item, remote_item)
            if any(c.conflict_type == conflict.conflict_type for c in conflicts):
                return await resolver.resolve_conflict(
                    conflict, local_item, remote_item, strategy
                )
        
        # Default to manual resolution
        return ResolutionResult(
            action=ResolutionAction.MANUAL,
            manual_review_required=True,
            notes="No resolver available for this conflict type"
        )


class ConflictResolutionLogger:
    """Logs conflict resolution decisions for audit."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def log_conflict(
        self,
        conflict: ConflictInfo,
        resolution: ResolutionResult,
        user_id: Optional[str] = None,
        sync_job_id: Optional[str] = None
    ):
        """Log conflict resolution decision."""
        from models.sync_conflict_log import SyncConflictLog
        
        log_entry = SyncConflictLog(
            sync_job_id=sync_job_id,
            conflict_type=conflict.conflict_type.value,
            local_id=conflict.local_id,
            remote_id=conflict.remote_id,
            resolution_action=resolution.action.value,
            field_conflicts=conflict.field_conflicts,
            merge_conflicts=resolution.merge_conflicts,
            manual_review_required=resolution.manual_review_required,
            resolved_by=user_id,
            resolved_at=datetime.utcnow() if resolution.action != ResolutionAction.MANUAL else None,
            notes=resolution.notes
        )
        
        self.db.add(log_entry)
        await self.db.commit()
        
        return log_entry