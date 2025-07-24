"""
Financial domain schemas for API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from .models import (
    CommissionTier,
    PayoutStatus,
    TransactionType,
    CryptoNetwork,
    InvoiceStatus
)


# Commission schemas
class CommissionRuleBase(BaseModel):
    """Base schema for commission rules."""
    tier: CommissionTier = CommissionTier.TIER_1
    rate: Decimal = Field(..., ge=0, le=100, description="Commission rate percentage")
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class CommissionRuleCreate(CommissionRuleBase):
    """Schema for creating commission rule."""
    agency_id: str
    model_id: Optional[str] = None


class CommissionRuleUpdate(BaseModel):
    """Schema for updating commission rule."""
    tier: Optional[CommissionTier] = None
    rate: Optional[Decimal] = Field(None, ge=0, le=100)
    effective_until: Optional[datetime] = None


class CommissionRuleResponse(CommissionRuleBase):
    """Response schema for commission rule."""
    id: str
    agency_id: str
    model_id: Optional[str]
    is_override: bool
    override_reason: Optional[str]
    override_by: Optional[str]
    override_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CommissionOverrideRequest(BaseModel):
    """Request to override commission for super_admin."""
    rate: Decimal = Field(..., ge=0, le=100, description="Override commission rate")
    reason: str = Field(..., min_length=10, max_length=500)
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


# Billing cycle schemas
class BillingCycleSummary(BaseModel):
    """Summary of a billing cycle."""
    id: str
    agency_id: str
    cycle_start: datetime
    cycle_end: datetime
    gross_revenue: Decimal
    total_commission: Decimal
    net_revenue: Decimal
    is_closed: bool
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class BillingCycleDetails(BillingCycleSummary):
    """Detailed billing cycle information."""
    model_revenues: List[Dict[str, Any]]  # Revenue breakdown by model
    pending_payouts: int
    completed_payouts: int
    total_payout_amount: Decimal


# Payout schemas
class PayoutRequest(BaseModel):
    """Request to create a payout."""
    billing_cycle_id: str
    recipient_id: str
    recipient_type: str = Field(..., pattern="^(model|agency)$")
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., pattern="^(crypto|bank_transfer)$")
    payment_details: Dict[str, Any]
    scheduled_at: Optional[datetime] = None


class PayoutResponse(BaseModel):
    """Response for payout information."""
    id: str
    billing_cycle_id: str
    recipient_id: str
    recipient_type: str
    amount: Decimal
    currency: str
    status: PayoutStatus
    payment_method: str
    transaction_id: Optional[str]
    transaction_hash: Optional[str]
    scheduled_at: Optional[datetime]
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PayoutStatusUpdate(BaseModel):
    """Update payout status."""
    status: PayoutStatus
    transaction_id: Optional[str]
    transaction_hash: Optional[str]
    failure_reason: Optional[str]


# Crypto wallet schemas
class CryptoWalletCreate(BaseModel):
    """Create a new crypto wallet."""
    network: CryptoNetwork
    address: str
    label: Optional[str] = None
    is_default: bool = False

    @validator('address')
    def validate_address(cls, v, values):
        """Basic validation for crypto addresses."""
        if not v:
            raise ValueError("Address cannot be empty")
        
        # Basic length checks
        network = values.get('network')
        if network in [CryptoNetwork.BITCOIN]:
            if len(v) < 26 or len(v) > 35:
                raise ValueError("Invalid Bitcoin address length")
        elif network in [CryptoNetwork.ETHEREUM, CryptoNetwork.BINANCE_SMART_CHAIN, 
                         CryptoNetwork.POLYGON, CryptoNetwork.USDT_ERC20, CryptoNetwork.USDC]:
            if not v.startswith('0x') or len(v) != 42:
                raise ValueError("Invalid Ethereum-based address format")
        elif network == CryptoNetwork.TRON:
            if not v.startswith('T') or len(v) != 34:
                raise ValueError("Invalid TRON address format")
        
        return v


class CryptoWalletResponse(BaseModel):
    """Response for crypto wallet."""
    id: str
    user_id: str
    network: CryptoNetwork
    address: str
    label: Optional[str]
    is_verified: bool
    verified_at: Optional[datetime]
    is_active: bool
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CryptoWalletVerification(BaseModel):
    """Verify ownership of crypto wallet."""
    signature: str = Field(..., description="Signed message proving ownership")


# Transaction schemas
class TransactionFilter(BaseModel):
    """Filter criteria for transactions."""
    type: Optional[TransactionType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    agency_id: Optional[str] = None
    model_id: Optional[str] = None
    user_id: Optional[str] = None


class TransactionResponse(BaseModel):
    """Response for financial transaction."""
    id: str
    type: TransactionType
    amount: Decimal
    currency: str
    description: Optional[str]
    balance_before: Optional[Decimal]
    balance_after: Optional[Decimal]
    transaction_date: datetime
    related_entity: Optional[Dict[str, Any]]  # Agency/Model/User info

    class Config:
        from_attributes = True


# Invoice schemas
class InvoiceLineItem(BaseModel):
    """Line item for invoice."""
    description: str
    quantity: int = 1
    unit_price: Decimal
    total: Decimal


class InvoiceCreate(BaseModel):
    """Create a new invoice."""
    agency_id: str
    model_id: Optional[str] = None
    billing_cycle_id: Optional[str] = None
    due_date: Optional[datetime] = None
    line_items: List[InvoiceLineItem]
    tax_rate: Decimal = Field(0, ge=0, le=100)
    notes: Optional[str] = None
    terms_conditions: Optional[str] = None


class InvoiceUpdate(BaseModel):
    """Update invoice details."""
    status: Optional[InvoiceStatus] = None
    due_date: Optional[datetime] = None
    line_items: Optional[List[InvoiceLineItem]] = None
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    notes: Optional[str] = None
    paid_amount: Optional[Decimal] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Response for invoice."""
    id: str
    invoice_number: str
    agency_id: str
    model_id: Optional[str]
    status: InvoiceStatus
    issue_date: datetime
    due_date: Optional[datetime]
    paid_date: Optional[datetime]
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    line_items: List[InvoiceLineItem]
    notes: Optional[str]
    pdf_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Payment gateway schemas
