"""Tests for commission calculation service."""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from services.commission_service import CommissionService


class TestCommissionService:
    """Test commission calculation service."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=AsyncSession)
    
    @pytest.fixture
    def commission_service(self, mock_db):
        """Create commission service instance."""
        return CommissionService(mock_db)
    
    def test_calculate_agency_commission_rate(self, commission_service):
        """Test commission rate calculation for different revenue tiers."""
        # Test tier 1: 0-$10k = 20%
        assert commission_service.calculate_agency_commission_rate(Decimal("0")) == Decimal("0.20")
        assert commission_service.calculate_agency_commission_rate(Decimal("5000")) == Decimal("0.20")
        assert commission_service.calculate_agency_commission_rate(Decimal("9999")) == Decimal("0.20")
        
        # Test tier 2: $10k-$25k = 25%
        assert commission_service.calculate_agency_commission_rate(Decimal("10000")) == Decimal("0.25")
        assert commission_service.calculate_agency_commission_rate(Decimal("15000")) == Decimal("0.25")
        assert commission_service.calculate_agency_commission_rate(Decimal("24999")) == Decimal("0.25")
        
        # Test tier 3: $25k-$50k = 30%
        assert commission_service.calculate_agency_commission_rate(Decimal("25000")) == Decimal("0.30")
        assert commission_service.calculate_agency_commission_rate(Decimal("35000")) == Decimal("0.30")
        assert commission_service.calculate_agency_commission_rate(Decimal("49999")) == Decimal("0.30")
        
        # Test tier 4: $50k+ = 35%
        assert commission_service.calculate_agency_commission_rate(Decimal("50000")) == Decimal("0.35")
        assert commission_service.calculate_agency_commission_rate(Decimal("100000")) == Decimal("0.35")
        assert commission_service.calculate_agency_commission_rate(Decimal("1000000")) == Decimal("0.35")
    
    def test_calculate_tiered_commission_single_tier(self, commission_service):
        """Test commission calculation within a single tier."""
        # Transaction fully within tier 1 (20%)
        result = commission_service.calculate_tiered_commission(
            gross_amount=Decimal("100"),
            monthly_revenue_before=Decimal("5000")
        )
        
        # Platform fee: 100 * 0.20 = 20
        assert result["platform_fee"] == Decimal("20")
        
        # After platform: 100 - 20 = 80
        # Agency fee: 80 * 0.20 = 16
        assert result["agency_fee"] == Decimal("16")
        
        # Model earnings: 80 - 16 = 64
        assert result["model_earnings"] == Decimal("64")
    
    def test_calculate_tiered_commission_cross_tier(self, commission_service):
        """Test commission calculation crossing tier boundaries."""
        # Transaction crossing from tier 1 (20%) to tier 2 (25%)
        # Monthly revenue: $9,500, transaction: $1,000
        result = commission_service.calculate_tiered_commission(
            gross_amount=Decimal("1000"),
            monthly_revenue_before=Decimal("9500")
        )
        
        # Platform fee: 1000 * 0.20 = 200
        assert result["platform_fee"] == Decimal("200")
        
        # After platform: 1000 - 200 = 800
        # First $500 in tier 1 (20%): 500 * 0.20 = 100
        # Next $300 in tier 2 (25%): 300 * 0.25 = 75
        # Total agency fee: 100 + 75 = 175
        assert result["agency_fee"] == Decimal("175")
        
        # Model earnings: 800 - 175 = 625
        assert result["model_earnings"] == Decimal("625")
    
    def test_calculate_tiered_commission_multiple_tiers(self, commission_service):
        """Test commission calculation crossing multiple tiers."""
        # Transaction crossing multiple tiers
        # Monthly revenue: $24,000, transaction: $30,000
        result = commission_service.calculate_tiered_commission(
            gross_amount=Decimal("30000"),
            monthly_revenue_before=Decimal("24000")
        )
        
        # Platform fee: 30000 * 0.20 = 6000
        assert result["platform_fee"] == Decimal("6000")
        
        # After platform: 30000 - 6000 = 24000
        # First $1,000 in tier 2 (25%): 1000 * 0.25 = 250
        # Next $23,000 in tier 3 (30%): 23000 * 0.30 = 6900
        # Total agency fee: 250 + 6900 = 7150
        assert result["agency_fee"] == Decimal("7150")
        
        # Model earnings: 24000 - 7150 = 16850
        assert result["model_earnings"] == Decimal("16850")
    
    def test_calculate_tiered_commission_highest_tier(self, commission_service):
        """Test commission calculation in highest tier."""
        # Transaction fully in highest tier (35%)
        result = commission_service.calculate_tiered_commission(
            gross_amount=Decimal("10000"),
            monthly_revenue_before=Decimal("100000")
        )
        
        # Platform fee: 10000 * 0.20 = 2000
        assert result["platform_fee"] == Decimal("2000")
        
        # After platform: 10000 - 2000 = 8000
        # Agency fee: 8000 * 0.35 = 2800
        assert result["agency_fee"] == Decimal("2800")
        
        # Model earnings: 8000 - 2800 = 5200
        assert result["model_earnings"] == Decimal("5200")
    
    def test_get_tier_info(self, commission_service):
        """Test tier information retrieval."""
        # Test tier 1
        info = commission_service.get_tier_info(Decimal("5000"))
        assert info["current_tier"] == 0
        assert info["current_rate"] == 0.20
        assert info["next_tier"] == 10000
        assert info["progress_to_next"] == 0.5  # 5000/10000
        
        # Test tier 2
        info = commission_service.get_tier_info(Decimal("15000"))
        assert info["current_tier"] == 10000
        assert info["current_rate"] == 0.25
        assert info["next_tier"] == 25000
        assert info["progress_to_next"] == pytest.approx(0.333, rel=0.01)  # 5000/15000
        
        # Test highest tier
        info = commission_service.get_tier_info(Decimal("75000"))
        assert info["current_tier"] == 50000
        assert info["current_rate"] == 0.35
        assert info["next_tier"] is None
        assert info["progress_to_next"] is None
    
    @pytest.mark.asyncio
    async def test_get_model_monthly_revenue(self, commission_service, mock_db):
        """Test monthly revenue calculation."""
        # Mock the database response
        mock_db.scalar = AsyncMock(return_value=Decimal("12500"))
        
        # Test with current month
        revenue = await commission_service.get_model_monthly_revenue(1)
        assert revenue == Decimal("12500")
        
        # Verify query was called
        mock_db.scalar.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_calculate_transaction_fees(self, commission_service, mock_db):
        """Test full transaction fee calculation."""
        # Mock monthly revenue
        mock_db.scalar = AsyncMock(return_value=Decimal("8000"))
        
        # Calculate fees
        fees = await commission_service.calculate_transaction_fees(
            model_id=1,
            gross_amount=Decimal("500")
        )
        
        # Platform fee: 500 * 0.20 = 100
        assert fees["platform_fee"] == Decimal("100")
        
        # After platform: 500 - 100 = 400
        # Agency fee (tier 1, 20%): 400 * 0.20 = 80
        assert fees["agency_fee"] == Decimal("80")
        
        # Model earnings: 400 - 80 = 320
        assert fees["model_earnings"] == Decimal("320")
        
        # Verify total adds up
        assert (fees["platform_fee"] + fees["agency_fee"] + fees["model_earnings"]) == Decimal("500")