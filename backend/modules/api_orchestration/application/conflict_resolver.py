"""
Conflict resolution service for data from multiple APIs.

Handles conflicts when the same data exists in multiple sources with
different values.
"""
import logging
from typing import Dict, Any, Optional, List, Union, TypeVar, Generic
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.schemas import DataSource, ConflictResolution


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class DataPoint(Generic[T]):
    """Represents a data point from a specific source."""
    source: DataSource
    value: T
    timestamp: datetime
    confidence: float = 1.0  # 0-1 confidence score
    metadata: Optional[Dict[str, Any]] = None
    

@dataclass
class ConflictReport:
    """Report of conflicts found during resolution."""
    field_name: str
    values: List[DataPoint]
    resolution_method: ConflictResolution
    resolved_value: Any
    confidence: float
    

class ConflictResolver:
    """Resolves conflicts between data from multiple sources."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conflict_reports: List[ConflictReport] = []
        
    def resolve_fan_data(
        self,
        inflow_data: Optional[Dict[str, Any]],
        onlyfans_data: Optional[Dict[str, Any]],
        resolution_strategy: ConflictResolution = ConflictResolution.LATEST
    ) -> Dict[str, Any]:
        """Resolve conflicts in fan/subscriber data."""
        self.conflict_reports = []
        resolved_data = {}
        
        # Handle case where only one source has data
        if not inflow_data:
            return onlyfans_data or {}
        if not onlyfans_data:
            return inflow_data or {}
            
        # Define field resolution strategies
        field_strategies = {
            # Identity fields - prefer most complete
            "username": ConflictResolution.MERGE,
            "display_name": ConflictResolution.MERGE,
            "email": ConflictResolution.MERGE,
            "avatar_url": ConflictResolution.LATEST,
            
            # Financial fields - sum or max
            "total_spent": "sum",
            "tip_count": "sum",
            "message_count": "sum",
            "ppv_purchased_count": "sum",
            "subscription_price": "max",
            
            # Status fields - prefer active/positive
            "is_subscriber": "any_true",
            "is_paying": "any_true",
            "is_verified": "any_true",
            
            # Timestamps - latest or earliest
            "subscribed_at": "earliest",
            "expires_at": "latest",
            "last_active_at": "latest",
            "created_at": "earliest",
            
            # Other fields - use strategy
            "bio": ConflictResolution.MERGE,
            "location": ConflictResolution.LATEST,
            "metadata": "merge_dict"
        }
        
        # Get all unique fields
        all_fields = set(inflow_data.keys()) | set(onlyfans_data.keys())
        
        for field in all_fields:
            inflow_value = inflow_data.get(field)
            onlyfans_value = onlyfans_data.get(field)
            
            # Skip if values are identical
            if inflow_value == onlyfans_value:
                resolved_data[field] = inflow_value
                continue
                
            # Get resolution strategy for field
            strategy = field_strategies.get(field, resolution_strategy)
            
            # Create data points
            data_points = []
            if inflow_value is not None:
                data_points.append(DataPoint(
                    source=DataSource.INFLOW,
                    value=inflow_value,
                    timestamp=datetime.utcnow(),  # Should use actual sync time
                    confidence=0.9
                ))
            if onlyfans_value is not None:
                data_points.append(DataPoint(
                    source=DataSource.ONLYFANS,
                    value=onlyfans_value,
                    timestamp=datetime.utcnow(),
                    confidence=0.95  # OnlyFans typically more reliable
                ))
                
            # Resolve conflict
            resolved_value, confidence = self._resolve_field_conflict(
                field, data_points, strategy
            )
            
            resolved_data[field] = resolved_value
            
            # Record conflict if values differed
            if len(data_points) > 1:
                self.conflict_reports.append(ConflictReport(
                    field_name=field,
                    values=data_points,
                    resolution_method=strategy if isinstance(strategy, ConflictResolution) else ConflictResolution.MERGE,
                    resolved_value=resolved_value,
                    confidence=confidence
                ))
                
        return resolved_data
        
    def _resolve_field_conflict(
        self,
        field_name: str,
        data_points: List[DataPoint],
        strategy: Union[ConflictResolution, str]
    ) -> tuple[Any, float]:
        """Resolve conflict for a single field."""
        if not data_points:
            return None, 0.0
            
        if len(data_points) == 1:
            return data_points[0].value, data_points[0].confidence
            
        # Handle string strategies
        if isinstance(strategy, str):
            if strategy == "sum":
                return self._sum_values(data_points)
            elif strategy == "max":
                return self._max_value(data_points)
            elif strategy == "min":
                return self._min_value(data_points)
            elif strategy == "any_true":
                return self._any_true(data_points)
            elif strategy == "all_true":
                return self._all_true(data_points)
            elif strategy == "earliest":
                return self._earliest_value(data_points)
            elif strategy == "latest":
                return self._latest_value(data_points)
            elif strategy == "merge_dict":
                return self._merge_dicts(data_points)
            else:
                # Fall back to LATEST
                strategy = ConflictResolution.LATEST
                
        # Handle ConflictResolution enum strategies
        if strategy == ConflictResolution.PREFER_ONLYFANS:
            of_point = next((p for p in data_points if p.source == DataSource.ONLYFANS), None)
            if of_point:
                return of_point.value, of_point.confidence
            return data_points[0].value, data_points[0].confidence
            
        elif strategy == ConflictResolution.PREFER_INFLOW:
            if_point = next((p for p in data_points if p.source == DataSource.INFLOW), None)
            if if_point:
                return if_point.value, if_point.confidence
            return data_points[0].value, data_points[0].confidence
            
        elif strategy == ConflictResolution.LATEST:
            latest_point = max(data_points, key=lambda p: p.timestamp)
            return latest_point.value, latest_point.confidence
            
        elif strategy == ConflictResolution.MERGE:
            return self._merge_values(field_name, data_points)
            
        # Default to highest confidence
        best_point = max(data_points, key=lambda p: p.confidence)
        return best_point.value, best_point.confidence
        
    def _sum_values(self, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Sum numeric values."""
        total = 0
        value_type = type(data_points[0].value)
        
        for point in data_points:
            if isinstance(point.value, (int, float, Decimal)):
                total += point.value
                
        # Convert back to original type
        if value_type == Decimal:
            total = Decimal(str(total))
        elif value_type == int:
            total = int(total)
            
        # Confidence is average of sources
        avg_confidence = sum(p.confidence for p in data_points) / len(data_points)
        
        return total, avg_confidence
        
    def _max_value(self, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Get maximum value."""
        max_point = max(data_points, key=lambda p: p.value if p.value is not None else float('-inf'))
        return max_point.value, max_point.confidence
        
    def _min_value(self, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Get minimum value."""
        min_point = min(data_points, key=lambda p: p.value if p.value is not None else float('inf'))
        return min_point.value, min_point.confidence
        
    def _any_true(self, data_points: List[DataPoint]) -> tuple[bool, float]:
        """Return True if any value is True."""
        has_true = any(p.value is True for p in data_points)
        if has_true:
            # Confidence is highest among True values
            true_points = [p for p in data_points if p.value is True]
            max_confidence = max(p.confidence for p in true_points)
            return True, max_confidence
        else:
            # All False, average confidence
            avg_confidence = sum(p.confidence for p in data_points) / len(data_points)
            return False, avg_confidence
            
    def _all_true(self, data_points: List[DataPoint]) -> tuple[bool, float]:
        """Return True only if all values are True."""
        all_true = all(p.value is True for p in data_points)
        # Confidence is minimum among all points (weakest link)
        min_confidence = min(p.confidence for p in data_points)
        return all_true, min_confidence
        
    def _earliest_value(self, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Get value associated with earliest timestamp."""
        # Assuming value is a timestamp
        earliest_point = min(
            data_points,
            key=lambda p: p.value if isinstance(p.value, datetime) else datetime.max
        )
        return earliest_point.value, earliest_point.confidence
        
    def _latest_value(self, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Get value associated with latest timestamp."""
        # Assuming value is a timestamp
        latest_point = max(
            data_points,
            key=lambda p: p.value if isinstance(p.value, datetime) else datetime.min
        )
        return latest_point.value, latest_point.confidence
        
    def _merge_dicts(self, data_points: List[DataPoint]) -> tuple[Dict[str, Any], float]:
        """Merge dictionary values."""
        merged = {}
        for point in data_points:
            if isinstance(point.value, dict):
                merged.update(point.value)
        
        # Confidence is average
        avg_confidence = sum(p.confidence for p in data_points) / len(data_points)
        return merged, avg_confidence
        
    def _merge_values(self, field_name: str, data_points: List[DataPoint]) -> tuple[Any, float]:
        """Intelligently merge values based on field type."""
        values = [p.value for p in data_points if p.value is not None]
        
        if not values:
            return None, 0.0
            
        # For strings, prefer longer/more complete
        if all(isinstance(v, str) for v in values):
            # Remove empty strings
            values = [v for v in values if v.strip()]
            if not values:
                return "", 0.5
                
            # Prefer longer strings (likely more complete)
            longest = max(values, key=len)
            
            # Check if one contains the other
            for v in values:
                if v != longest and v in longest:
                    # Longer string contains shorter, use longer
                    point = next(p for p in data_points if p.value == longest)
                    return longest, point.confidence
                    
            # Otherwise use highest confidence
            best_point = max(data_points, key=lambda p: p.confidence)
            return best_point.value, best_point.confidence
            
        # For lists, combine unique values
        elif all(isinstance(v, list) for v in values):
            combined = []
            seen = set()
            for v_list in values:
                for item in v_list:
                    # Use hash for deduplication
                    item_hash = hashlib.md5(str(item).encode()).hexdigest()
                    if item_hash not in seen:
                        seen.add(item_hash)
                        combined.append(item)
            
            avg_confidence = sum(p.confidence for p in data_points) / len(data_points)
            return combined, avg_confidence
            
        # Default: use highest confidence
        best_point = max(data_points, key=lambda p: p.confidence)
        return best_point.value, best_point.confidence
        
    def get_conflict_summary(self) -> Dict[str, Any]:
        """Get summary of conflicts found during resolution."""
        if not self.conflict_reports:
            return {
                "has_conflicts": False,
                "conflict_count": 0,
                "reports": []
            }
            
        return {
            "has_conflicts": True,
            "conflict_count": len(self.conflict_reports),
            "reports": [
                {
                    "field": report.field_name,
                    "sources": [
                        {
                            "source": dp.source.value,
                            "value": str(dp.value)[:100],  # Truncate long values
                            "confidence": dp.confidence
                        }
                        for dp in report.values
                    ],
                    "resolution_method": report.resolution_method.value if isinstance(report.resolution_method, ConflictResolution) else report.resolution_method,
                    "resolved_value": str(report.resolved_value)[:100],
                    "confidence": report.confidence
                }
                for report in self.conflict_reports
            ],
            "average_confidence": sum(r.confidence for r in self.conflict_reports) / len(self.conflict_reports)
        }