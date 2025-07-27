"""
Tests for database optimization features.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.query_analyzer import QueryAnalyzer, QueryOptimizer
from core.database.query_builders import OptimizedQueries, BatchOperations
from core.domain.models import ModelProfile, Agency, Fan
from modules.financial.domain.models import FinancialTransaction, TransactionType


class TestQueryAnalyzer:
    
    @pytest.mark.asyncio
    async def test_analyze_slow_queries(self, db_session: AsyncSession):
        """Test slow query analysis."""
        # Note: This requires pg_stat_statements extension
        slow_queries = await QueryAnalyzer.analyze_slow_queries(
            db_session,
            min_duration_ms=0  # Get all queries for testing
        )
        
        # Should return a list (might be empty if no queries)
        assert isinstance(slow_queries, list)
        
        if slow_queries:
            # Check structure
            query = slow_queries[0]
            assert "query" in query
            assert "mean_time_ms" in query
            assert "calls" in query
    
    @pytest.mark.asyncio
    async def test_analyze_missing_indexes(self, db_session: AsyncSession):
        """Test missing index analysis."""
        suggestions = await QueryAnalyzer.analyze_missing_indexes(
            db_session,
            min_scans=0  # Get all tables for testing
        )
        
        assert isinstance(suggestions, list)
        
        if suggestions:
            suggestion = suggestions[0]
            assert "table" in suggestion
            assert "seq_scan_ratio" in suggestion
            assert "suggestion" in suggestion
    
    @pytest.mark.asyncio
    async def test_analyze_table_bloat(self, db_session: AsyncSession):
        """Test table bloat analysis."""
        bloated_tables = await QueryAnalyzer.analyze_table_bloat(
            db_session,
            min_bloat_ratio=0  # Get all tables for testing
        )
        
        assert isinstance(bloated_tables, list)
        
        if bloated_tables:
            table = bloated_tables[0]
            assert "table" in table
            assert "bloat_ratio" in table
            assert "action" in table
    
    @pytest.mark.asyncio
    async def test_analyze_connection_stats(self, db_session: AsyncSession):
        """Test connection statistics analysis."""
        stats = await QueryAnalyzer.analyze_connection_stats(db_session)
        
        assert isinstance(stats, dict)
        assert "total_connections" in stats
        assert "active_connections" in stats
        assert "idle_connections" in stats
        assert stats["total_connections"] >= 1  # At least our test connection
    
    def test_optimize_query_suggestions(self):
        """Test query optimization suggestions."""
        # Test SELECT * detection
        suggestions = QueryOptimizer.optimize_query("SELECT * FROM users")
        assert suggestions["has_issues"] is True
        assert any("SELECT *" in s["issue"] for s in suggestions["suggestions"])
        
        # Test missing WHERE clause
        suggestions = QueryOptimizer.optimize_query("DELETE FROM users")
        assert suggestions["has_issues"] is True
        assert any("WHERE clause" in s["issue"] for s in suggestions["suggestions"])
        
        # Test leading wildcard
        suggestions = QueryOptimizer.optimize_query("SELECT * FROM users WHERE name LIKE '%john'")
        assert suggestions["has_issues"] is True
        assert any("wildcard" in s["issue"] for s in suggestions["suggestions"])
    
    def test_suggest_indexes(self):
        """Test index suggestion generation."""
        suggestions = QueryOptimizer.suggest_indexes(
            table="users",
            frequent_filters=["agency_id", "is_active"],
            frequent_joins=["id"]
        )
        
        assert len(suggestions) >= 3
        assert any("idx_users_agency_id" in s for s in suggestions)
        assert any("idx_users_composite" in s for s in suggestions)


class TestOptimizedQueries:
    
    @pytest.mark.asyncio
    async def test_get_model_with_relations(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test optimized model query with relations."""
        query = OptimizedQueries.get_model_with_relations()
        query = query.where(ModelProfile.id == test_model_profile.id)
        
        result = await db_session.execute(query)
        model = result.scalar_one()
        
        assert model.id == test_model_profile.id
        # Relations should be loaded
        assert model.agency is not None
    
    @pytest.mark.asyncio
    async def test_get_model_financial_summary(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test financial summary aggregation."""
        # Create test transactions
        transactions = [
            FinancialTransaction(
                agency_id=test_model_profile.agency_id,
                model_id=test_model_profile.id,
                type=TransactionType.REVENUE,
                amount=Decimal("100.00"),
                transaction_date=datetime.utcnow()
            ),
            FinancialTransaction(
                agency_id=test_model_profile.agency_id,
                model_id=test_model_profile.id,
                type=TransactionType.COMMISSION,
                amount=Decimal("20.00"),
                transaction_date=datetime.utcnow()
            )
        ]
        
        for txn in transactions:
            db_session.add(txn)
        await db_session.commit()
        
        # Test summary query
        query = OptimizedQueries.get_model_financial_summary(
            model_id=str(test_model_profile.id),
            start_date=datetime.utcnow() - timedelta(days=1),
            end_date=datetime.utcnow() + timedelta(days=1)
        )
        
        result = await db_session.execute(query)
        summary = result.fetchone()
        
        assert float(summary.total_revenue) == 100.00
        assert float(summary.total_commission) == 20.00
        assert summary.revenue_count == 1
    
    @pytest.mark.asyncio
    async def test_top_performing_models_query(
        self,
        db_session: AsyncSession,
        test_agency: Agency
    ):
        """Test top performing models query."""
        query = OptimizedQueries.get_top_performing_models(
            agency_id=str(test_agency.id),
            limit=5,
            period_days=30
        )
        
        result = await db_session.execute(
            query,
            {
                "agency_id": str(test_agency.id),
                "cutoff_date": datetime.utcnow() - timedelta(days=30),
                "limit": 5
            }
        )
        
        models = result.fetchall()
        assert isinstance(models, list)


class TestBatchOperations:
    
    @pytest.mark.asyncio
    async def test_batch_update_model_stats(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test batch model stats update."""
        stats = [{
            "model_id": str(test_model_profile.id),
            "subscriber_count": 150,
            "paying_subscriber_count": 75,
            "total_earnings": 5000.00
        }]
        
        await BatchOperations.batch_update_model_stats(db_session, stats)
        await db_session.commit()
        
        # Verify update
        await db_session.refresh(test_model_profile)
        assert test_model_profile.subscriber_count == 150
        assert test_model_profile.paying_subscriber_count == 75
        assert float(test_model_profile.total_earnings) == 5000.00
    
    @pytest.mark.asyncio
    async def test_batch_create_transactions(
        self,
        db_session: AsyncSession,
        test_model_profile: ModelProfile
    ):
        """Test batch transaction creation."""
        transactions = [
            {
                "agency_id": str(test_model_profile.agency_id),
                "model_id": str(test_model_profile.id),
                "type": TransactionType.REVENUE.value,
                "amount": 50.00,
                "transaction_date": datetime.utcnow(),
                "external_reference": f"test_ref_{i}"
            }
            for i in range(5)
        ]
        
        await BatchOperations.batch_create_transactions(db_session, transactions)
        await db_session.commit()
        
        # Verify creation
        result = await db_session.execute(
            text("""
                SELECT COUNT(*) FROM financial_transactions 
                WHERE model_id = :model_id 
                AND external_reference LIKE 'test_ref_%'
            """),
            {"model_id": test_model_profile.id}
        )
        count = result.scalar()
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_vacuum_old_data(self, db_session: AsyncSession):
        """Test old data cleanup."""
        # This should not fail
        await BatchOperations.vacuum_old_data(db_session, days_to_keep=90)
        # If no exception, test passes


class TestMaterializedViews:
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires materialized views to be created")
    async def test_refresh_materialized_views(self, db_session: AsyncSession):
        """Test materialized view refresh."""
        # This test requires the views to exist
        await db_session.execute(text("CALL refresh_analytics_views()"))
        await db_session.commit()
        
        # Query the view
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM model_revenue_summary")
        )
        count = result.scalar()
        assert count >= 0