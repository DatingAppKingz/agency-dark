"""Payment method models for storing model/agency payment details."""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from core.database import Base
from models.base import BaseModel
from models.financial import PaymentMethod as PaymentMethodType


class PaymentMethodModel(BaseModel):
    """Payment method details for models and agencies."""
    __tablename__ = "payment_methods"
    
    # Owner
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=True)
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=True)
    
    # Payment method details
    method_type = Column(SQLEnum(PaymentMethodType), nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    nickname = Column(String(100), nullable=True)  # User-friendly name
    
    # Bank transfer details
    bank_name = Column(String(255), nullable=True)
    account_holder_name = Column(String(255), nullable=True)
    account_number = Column(String(255), nullable=True)  # Encrypted
    routing_number = Column(String(255), nullable=True)  # Encrypted
    swift_code = Column(String(50), nullable=True)
    iban = Column(String(50), nullable=True)  # Encrypted
    
    # PayPal details
    paypal_email = Column(String(255), nullable=True)
    
    # Crypto details
    crypto_currency = Column(String(10), nullable=True)  # BTC, ETH, USDT, etc.
    crypto_address = Column(String(500), nullable=True)  # Encrypted
    crypto_network = Column(String(50), nullable=True)  # ERC20, TRC20, etc.
    
    # Wire transfer details
    wire_instructions = Column(JSON, nullable=True)  # Encrypted JSON with detailed instructions
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(String(30), nullable=True)
    verification_notes = Column(String(500), nullable=True)
    
    # Additional settings
    minimum_payout = Column(Integer, default=100, nullable=False)  # Minimum amount for this method
    processing_days = Column(Integer, default=3, nullable=False)  # Expected processing time
    
    # Metadata
    last_used_at = Column(String(30), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    model = relationship("Model", backref="payment_methods")
    agency = relationship("Agency", backref="payment_methods")
    
    def __repr__(self):
        owner = f"Model:{self.model_id}" if self.model_id else f"Agency:{self.agency_id}"
        return f"<PaymentMethod {self.method_type} - {owner} - {'Primary' if self.is_primary else 'Secondary'}>"
    
    @property
    def display_name(self):
        """Get a display-friendly name for the payment method."""
        if self.nickname:
            return self.nickname
        
        if self.method_type == PaymentMethodType.BANK_TRANSFER:
            return f"{self.bank_name} - ****{self.account_number[-4:] if self.account_number else ''}"
        elif self.method_type == PaymentMethodType.PAYPAL:
            return f"PayPal - {self.paypal_email}"
        elif self.method_type == PaymentMethodType.CRYPTO:
            return f"{self.crypto_currency} - {self.crypto_address[:6]}...{self.crypto_address[-4:]}"
        else:
            return str(self.method_type.value).replace('_', ' ').title()
    
    def mask_sensitive_data(self):
        """Return a version with masked sensitive information."""
        data = {
            'id': self.id,
            'method_type': self.method_type.value,
            'is_primary': self.is_primary,
            'is_active': self.is_active,
            'nickname': self.nickname,
            'is_verified': self.is_verified,
        }
        
        if self.method_type == PaymentMethodType.BANK_TRANSFER:
            data.update({
                'bank_name': self.bank_name,
                'account_holder_name': self.account_holder_name,
                'account_number': f"****{self.account_number[-4:]}" if self.account_number else None,
                'routing_number': f"****{self.routing_number[-4:]}" if self.routing_number else None,
            })
        elif self.method_type == PaymentMethodType.PAYPAL:
            data['paypal_email'] = self.paypal_email
        elif self.method_type == PaymentMethodType.CRYPTO:
            data.update({
                'crypto_currency': self.crypto_currency,
                'crypto_address': f"{self.crypto_address[:6]}...{self.crypto_address[-4:]}" if self.crypto_address else None,
                'crypto_network': self.crypto_network,
            })
        
        return data