class PaymentGatewayConfigCreate(BaseModel):
    """Create payment gateway configuration."""
    provider: str
    api_key: str
    api_secret: Optional[str] = None
    webhook_secret: Optional[str] = None
    merchant_id: Optional[str] = None
    is_test_mode: bool = True
    supported_currencies: List[str] = ["USD", "BTC", "ETH", "USDT", "USDC"]
    config: Dict[str, Any] = Field(default_factory=dict)


class PaymentGatewayConfigResponse(BaseModel):
    """Response for payment gateway config."""
    id: str
    agency_id: Optional[str]
    provider: str
    is_active: bool
    is_test_mode: bool
    supported_currencies: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Crypto payment schemas
class CryptoPaymentRequest(BaseModel):
    """Request for crypto payment."""
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., description="USD, BTC, ETH, etc.")
    description: str
    recipient_wallet_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CryptoPaymentResponse(BaseModel):
    """Response for crypto payment creation."""
    payment_id: str
    amount: Decimal
    currency: str
    network: CryptoNetwork
    recipient_address: str
    status: str
    transaction_hash: Optional[str]
    expires_at: Optional[datetime]
    payment_url: Optional[str]  # For payment gateways like Coinbase Commerce


# Financial summary schemas
class FinancialSummary(BaseModel):
    """Financial summary for dashboard."""
    period: str  # today, week, month, year
    gross_revenue: Decimal
    total_commission: Decimal
    net_revenue: Decimal
    pending_payouts: Decimal
    completed_payouts: Decimal
    active_models: int
    top_earning_models: List[Dict[str, Any]]
    revenue_by_source: Dict[str, Decimal]  # OnlyFans, Inflow, etc.


class CommissionCalculation(BaseModel):
    """Commission calculation details."""
    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    net_amount: Decimal
    tier: CommissionTier
    is_override: bool = False
    calculation_date: datetime