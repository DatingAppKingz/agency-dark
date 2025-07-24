"""
Invoice generation and management service.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from modules.financial.domain.models import (
    Invoice,
    InvoiceStatus,
    BillingCycle,
    FinancialTransaction,
    TransactionType
)
from modules.financial.domain.schemas import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceLineItem
)
from core.domain.models import Agency, ModelProfile, User


logger = logging.getLogger(__name__)


class InvoiceService:
    """Handles invoice generation and management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_invoice(
        self,
        invoice_data: InvoiceCreate,
        created_by: User
    ) -> InvoiceResponse:
        """
        Create a new invoice.
        
        Args:
            invoice_data: Invoice details
            created_by: User creating the invoice
            
        Returns:
            Created invoice
        """
        # Verify agency exists
        agency = await self.db.get(Agency, invoice_data.agency_id)
        if not agency:
            raise ValueError("Agency not found")
        
        # Verify model if specified
        if invoice_data.model_id:
            model = await self.db.get(ModelProfile, invoice_data.model_id)
            if not model or str(model.agency_id) != invoice_data.agency_id:
                raise ValueError("Model not found or doesn't belong to agency")
        
        # Generate invoice number
        invoice_number = await self._generate_invoice_number(agency.id)
        
        # Calculate amounts
        subtotal = sum(item.total for item in invoice_data.line_items)
        tax_amount = subtotal * (invoice_data.tax_rate / 100)
        total_amount = subtotal + tax_amount
        
        # Set due date if not provided
        if not invoice_data.due_date:
            invoice_data.due_date = datetime.utcnow() + timedelta(days=30)
        
        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            agency_id=invoice_data.agency_id,
            model_id=invoice_data.model_id,
            billing_cycle_id=invoice_data.billing_cycle_id,
            status=InvoiceStatus.DRAFT,
            due_date=invoice_data.due_date,
            subtotal=subtotal,
            tax_rate=invoice_data.tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_items=[item.model_dump() for item in invoice_data.line_items],
            notes=invoice_data.notes,
            terms_conditions=invoice_data.terms_conditions or self._get_default_terms()
        )
        
        self.db.add(invoice)
        
        # Create financial transaction
        transaction = FinancialTransaction(
            agency_id=invoice_data.agency_id,
            model_id=invoice_data.model_id,
            type=TransactionType.REVENUE,
            amount=total_amount,
            invoice_id=invoice.id,
            description=f"Invoice {invoice_number}",
            transaction_date=datetime.utcnow()
        )
        
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(invoice)
        
        logger.info(f"Created invoice {invoice_number} for {total_amount}")
        
        return InvoiceResponse.model_validate(invoice)
    
    async def update_invoice(
        self,
        invoice_id: str,
        update_data: InvoiceUpdate,
        updated_by: User
    ) -> InvoiceResponse:
        """Update an invoice."""
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        
        # Can't update if already paid
        if invoice.status == InvoiceStatus.PAID:
            raise ValueError("Cannot update paid invoice")
        
        # Update fields
        if update_data.status is not None:
            invoice.status = update_data.status
            
            if update_data.status == InvoiceStatus.PAID:
                invoice.paid_date = datetime.utcnow()
                invoice.paid_amount = invoice.total_amount
        
        if update_data.due_date is not None:
            invoice.due_date = update_data.due_date
        
        if update_data.line_items is not None:
            # Recalculate amounts
            subtotal = sum(item.total for item in update_data.line_items)
            tax_amount = subtotal * (invoice.tax_rate / 100)
            total_amount = subtotal + tax_amount
            
            invoice.line_items = [item.model_dump() for item in update_data.line_items]
            invoice.subtotal = subtotal
            invoice.tax_amount = tax_amount
            invoice.total_amount = total_amount
        
        if update_data.tax_rate is not None:
            invoice.tax_rate = update_data.tax_rate
            invoice.tax_amount = invoice.subtotal * (update_data.tax_rate / 100)
            invoice.total_amount = invoice.subtotal + invoice.tax_amount
        
        if update_data.notes is not None:
            invoice.notes = update_data.notes
        
        if update_data.paid_amount is not None:
            invoice.paid_amount = update_data.paid_amount
        
        if update_data.payment_method is not None:
            invoice.payment_method = update_data.payment_method
        
        if update_data.payment_reference is not None:
            invoice.payment_reference = update_data.payment_reference
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        return InvoiceResponse.model_validate(invoice)
    
    async def send_invoice(
        self,
        invoice_id: str,
        sent_by: User
    ) -> InvoiceResponse:
        """
        Send an invoice to the recipient.
        
        Args:
            invoice_id: Invoice ID
            sent_by: User sending the invoice
            
        Returns:
            Updated invoice
        """
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only send draft invoices")
        
        # Generate PDF if not exists
        if not invoice.pdf_url:
            pdf_url = await self._generate_invoice_pdf(invoice)
            invoice.pdf_url = pdf_url
            invoice.pdf_generated_at = datetime.utcnow()
        
        # Update status
        invoice.status = InvoiceStatus.SENT
        
        # TODO: Send email notification with PDF
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        logger.info(f"Sent invoice {invoice.invoice_number}")
        
        return InvoiceResponse.model_validate(invoice)
    
    async def get_invoices(
        self,
        agency_id: Optional[str] = None,
        model_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        due_date_start: Optional[datetime] = None,
        due_date_end: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InvoiceResponse]:
        """Get invoices with optional filters."""
        query = select(Invoice)
        
        # Add filters
        conditions = []
        if agency_id:
            conditions.append(Invoice.agency_id == agency_id)
        if model_id:
            conditions.append(Invoice.model_id == model_id)
        if status:
            conditions.append(Invoice.status == status)
        if due_date_start:
            conditions.append(Invoice.due_date >= due_date_start)
        if due_date_end:
            conditions.append(Invoice.due_date <= due_date_end)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Invoice.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        invoices = result.scalars().all()
        
        return [InvoiceResponse.model_validate(invoice) for invoice in invoices]
    
    async def create_billing_cycle_invoices(
        self,
        billing_cycle_id: str,
        created_by: User
    ) -> List[InvoiceResponse]:
        """
        Create invoices for all models in a billing cycle.
        
        Args:
            billing_cycle_id: Billing cycle ID
            created_by: User creating invoices
            
        Returns:
            List of created invoices
        """
        cycle = await self.db.get(BillingCycle, billing_cycle_id)
        if not cycle:
            raise ValueError("Billing cycle not found")
        
        if not cycle.is_closed:
            raise ValueError("Billing cycle must be closed before creating invoices")
        
        # Get revenue by model for this cycle
        result = await self.db.execute(
            select(
                FinancialTransaction.model_id,
                func.sum(FinancialTransaction.amount).label('total')
            )
            .where(
                and_(
                    FinancialTransaction.billing_cycle_id == billing_cycle_id,
                    FinancialTransaction.type == TransactionType.REVENUE,
                    FinancialTransaction.model_id.isnot(None)
                )
            )
            .group_by(FinancialTransaction.model_id)
        )
        
        model_revenues = result.all()
        
        # Get commission service
        from modules.financial.application.commission_service import CommissionService
        commission_service = CommissionService(self.db)
        
        created_invoices = []
        
        for model_id, gross_amount in model_revenues:
            # Get model
            model = await self.db.get(ModelProfile, model_id)
            if not model:
                continue
            
            # Calculate commission
            calc = await commission_service.calculate_commission(
                gross_amount,
                str(model_id),
                cycle.cycle_end
            )
            
            # Create line items
            line_items = [
                InvoiceLineItem(
                    description=f"Earnings for period {cycle.cycle_start.date()} - {cycle.cycle_end.date()}",
                    quantity=1,
                    unit_price=gross_amount,
                    total=gross_amount
                ),
                InvoiceLineItem(
                    description=f"Commission ({calc.commission_rate}%)",
                    quantity=1,
                    unit_price=-calc.commission_amount,
                    total=-calc.commission_amount
                )
            ]
            
            # Create invoice
            invoice_data = InvoiceCreate(
                agency_id=str(cycle.agency_id),
                model_id=str(model_id),
                billing_cycle_id=billing_cycle_id,
                line_items=line_items,
                tax_rate=Decimal("0"),  # No tax on model payouts
                notes=f"Net payout: ${calc.net_amount}"
            )
            
            try:
                invoice = await self.create_invoice(invoice_data, created_by)
                created_invoices.append(invoice)
            except Exception as e:
                logger.error(f"Failed to create invoice for model {model_id}: {e}")
        
        # Create agency invoice for commission
        if cycle.total_commission > 0:
            agency_line_items = []
            
            for model_id, _ in model_revenues:
                model = await self.db.get(ModelProfile, model_id)
                if model:
                    # Get model's commission
                    model_calc = await commission_service.calculate_commission(
                        gross_amount,
                        str(model_id),
                        cycle.cycle_end
                    )
                    
                    agency_line_items.append(
                        InvoiceLineItem(
                            description=f"Commission from {model.username}",
                            quantity=1,
                            unit_price=model_calc.commission_amount,
                            total=model_calc.commission_amount
                        )
                    )
            
            agency_invoice_data = InvoiceCreate(
                agency_id=str(cycle.agency_id),
                billing_cycle_id=billing_cycle_id,
                line_items=agency_line_items,
                tax_rate=Decimal("0"),
                notes="Agency commission for billing period"
            )
            
            try:
                invoice = await self.create_invoice(agency_invoice_data, created_by)
                created_invoices.append(invoice)
            except Exception as e:
                logger.error(f"Failed to create agency invoice: {e}")
        
        return created_invoices
    
    async def process_overdue_invoices(self):
        """Mark overdue invoices and send reminders."""
        # Get sent invoices past due date
        result = await self.db.execute(
            select(Invoice).where(
                and_(
                    Invoice.status == InvoiceStatus.SENT,
                    Invoice.due_date < datetime.utcnow()
                )
            )
        )
        
        overdue_invoices = result.scalars().all()
        
        for invoice in overdue_invoices:
            invoice.status = InvoiceStatus.OVERDUE
            
            # TODO: Send overdue notification
            
        await self.db.commit()
        
        logger.info(f"Marked {len(overdue_invoices)} invoices as overdue")
        
        return len(overdue_invoices)
    
    async def _generate_invoice_number(self, agency_id: str) -> str:
        """Generate unique invoice number."""
        # Get count of invoices for this agency this year
        year = datetime.utcnow().year
        
        result = await self.db.execute(
            select(func.count(Invoice.id))
            .where(
                and_(
                    Invoice.agency_id == agency_id,
                    func.extract('year', Invoice.created_at) == year
                )
            )
        )
        
        count = result.scalar() or 0
        
        # Format: INV-YYYY-AAAA-NNNN
        # Where YYYY is year, AAAA is first 4 chars of agency ID, NNNN is sequential number
        agency_prefix = str(agency_id)[:4].upper()
        invoice_number = f"INV-{year}-{agency_prefix}-{count + 1:04d}"
        
        return invoice_number
    
    async def _generate_invoice_pdf(self, invoice: Invoice) -> str:
        """
        Generate PDF for invoice.
        
        Args:
            invoice: Invoice to generate PDF for
            
        Returns:
            URL to generated PDF
        """
        # In production, this would use a PDF generation library like ReportLab
        # and upload to S3 or similar storage
        
        # For MVP, we'll return a placeholder URL
        pdf_filename = f"invoice_{invoice.invoice_number}.pdf"
        pdf_url = f"/api/v1/financial/invoices/{invoice.id}/pdf"
        
        logger.info(f"Generated PDF for invoice {invoice.invoice_number}")
        
        return pdf_url
    
    def _get_default_terms(self) -> str:
        """Get default terms and conditions."""
        return """
Payment Terms:
- Payment is due within 30 days of invoice date
- Late payments may incur additional fees
- All amounts are in USD unless otherwise specified

Service Terms:
- Services provided through AgencyDark platform
- Subject to platform terms of service
- Commission rates as per agreed terms

For questions regarding this invoice, please contact support.
"""