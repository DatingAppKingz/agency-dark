"""PDF generation service for reports."""

import io
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, PageBreak, KeepTogether, Flowable
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
import base64
from io import BytesIO

from core.logger import get_logger
from core.config import settings

logger = get_logger(__name__)


class HeaderFooter:
    """Custom header and footer for PDF pages."""
    
    def __init__(self, title: str, agency_name: str):
        self.title = title
        self.agency_name = agency_name
        self.page_num = 0
    
    def __call__(self, canvas, doc):
        canvas.saveState()
        
        # Header
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawString(inch, letter[1] - 0.5*inch, self.agency_name)
        canvas.setFont('Helvetica', 10)
        canvas.drawRightString(letter[0] - inch, letter[1] - 0.5*inch, 
                              datetime.now().strftime('%B %d, %Y'))
        
        # Footer
        canvas.setFont('Helvetica', 9)
        canvas.drawString(inch, 0.5*inch, self.title)
        canvas.drawRightString(letter[0] - inch, 0.5*inch, f"Page {doc.page}")
        
        # Line separators
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(inch, letter[1] - 0.75*inch, letter[0] - inch, letter[1] - 0.75*inch)
        canvas.line(inch, 0.75*inch, letter[0] - inch, 0.75*inch)
        
        canvas.restoreState()


