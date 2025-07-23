"""
Financial domain models for commission, payments, and invoicing.
"""
from sqlalchemy import Column, String, DateTime, Numeric, Integer, ForeignKey, Index, JSON, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from backend.core.database import Base


class CommissionTier(str, enum.Enum):
    """Commission tier levels."""
    TIER_1 = "tier_1"  # 70%
    TIER_2 = "tier_2"  # 65%
    TIER_3 = "tier_3"  # 60%
    CUSTOM = "custom"  # Custom rate


class PayoutStatus(str, enum.Enum):
    """Payout status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransactionType(str, enum.Enum):
    """Financial transaction types."""
    REVENUE = "revenue"
    COMMISSION = "commission"
    PAYOUT = "payout"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class CryptoNetwork(str, enum.Enum):
    """Supported cryptocurrency networks."""
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    BINANCE_SMART_CHAIN = "bsc"
    POLYGON = "polygon"
    TRON = "tron"
    USDT_TRC20 = "usdt_trc20"
    USDT_ERC20 = "usdt_erc20"
    USDC = "usdc"


class InvoiceStatus(str, enum.Enum):
    """Invoice status."""
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class CommissionRule(Base):
    """Commission rules for agencies and models."""
    __tablename__ = "commission_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"), nullable=True)
    
    # Commission settings
    tier = Column(Enum(CommissionTier), default=CommissionTier.TIER_1, nullable=False)
    rate = Column(Numeric(5, 2), nullable=False)  # Percentage (0-100)
    
    # Override settings (for super_admin)
    is_override = Column(Boolean, default=False)
    override_reason = Column(String(500))
    override_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    override_at = Column(DateTime(timezone=True))
    
    # Validity period
    effective_from = Column(DateTime(timezone=True), default=func.now())
    effective_until = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_commission_rule_agency', 'agency_id'),
        Index('idx_commission_rule_model', 'model_id'),
        Index('idx_commission_rule_effective', 'effective_from', 'effective_until'),
    )


class BillingCycle(Base):
    """Billing cycles for commission calculation."""
    __tablename__ = "billing_cycles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    
    # Cycle period
    cycle_start = Column(DateTime(timezone=True), nullable=False)
    cycle_end = Column(DateTime(timezone=True), nullable=False)
    
    # Revenue summary
    gross_revenue = Column(Numeric(12, 2), default=0)
    total_commission = Column(Numeric(12, 2), default=0)
    net_revenue = Column(Numeric(12, 2), default=0)
    
    # Status
    is_closed = Column(Boolean, default=False)
    closed_at = Column(DateTime(timezone=True))
    closed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_billing_cycle_agency', 'agency_id'),
        Index('idx_billing_cycle_period', 'cycle_start', 'cycle_end'),
    )


class Payout(Base):
    """Payout records for models and agencies."""
    __tablename__ = "payouts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    billing_cycle_id = Column(UUID(as_uuid=True), ForeignKey("billing_cycles.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipient_type = Column(String(20), nullable=False)  # 'model', 'agency'
    
    # Payout details
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default='USD')
    status = Column(Enum(PayoutStatus), default=PayoutStatus.PENDING)
    
    # Payment method
    payment_method = Column(String(50), nullable=False)  # 'crypto', 'bank_transfer'
    payment_details = Column(JSON)  # Encrypted payment details
    
    # Transaction info
    transaction_id = Column(String(255))
    transaction_hash = Column(String(255))  # For crypto payments
    
    # Processing dates
    scheduled_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Error handling
    failure_reason = Column(String(500))
    retry_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_payout_cycle', 'billing_cycle_id'),
        Index('idx_payout_recipient', 'recipient_id'),
        Index('idx_payout_status', 'status'),
    )


class CryptoWallet(Base):
    """Cryptocurrency wallet addresses for payouts."""
    __tablename__ = "crypto_wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Wallet details
    network = Column(Enum(CryptoNetwork), nullable=False)
    address = Column(String(255), nullable=False)
    label = Column(String(100))
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True))
    verification_signature = Column(String(500))
    
    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_crypto_wallet_user', 'user_id'),
        Index('idx_crypto_wallet_network', 'network'),
        # Unique constraint: one default wallet per network per user
        Index('idx_crypto_wallet_default', 'user_id', 'network', 'is_default', unique=True,
              postgresql_where='is_default = true'),
    )


class FinancialTransaction(Base):
    """Detailed financial transaction records."""
    __tablename__ = "financial_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Related entities
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"))
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Transaction details
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default='USD')
    
    # Related records
    billing_cycle_id = Column(UUID(as_uuid=True), ForeignKey("billing_cycles.id"))
    payout_id = Column(UUID(as_uuid=True), ForeignKey("payouts.id"))
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    
    # External references
    external_reference = Column(String(255))  # OnlyFans/Inflow transaction ID
    description = Column(String(500))
    
    # Balance tracking
    balance_before = Column(Numeric(12, 2))
    balance_after = Column(Numeric(12, 2))
    
    # Timestamps
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_financial_transaction_agency', 'agency_id'),
        Index('idx_financial_transaction_model', 'model_id'),
        Index('idx_financial_transaction_user', 'user_id'),
        Index('idx_financial_transaction_date', 'transaction_date'),
        Index('idx_financial_transaction_type', 'type'),
    )


class Invoice(Base):
    """Invoice records for billing."""
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False)
    
    # Billing parties
    billing_cycle_id = Column(UUID(as_uuid=True), ForeignKey("billing_cycles.id"))
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model_profiles.id"))
    
    # Invoice details
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    issue_date = Column(DateTime(timezone=True), default=func.now())
    due_date = Column(DateTime(timezone=True))
    paid_date = Column(DateTime(timezone=True))
    
    # Amounts
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=0)
    tax_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0)
    
    # Line items (JSON array)
    line_items = Column(JSON, default=list)
    
    # Payment info
    payment_method = Column(String(50))
    payment_reference = Column(String(255))
    
    # Notes
    notes = Column(String(1000))
    terms_conditions = Column(String(2000))
    
    # PDF storage
    pdf_url = Column(String(500))
    pdf_generated_at = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_invoice_agency', 'agency_id'),
        Index('idx_invoice_model', 'model_id'),
        Index('idx_invoice_status', 'status'),
        Index('idx_invoice_due_date', 'due_date'),
    )


class PaymentGatewayConfig(Base):
    """Configuration for payment gateways (crypto providers)."""
    __tablename__ = "payment_gateway_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True)
    
    # Gateway details
    provider = Column(String(50), nullable=False)  # 'coinbase_commerce', 'bitpay', etc.
    is_active = Column(Boolean, default=True)
    is_test_mode = Column(Boolean, default=False)
    
    # API credentials (encrypted)
    api_key = Column(String(500))
    api_secret = Column(String(500))
    webhook_secret = Column(String(500))
    merchant_id = Column(String(255))
    
    # Supported currencies
    supported_currencies = Column(JSON, default=list)
    
    # Configuration
    config = Column(JSON, default=dict)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_payment_gateway_config_agency', 'agency_id'),
        Index('idx_payment_gateway_config_provider', 'provider'),
    )