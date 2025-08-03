from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Numeric, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from core.database import Base
from models.base import BaseModel


class TransactionType(str, enum.Enum):
    """Transaction type enumeration."""
    TIP = "tip"
    PPV = "ppv"  # Pay-per-view
    SUBSCRIPTION = "subscription"
    MESSAGE = "message"
    REFERRAL = "referral"
    ADJUSTMENT = "adjustment"
    CHARGEBACK = "chargeback"
    REFUND = "refund"


class TransactionStatus(str, enum.Enum):
    """Transaction status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class PayoutStatus(str, enum.Enum):
    """Payout status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Payment method enumeration."""
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    CRYPTO = "crypto"
    CHECK = "check"
    WIRE = "wire"


class Transaction(BaseModel):
    """Financial transaction record."""
    __tablename__ = "transactions"
    
    # Relationships
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    
    # Transaction details
    type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    
    # External references
    platform_transaction_id = Column(String(255), unique=True, nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    
    # Financial amounts
    gross_amount = Column(Numeric(12, 2), nullable=False)
    platform_fee = Column(Numeric(12, 2), default=0.00, nullable=False)
    agency_commission = Column(Numeric(12, 2), default=0.00, nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)  # Model's earning
    currency = Column(String(3), default="USD", nullable=False)
    
    # Fan information
    fan_id = Column(String(255), nullable=False, index=True)
    fan_username = Column(String(255), nullable=False)
    
    # Timing
    transaction_date = Column(String(30), nullable=False)  # When transaction occurred
    processed_at = Column(String(30), nullable=True)  # When we processed it
    
    # Additional data
    description = Column(String(500), nullable=True)
    transaction_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="transactions")
    model = relationship("Model", back_populates="transactions")
    earning = relationship("Earning", back_populates="transaction", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_transactions_date', 'transaction_date'),
        Index('idx_transactions_model_date', 'model_id', 'transaction_date'),
    )
    
    def __repr__(self):
        return f"<Transaction {self.type} - ${self.gross_amount} - {self.status}>"


class Earning(BaseModel):
    """Model earnings tracking."""
    __tablename__ = "earnings"
    
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Period tracking
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    period_week = Column(Integer, nullable=False)
    
    # Amounts
    gross_amount = Column(Numeric(12, 2), nullable=False)
    commission_amount = Column(Numeric(12, 2), nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)
    
    # Status
    is_paid = Column(Boolean, default=False, nullable=False)
    payout_id = Column(Integer, ForeignKey("payouts.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    model = relationship("Model", back_populates="earnings")
    transaction = relationship("Transaction", back_populates="earning")
    payout = relationship("Payout", back_populates="earnings")
    
    # Indexes
    __table_args__ = (
        Index('idx_earnings_period', 'model_id', 'period_year', 'period_month'),
        Index('idx_earnings_unpaid', 'model_id', 'is_paid'),
    )
    
    def __repr__(self):
        return f"<Earning Model:{self.model_id} - ${self.net_amount} - {'Paid' if self.is_paid else 'Unpaid'}>"


class Payout(BaseModel):
    """Payout to models."""
    __tablename__ = "payouts"
    
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    
    # Payout details
    payout_number = Column(String(50), unique=True, nullable=False)
    status = Column(SQLEnum(PayoutStatus), default=PayoutStatus.PENDING, nullable=False)
    
    # Period
    period_start = Column(String(30), nullable=False)
    period_end = Column(String(30), nullable=False)
    
    # Amounts
    gross_earnings = Column(Numeric(12, 2), nullable=False)
    commission_amount = Column(Numeric(12, 2), nullable=False)
    adjustments = Column(Numeric(12, 2), default=0.00, nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Payment method
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    payment_details = Column(JSON, default=dict, nullable=False)  # Encrypted in production
    
    # Processing
    scheduled_date = Column(String(30), nullable=False)
    processed_date = Column(String(30), nullable=True)
    completed_date = Column(String(30), nullable=True)
    
    # References
    transaction_reference = Column(String(255), nullable=True)  # Bank/payment processor reference
    notes = Column(String(1000), nullable=True)
    
    # Relationships
    agency = relationship("Agency", back_populates="payouts")
    model = relationship("Model", back_populates="payouts")
    earnings = relationship("Earning", back_populates="payout")
    
    def __repr__(self):
        return f"<Payout {self.payout_number} - ${self.net_amount} - {self.status}>"
    
    @property
    def earnings_count(self):
        """Get count of earnings in this payout."""
        return len(self.earnings)


class Invoice(BaseModel):
    """Invoice for agency billing."""
    __tablename__ = "invoices"
    
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Invoice details
    invoice_number = Column(String(50), unique=True, nullable=False)
    invoice_date = Column(String(30), nullable=False)
    due_date = Column(String(30), nullable=False)
    
    # Billing period
    period_start = Column(String(30), nullable=False)
    period_end = Column(String(30), nullable=False)
    
    # Amounts
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    
    # Status
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_date = Column(String(30), nullable=True)
    payment_method = Column(String(50), nullable=True)
    
    # Line items
    line_items = Column(JSON, default=list, nullable=False)
    
    # Stripe
    stripe_invoice_id = Column(String(255), nullable=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    
    # Relationships
    agency = relationship("Agency", back_populates="invoices")
    
    def __repr__(self):
        return f"<Invoice {self.invoice_number} - ${self.total_amount}>"