class PDFGenerator:
    """Service for generating PDF reports."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1E40AF'),
            spaceAfter=30
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3B82F6'),
            spaceAfter=20
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#1F2937'),
            spaceBefore=20,
            spaceAfter=10
        ))
        
        # Metric style
        self.styles.add(ParagraphStyle(
            name='Metric',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#374151')
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=1  # Center
        ))
    
    async def generate_report_pdf(
        self,
        report_data: Dict[str, Any],
        report_type: str,
        agency_name: str = "Agency Dark",
        output_path: Optional[str] = None
    ) -> Union[str, bytes]:
        """
        Generate PDF report from data.
        
        Args:
            report_data: Report data including charts
            report_type: Type of report (revenue, performance, etc.)
            agency_name: Agency name for branding
            output_path: Optional path to save PDF
            
        Returns:
            Path to saved file or bytes if no output path
        """
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build content
        story = []
        
        # Title page
        story.extend(self._build_title_page(report_type, agency_name, report_data))
        story.append(PageBreak())
        
        # Executive summary
        if report_type == 'revenue':
            story.extend(self._build_revenue_summary(report_data))
        elif report_type == 'performance':
            story.extend(self._build_performance_summary(report_data))
        elif report_type == 'financial':
            story.extend(self._build_financial_summary(report_data))
        
        # Add charts if available
        if report_data.get('charts'):
            story.append(PageBreak())
            story.extend(self._build_charts_section(report_data['charts']))
        
        # Detailed data tables
        story.append(PageBreak())
        story.extend(self._build_data_tables(report_data, report_type))
        
        # Build PDF
        header_footer = HeaderFooter(f"{report_type.title()} Report", agency_name)
        doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
        
        # Return result
        buffer.seek(0)
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(buffer.read())
            return output_path
        else:
            return buffer.read()
    
    def _build_title_page(
        self,
        report_type: str,
        agency_name: str,
        report_data: Dict[str, Any]
    ) -> List[Flowable]:
        """Build title page elements."""
        elements = []
        
        # Agency logo placeholder
        logo_spacer = Spacer(1, 2*inch)
        elements.append(logo_spacer)
        
        # Title
        title = Paragraph(
            f"{report_type.replace('_', ' ').title()} Report",
            self.styles['CustomTitle']
        )
        elements.append(title)
        
        # Agency name
        agency = Paragraph(agency_name, self.styles['Subtitle'])
        elements.append(agency)
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Report period
        if report_data.get('period'):
            period = report_data['period']
            if isinstance(period, dict):
                if 'start' in period and 'end' in period:
                    period_text = f"{period['start']} to {period['end']}"
                else:
                    period_text = str(period)
            else:
                period_text = str(period)
            
            period_para = Paragraph(
                f"Report Period: {period_text}",
                self.styles['Metric']
            )
            elements.append(period_para)
        
        # Generated date
        generated = Paragraph(
            f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            self.styles['Metric']
        )
        elements.append(generated)
        
        return elements
    
    def _build_revenue_summary(self, report_data: Dict[str, Any]) -> List[Flowable]:
        """Build revenue report summary."""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['Subtitle']))
        
        if report_data.get('data') and report_data['data'].get('summary'):
            summary = report_data['data']['summary']
            
            # Key metrics table
            metrics_data = [
                ['Metric', 'Value'],
                ['Total Gross Revenue', f"${summary.get('total_gross', 0):,.2f}"],
                ['Total Net Revenue', f"${summary.get('total_net', 0):,.2f}"],
                ['Platform Fees', f"${summary.get('total_fees', 0):,.2f}"],
                ['Total Transactions', f"{summary.get('total_transactions', 0):,}"],
                ['Average Daily Revenue', f"${summary.get('avg_daily_revenue', 0):,.2f}"],
                ['Growth Rate', f"{summary.get('growth_rate', 0):.1f}%"]
            ]
            
            metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E5E7EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))
            
            elements.append(Spacer(1, 0.25*inch))
            elements.append(metrics_table)
        
        return elements
    
    def _build_performance_summary(self, report_data: Dict[str, Any]) -> List[Flowable]:
        """Build performance report summary."""
        elements = []
        
        elements.append(Paragraph("Performance Overview", self.styles['Subtitle']))
        
        if report_data.get('metrics'):
            metrics = report_data['metrics']
            
            # Create summary paragraphs
            if metrics.get('revenue'):
                revenue_text = f"Total Revenue: ${metrics['revenue'].get('total', 0):,.2f}"
                elements.append(Paragraph(revenue_text, self.styles['Metric']))
            
            if metrics.get('users'):
                users_text = f"Total Users: {metrics['users'].get('total', 0):,}"
                elements.append(Paragraph(users_text, self.styles['Metric']))
            
            if metrics.get('engagement'):
                engagement_text = f"Average Engagement Rate: {metrics['engagement'].get('avg_engagement_rate', 0):.1f}%"
                elements.append(Paragraph(engagement_text, self.styles['Metric']))
        
        return elements
    
    def _build_financial_summary(self, report_data: Dict[str, Any]) -> List[Flowable]:
        """Build financial report summary."""
        elements = []
        
        elements.append(Paragraph("Financial Summary", self.styles['Subtitle']))
        
        if report_data.get('financial_data') and report_data['financial_data'].get('summary'):
            summary = report_data['financial_data']['summary']
            
            # Financial overview table
            financial_data = []
            
            if summary.get('revenue'):
                for key, value in summary['revenue'].items():
                    financial_data.append([f"Revenue - {key.replace('_', ' ').title()}", f"${value:,.2f}"])
            
            if summary.get('expenses'):
                for key, value in summary['expenses'].items():
                    financial_data.append([f"Expense - {key.replace('_', ' ').title()}", f"${value:,.2f}"])
            
            if summary.get('profit'):
                for key, value in summary['profit'].items():
                    financial_data.append([f"Profit - {key.replace('_', ' ').title()}", f"${value:,.2f}"])
            
            if financial_data:
                financial_table = Table(financial_data, colWidths=[3.5*inch, 2*inch])
                financial_table.setStyle(TableStyle([
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey)
                ]))
                
                elements.append(Spacer(1, 0.25*inch))
                elements.append(financial_table)
        
        return elements
    
    def _build_charts_section(self, charts: Dict[str, str]) -> List[Flowable]:
        """Build charts section from base64 encoded images."""
        elements = []
        
        elements.append(Paragraph("Charts & Visualizations", self.styles['Subtitle']))
        
        for chart_name, chart_data in charts.items():
            if chart_data and chart_data.startswith('data:image'):
                try:
                    # Extract base64 data
                    base64_data = chart_data.split(',')[1]
                    image_data = base64.b64decode(base64_data)
                    
                    # Create image
                    img = Image(BytesIO(image_data), width=6*inch, height=4*inch)
                    
                    # Add title and image
                    title = chart_name.replace('_', ' ').title()
                    elements.append(Paragraph(title, self.styles['SectionHeader']))
                    elements.append(img)
                    elements.append(Spacer(1, 0.5*inch))
                    
                except Exception as e:
                    logger.error(f"Error adding chart {chart_name}: {e}")
        
        return elements
    
    def _build_data_tables(self, report_data: Dict[str, Any], report_type: str) -> List[Flowable]:
        """Build detailed data tables."""
        elements = []
        
        elements.append(Paragraph("Detailed Data", self.styles['Subtitle']))
        
        if report_type == 'revenue' and report_data.get('data', {}).get('data'):
            elements.extend(self._build_revenue_table(report_data['data']['data']))
        elif report_type == 'performance' and report_data.get('metrics'):
            elements.extend(self._build_performance_tables(report_data['metrics']))
        elif report_type == 'financial' and report_data.get('financial_data'):
            elements.extend(self._build_financial_tables(report_data['financial_data']))
        
        return elements
    
    def _build_revenue_table(self, revenue_data: List[Dict[str, Any]]) -> List[Flowable]:
        """Build revenue data table."""
        elements = []
        
        elements.append(Paragraph("Daily Revenue Breakdown", self.styles['SectionHeader']))
        
        # Table headers
        headers = ['Date', 'Transactions', 'Gross Revenue', 'Fees', 'Net Revenue']
        table_data = [headers]
        
        # Add data rows
        for item in revenue_data[:30]:  # Limit to 30 rows for PDF
            row = [
                item.get('period', '')[:10],  # Date only
                str(item.get('transaction_count', 0)),
                f"${item.get('gross_revenue', 0):,.2f}",
                f"${item.get('platform_fees', 0):,.2f}",
                f"${item.get('net_revenue', 0):,.2f}"
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')])
        ]))
        
        elements.append(table)
        
        if len(revenue_data) > 30:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(
                f"* Showing first 30 of {len(revenue_data)} records",
                self.styles['Footer']
            ))
        
        return elements
    
    def _build_performance_tables(self, metrics: Dict[str, Any]) -> List[Flowable]:
        """Build performance metric tables."""
        elements = []
        
        # Add different metric sections
        for metric_type, metric_data in metrics.items():
            if isinstance(metric_data, dict) and any(isinstance(v, list) for v in metric_data.values()):
                elements.append(Paragraph(
                    f"{metric_type.replace('_', ' ').title()} Metrics",
                    self.styles['SectionHeader']
                ))
                
                # Find first list in metric data
                for key, value in metric_data.items():
                    if isinstance(value, list) and value:
                        # Create simple table from list data
                        table_data = []
                        if isinstance(value[0], dict):
                            # Extract headers from first item
                            headers = list(value[0].keys())
                            table_data.append([h.replace('_', ' ').title() for h in headers])
                            
                            # Add rows
                            for item in value[:20]:  # Limit rows
                                row = [str(item.get(h, '')) for h in headers]
                                table_data.append(row)
                            
                            if table_data:
                                col_width = 6.5 * inch / len(headers)
                                table = Table(table_data, colWidths=[col_width] * len(headers))
                                table.setStyle(self._get_basic_table_style())
                                elements.append(table)
                                elements.append(Spacer(1, 0.25*inch))
                        break
        
        return elements
    
    def _build_financial_tables(self, financial_data: Dict[str, Any]) -> List[Flowable]:
        """Build financial data tables."""
        elements = []
        
        if financial_data.get('monthly_breakdown'):
            elements.append(Paragraph("Monthly Financial Breakdown", self.styles['SectionHeader']))
            
            # Create monthly table
            headers = ['Month', 'Revenue', 'Expenses', 'Profit', 'Margin']
            table_data = [headers]
            
            for item in financial_data['monthly_breakdown']:
                row = [
                    item.get('month', ''),
                    f"${item.get('revenue', 0):,.2f}",
                    f"${item.get('expenses', 0):,.2f}",
                    f"${item.get('profit', 0):,.2f}",
                    f"{item.get('margin', 0):.1f}%"
                ]
                table_data.append(row)
            
            table = Table(table_data, colWidths=[1.3*inch] * 5)
            table.setStyle(self._get_financial_table_style())
            elements.append(table)
        
        return elements
    
    def _get_basic_table_style(self) -> TableStyle:
        """Get basic table style."""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9)
        ])
    
    def _get_financial_table_style(self) -> TableStyle:
        """Get financial table style."""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
        ])
    
    async def generate_invoice_pdf(
        self,
        invoice_data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> Union[str, bytes]:
        """Generate PDF invoice."""
        buffer = BytesIO()
        
        # Create canvas for custom invoice layout
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Header
        c.setFont("Helvetica-Bold", 24)
        c.drawString(72, height - 72, "INVOICE")
        
        # Invoice details
        c.setFont("Helvetica", 12)
        c.drawRightString(width - 72, height - 72, f"Invoice #: {invoice_data.get('invoice_number', 'N/A')}")
        c.drawRightString(width - 72, height - 90, f"Date: {invoice_data.get('date', datetime.now().strftime('%B %d, %Y'))}")
        
        # Company info
        y_position = height - 150
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, y_position, invoice_data.get('company_name', 'Agency Dark'))
        
        c.setFont("Helvetica", 10)
        y_position -= 20
        c.drawString(72, y_position, invoice_data.get('company_address', ''))
        y_position -= 15
        c.drawString(72, y_position, invoice_data.get('company_email', ''))
        
        # Bill to
        y_position -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y_position, "Bill To:")
        
        c.setFont("Helvetica", 10)
        y_position -= 20
        c.drawString(72, y_position, invoice_data.get('client_name', ''))
        y_position -= 15
        c.drawString(72, y_position, invoice_data.get('client_address', ''))
        y_position -= 15
        c.drawString(72, y_position, invoice_data.get('client_email', ''))
        
        # Line items
        y_position -= 40
        c.setFont("Helvetica-Bold", 10)
        c.drawString(72, y_position, "Description")
        c.drawRightString(width - 200, y_position, "Quantity")
        c.drawRightString(width - 130, y_position, "Rate")
        c.drawRightString(width - 72, y_position, "Amount")
        
        c.line(72, y_position - 5, width - 72, y_position - 5)
        
        # Items
        c.setFont("Helvetica", 10)
        y_position -= 20
        
        subtotal = 0
        for item in invoice_data.get('items', []):
            c.drawString(72, y_position, item['description'])
            c.drawRightString(width - 200, y_position, str(item['quantity']))
            c.drawRightString(width - 130, y_position, f"${item['rate']:,.2f}")
            amount = item['quantity'] * item['rate']
            c.drawRightString(width - 72, y_position, f"${amount:,.2f}")
            subtotal += amount
            y_position -= 20
        
        # Totals
        y_position -= 20
        c.line(width - 250, y_position, width - 72, y_position)
        
        y_position -= 20
        c.drawString(width - 250, y_position, "Subtotal:")
        c.drawRightString(width - 72, y_position, f"${subtotal:,.2f}")
        
        tax_rate = invoice_data.get('tax_rate', 0)
        if tax_rate > 0:
            y_position -= 20
            tax_amount = subtotal * tax_rate / 100
            c.drawString(width - 250, y_position, f"Tax ({tax_rate}%):")
            c.drawRightString(width - 72, y_position, f"${tax_amount:,.2f}")
            total = subtotal + tax_amount
        else:
            total = subtotal
        
        y_position -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(width - 250, y_position, "Total:")
        c.drawRightString(width - 72, y_position, f"${total:,.2f}")
        
        # Payment terms
        y_position -= 60
        c.setFont("Helvetica", 10)
        c.drawString(72, y_position, f"Payment Terms: {invoice_data.get('payment_terms', 'Due on receipt')}")
        
        # Save PDF
        c.save()
        
        buffer.seek(0)
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(buffer.read())
            return output_path
        else:
            return buffer.read()


# Singleton instance
_pdf_generator = None


def get_pdf_generator() -> PDFGenerator:
    """Get singleton instance of PDF generator."""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFGenerator()
    return _pdf_generator