"""
Tests for conflict resolution service.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from modules.api_orchestration.application.conflict_resolver import (
    ConflictResolver,
    DataPoint,
    ConflictReport
)
from modules.api_orchestration.domain.schemas import DataSource, ConflictResolution


@pytest.fixture
def conflict_resolver(db_session):
    """Create conflict resolver instance."""
    return ConflictResolver(db_session)


class TestConflictResolver:
    """Tests for ConflictResolver."""
    
    def test_no_conflict_identical_values(self, conflict_resolver):
        """Test when both sources have identical values."""
        inflow_data = {
            "username": "johndoe",
            "total_spent": 100.0,
            "is_subscriber": True
        }
        onlyfans_data = {
            "username": "johndoe",
            "total_spent": 100.0,
            "is_subscriber": True
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        assert result["username"] == "johndoe"
        assert result["total_spent"] == 100.0
        assert result["is_subscriber"] is True
        assert len(conflict_resolver.conflict_reports) == 0
        
    def test_financial_fields_sum(self, conflict_resolver):
        """Test that financial fields are summed."""
        inflow_data = {
            "total_spent": 100.0,
            "tip_count": 5,
            "message_count": 10
        }
        onlyfans_data = {
            "total_spent": 200.0,
            "tip_count": 3,
            "message_count": 15
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        assert result["total_spent"] == 300.0
        assert result["tip_count"] == 8
        assert result["message_count"] == 25
        
    def test_boolean_fields_any_true(self, conflict_resolver):
        """Test that boolean fields use any_true strategy."""
        inflow_data = {
            "is_subscriber": False,
            "is_paying": True,
            "is_verified": False
        }
        onlyfans_data = {
            "is_subscriber": True,
            "is_paying": False,
            "is_verified": False
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        assert result["is_subscriber"] is True
        assert result["is_paying"] is True
        assert result["is_verified"] is False
        
    def test_timestamp_fields_strategy(self, conflict_resolver):
        """Test timestamp field strategies."""
        now = datetime.utcnow()
        earlier = now - timedelta(days=30)
        later = now + timedelta(days=30)
        
        inflow_data = {
            "subscribed_at": now,
            "expires_at": earlier,
            "last_active_at": earlier,
            "created_at": now
        }
        onlyfans_data = {
            "subscribed_at": earlier,
            "expires_at": later,
            "last_active_at": now,
            "created_at": earlier
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        assert result["subscribed_at"] == earlier  # earliest
        assert result["expires_at"] == later  # latest
        assert result["last_active_at"] == now  # latest
        assert result["created_at"] == earlier  # earliest
        
    def test_string_merge_strategy(self, conflict_resolver):
        """Test string field merging."""
        inflow_data = {
            "username": "john",
            "display_name": "John Doe",
            "bio": "Short bio"
        }
        onlyfans_data = {
            "username": "johndoe",
            "display_name": "John",
            "bio": "This is a much longer bio with more information"
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        # Should prefer longer/more complete strings
        assert result["username"] == "johndoe"
        assert result["display_name"] == "John Doe"
        assert result["bio"] == "This is a much longer bio with more information"
        
    def test_prefer_onlyfans_strategy(self, conflict_resolver):
        """Test PREFER_ONLYFANS resolution strategy."""
        inflow_data = {"avatar_url": "https://inflow.com/avatar.jpg"}
        onlyfans_data = {"avatar_url": "https://onlyfans.com/avatar.jpg"}
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, 
            onlyfans_data,
            ConflictResolution.PREFER_ONLYFANS
        )
        
        assert result["avatar_url"] == "https://onlyfans.com/avatar.jpg"
        
    def test_conflict_report_generation(self, conflict_resolver):
        """Test that conflict reports are generated correctly."""
        inflow_data = {
            "username": "john",
            "total_spent": 100.0,
            "is_subscriber": True
        }
        onlyfans_data = {
            "username": "johndoe",
            "total_spent": 200.0,
            "is_subscriber": False
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        # Should have 3 conflicts
        assert len(conflict_resolver.conflict_reports) == 3
        
        # Check conflict summary
        summary = conflict_resolver.get_conflict_summary()
        assert summary["has_conflicts"] is True
        assert summary["conflict_count"] == 3
        assert len(summary["reports"]) == 3
        
        # Verify specific conflict
        username_conflict = next(
            r for r in summary["reports"] 
            if r["field"] == "username"
        )
        assert len(username_conflict["sources"]) == 2
        
    def test_null_value_handling(self, conflict_resolver):
        """Test handling of null/missing values."""
        inflow_data = {
            "username": "john",
            "email": None,
            "total_spent": 100.0
        }
        onlyfans_data = {
            "username": "john",
            "email": "john@example.com",
            "bio": "Some bio"
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        assert result["email"] == "john@example.com"
        assert result["total_spent"] == 100.0
        assert result["bio"] == "Some bio"
        
    def test_decimal_handling(self, conflict_resolver):
        """Test proper handling of Decimal values."""
        inflow_data = {"subscription_price": Decimal("9.99")}
        onlyfans_data = {"subscription_price": Decimal("14.99")}
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        # Should use max for subscription_price
        assert result["subscription_price"] == Decimal("14.99")
        assert isinstance(result["subscription_price"], Decimal)
        
    def test_list_merging(self, conflict_resolver):
        """Test merging of list values."""
        inflow_data = {
            "tags": ["vip", "active"],
            "interests": ["sports"]
        }
        onlyfans_data = {
            "tags": ["active", "whale"],
            "interests": ["sports", "music"]
        }
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, onlyfans_data
        )
        
        # Lists should be combined with unique values
        assert set(result["tags"]) == {"vip", "active", "whale"}
        assert set(result["interests"]) == {"sports", "music"}
        
    def test_empty_source_handling(self, conflict_resolver):
        """Test when one source has no data."""
        inflow_data = {"username": "john", "total_spent": 100.0}
        
        result = conflict_resolver.resolve_fan_data(
            inflow_data, None
        )
        
        assert result == inflow_data
        assert len(conflict_resolver.conflict_reports) == 0