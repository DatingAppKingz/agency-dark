"""Invoice management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid
from io import BytesIO
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from core.database import get_db
from models.user import User, UserRole
from models.agency import Agency
from models.financial import Invoice
from models.financial import Transaction
from api.v1.endpoints.auth_simple import get_current_user
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class InvoiceCreate(BaseModel):
    """Create a new invoice."""
    agency_id: int
    period_start: str
    period_end: str
    due_days: int = Field(default=30, ge=1, le=90)
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    """Update invoice details."""
    due_date: Optional[str] = None
    notes: Optional[str] = None
    line_items: Optional[List[Dict[str, Any]]] = None


class InvoiceResponse(BaseModel):
    """Invoice response model."""
    id: int
    agency_id: int
    agency_name: str
    invoice_number: str
    invoice_date: str
    due_date: str
    period_start: str
    period_end: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    is_paid: bool
    paid_date: Optional[str]
    payment_method: Optional[str]
    line_items: List[Dict[str, Any]]
    stripe_invoice_id: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agency_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get invoices with filters."""
    # Base query
    query = select(Invoice).join(Agency)
    
    # Apply filters based on user role
    if current_user.role == UserRole.AGENCY_OWNER:
        # Agency owners can only see their own invoices
        query = query.where(Invoice.agency_id == current_user.agency_id)
    elif current_user.role == UserRole.SUPER_ADMIN:
        # Super admins can see all invoices
        if agency_id:
            query = query.where(Invoice.agency_id == agency_id)
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Apply filters
    if status:
        if status == 'paid':
            query = query.where(Invoice.is_paid == True)
        elif status == 'unpaid':
            query = query.where(Invoice.is_paid == False)
        elif status == 'overdue':
            query = query.where(
                and_(
                    Invoice.is_paid == False,
                    Invoice.due_date < datetime.utcnow().isoformat()
                )
            )
    
    if start_date:
        query = query.where(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.where(Invoice.invoice_date <= end_date)
    
    # Order and paginate
    query = query.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    
    invoices = await db.scalars(query)
    
    # Format response
    result = []
    for invoice in invoices:
        agency = await db.get(Agency, invoice.agency_id)
        
        result.append(InvoiceResponse(
            id=invoice.id,
            agency_id=invoice.agency_id,
            agency_name=agency.name if agency else "Unknown",
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            subtotal=invoice.subtotal,
            tax_amount=invoice.tax_amount,
            total_amount=invoice.total_amount,
            currency=invoice.currency,
            is_paid=invoice.is_paid,
            paid_date=invoice.paid_date,
            payment_method=invoice.payment_method,
            line_items=invoice.line_items,
            stripe_invoice_id=invoice.stripe_invoice_id,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at
        ))
    
    return result


@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new invoice for an agency."""
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can create invoices")
    
    # Get agency
    agency = await db.get(Agency, invoice_data.agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    # Calculate invoice from transactions if no line items provided
    if not invoice_data.line_items:
        # Get all transactions for the period
        transactions_query = select(Transaction).where(
            and_(
                Transaction.agency_id == agency.id,
                Transaction.transaction_date >= invoice_data.period_start,
                Transaction.transaction_date <= invoice_data.period_end,
                Transaction.status == 'completed'
            )
        )
        transactions = await db.scalars(transactions_query)
        transactions_list = list(transactions)
        
        if not transactions_list:
            raise HTTPException(status_code=400, detail="No transactions found for the specified period")
        
        # Calculate totals
        total_revenue = sum(t.gross_amount for t in transactions_list)
        total_commission = sum(t.agency_commission for t in transactions_list)
        
        # Create line items
        line_items = [
            {
                'description': f'Platform management fee for {len(transactions_list)} transactions',
                'quantity': 1,
                'unit_price': float(total_commission * Decimal('0.1')),  # 10% platform fee
                'amount': float(total_commission * Decimal('0.1'))
            }
        ]
        
        subtotal = total_commission * Decimal('0.1')
    else:
        line_items = invoice_data.line_items
        subtotal = sum(Decimal(str(item['amount'])) for item in line_items)
    
    # Calculate tax (if applicable)
    tax_rate = Decimal('0.0')  # No tax by default
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount
    
    # Generate invoice number
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}"
    
    # Calculate due date
    invoice_date = datetime.utcnow()
    due_date = invoice_date + timedelta(days=invoice_data.due_days)
    
    # Create invoice
    invoice = Invoice(
        agency_id=agency.id,
        invoice_number=invoice_number,
        invoice_date=invoice_date.isoformat(),
        due_date=due_date.isoformat(),
        period_start=invoice_data.period_start,
        period_end=invoice_data.period_end,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        currency="USD",
        is_paid=False,
        line_items=line_items
    )
    
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    
    return InvoiceResponse(
        id=invoice.id,
        agency_id=invoice.agency_id,
        agency_name=agency.name,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        is_paid=invoice.is_paid,
        paid_date=invoice.paid_date,
        payment_method=invoice.payment_method,
        line_items=invoice.line_items,
        stripe_invoice_id=invoice.stripe_invoice_id,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific invoice."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.role == UserRole.AGENCY_OWNER:
        if invoice.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agency = await db.get(Agency, invoice.agency_id)
    
    return InvoiceResponse(
        id=invoice.id,
        agency_id=invoice.agency_id,
        agency_name=agency.name if agency else "Unknown",
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        is_paid=invoice.is_paid,
        paid_date=invoice.paid_date,
        payment_method=invoice.payment_method,
        line_items=invoice.line_items,
        stripe_invoice_id=invoice.stripe_invoice_id,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at
    )


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid(
    invoice_id: int,
    payment_data: Dict[str, str] = {},
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark an invoice as paid."""
    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can mark invoices as paid")
    
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.is_paid:
        raise HTTPException(status_code=400, detail="Invoice is already paid")
    
    # Update invoice
    invoice.is_paid = True
    invoice.paid_date = payment_data.get('paid_date', datetime.utcnow().isoformat())
    invoice.payment_method = payment_data.get('payment_method', 'manual')
    invoice.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(invoice)
    
    agency = await db.get(Agency, invoice.agency_id)
    
    return InvoiceResponse(
        id=invoice.id,
        agency_id=invoice.agency_id,
        agency_name=agency.name if agency else "Unknown",
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        is_paid=invoice.is_paid,
        paid_date=invoice.paid_date,
        payment_method=invoice.payment_method,
        line_items=invoice.line_items,
        stripe_invoice_id=invoice.stripe_invoice_id,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at
    )


@router.get("/{invoice_id}/download")
async def download_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download invoice as PDF."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.role == UserRole.AGENCY_OWNER:
        if invoice.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    agency = await db.get(Agency, invoice.agency_id)
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#333333'),
        spaceAfter=30,
    )
    
    # Title
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 12))
    
    # Invoice details
    invoice_info = [
        ['Invoice Number:', invoice.invoice_number],
        ['Invoice Date:', format(datetime.fromisoformat(invoice.invoice_date), '%B %d, %Y')],
        ['Due Date:', format(datetime.fromisoformat(invoice.due_date), '%B %d, %Y')],
        ['Status:', 'PAID' if invoice.is_paid else 'UNPAID'],
    ]
    
    t = Table(invoice_info, colWidths=[2*inch, 4*inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Billing info
    elements.append(Paragraph("Bill To:", styles['Heading2']))
    elements.append(Paragraph(agency.name if agency else "Unknown Agency", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Line items
    elements.append(Paragraph("Details:", styles['Heading2']))
    
    line_items_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
    for item in invoice.line_items:
        line_items_data.append([
            item['description'],
            str(item['quantity']),
            f"${item['unit_price']:,.2f}",
            f"${item['amount']:,.2f}"
        ])
    
    t = Table(line_items_data, colWidths=[3.5*inch, 1*inch, 1.25*inch, 1.25*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Totals
    totals_data = [
        ['Subtotal:', f"${invoice.subtotal:,.2f}"],
        ['Tax:', f"${invoice.tax_amount:,.2f}"],
        ['Total:', f"${invoice.total_amount:,.2f}"],
    ]
    
    t = Table(totals_data, colWidths=[5.5*inch, 1.5*inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, -1), (-1, -1), colors.grey),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    elements.append(t)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{invoice.invoice_number}.pdf"'
        }
    )


@router.get("/agency/{agency_id}/summary", response_model=Dict[str, Any])
async def get_agency_invoice_summary(
    agency_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get invoice summary for an agency."""
    # Check permissions
    if current_user.role == UserRole.AGENCY_OWNER:
        if current_user.agency_id != agency_id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get all invoices for the agency
    query = select(Invoice).where(Invoice.agency_id == agency_id)
    invoices = await db.scalars(query)
    invoices_list = list(invoices)
    
    # Calculate summary
    total_invoiced = sum(i.total_amount for i in invoices_list)
    total_paid = sum(i.total_amount for i in invoices_list if i.is_paid)
    total_unpaid = sum(i.total_amount for i in invoices_list if not i.is_paid)
    
    # Check for overdue invoices
    overdue_invoices = [
        i for i in invoices_list 
        if not i.is_paid and datetime.fromisoformat(i.due_date) < datetime.utcnow()
    ]
    total_overdue = sum(i.total_amount for i in overdue_invoices)
    
    return {
        'total_invoices': len(invoices_list),
        'total_invoiced': float(total_invoiced),
        'total_paid': float(total_paid),
        'total_unpaid': float(total_unpaid),
        'total_overdue': float(total_overdue),
        'overdue_count': len(overdue_invoices),
        'currency': 'USD'
    }