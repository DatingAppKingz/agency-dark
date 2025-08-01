"""Data export service for generating exports in various formats."""

import io
import csv
import json
import zipfile
from typing import List, Dict, Any, Optional, Type, Union
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
import pandas as pd
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from core.logger import get_logger
from models.user import User
from models.agency import Agency
from models.model import Model
from models.transaction import Transaction
from models.message import Message, Conversation
from models.media import MediaFile
from schemas.export import ExportConfig, ExportFormat, ExportResult

logger = get_logger(__name__)


class ExportService:
    """Service for exporting data in various formats."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.exporters = {
            ExportFormat.CSV: self._export_csv,
            ExportFormat.JSON: self._export_json,
            ExportFormat.EXCEL: self._export_excel,
            ExportFormat.PDF: self._export_pdf,
            ExportFormat.ZIP: self._export_zip,
        }
    
    async def export_data(
        self,
        config: ExportConfig,
        user: User
    ) -> ExportResult:
        """Export data based on configuration."""
        try:
            # Check permissions
            if not await self._check_export_permissions(user, config):
                raise ValueError("Insufficient permissions for this export")
            
            # Fetch data based on entity type
            data = await self._fetch_data(config, user)
            
            # Apply filters
            if config.filters:
                data = self._apply_filters(data, config.filters)
            
            # Export to specified format
            exporter = self.exporters.get(config.format)
            if not exporter:
                raise ValueError(f"Unsupported export format: {config.format}")
            
            file_content = await exporter(data, config)
            
            # Generate filename
            filename = self._generate_filename(config)
            
            # Log export
            await self._log_export(user, config, len(data))
            
            return ExportResult(
                filename=filename,
                content=file_content,
                mime_type=self._get_mime_type(config.format),
                size=len(file_content),
                record_count=len(data)
            )
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
    
    async def _fetch_data(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch data based on entity type."""
        entity_fetchers = {
            "users": self._fetch_users,
            "models": self._fetch_models,
            "transactions": self._fetch_transactions,
            "messages": self._fetch_messages,
            "media": self._fetch_media,
            "analytics": self._fetch_analytics,
        }
        
        fetcher = entity_fetchers.get(config.entity_type)
        if not fetcher:
            raise ValueError(f"Unknown entity type: {config.entity_type}")
        
        return await fetcher(config, user)
    
    async def _fetch_users(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch user data."""
        query = select(User)
        
        # Apply agency filter for non-superadmins
        if not user.is_superuser:
            query = query.where(User.agency_id == user.agency_id)
        
        # Apply date range
        if config.date_from:
            query = query.where(User.created_at >= config.date_from)
        if config.date_to:
            query = query.where(User.created_at <= config.date_to)
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # Convert to dict and filter fields
        return [
            self._serialize_user(u, config.fields)
            for u in users
        ]
    
    async def _fetch_models(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch model data."""
        query = select(Model).options(
            selectinload(Model.user),
            selectinload(Model.platforms),
            selectinload(Model.performance_metrics)
        )
        
        # Apply agency filter
        if not user.is_superuser:
            query = query.where(Model.agency_id == user.agency_id)
        
        # Apply date range
        if config.date_from:
            query = query.where(Model.created_at >= config.date_from)
        if config.date_to:
            query = query.where(Model.created_at <= config.date_to)
        
        result = await self.db.execute(query)
        models = result.scalars().all()
        
        return [
            self._serialize_model(m, config.fields)
            for m in models
        ]
    
    async def _fetch_transactions(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch transaction data."""
        query = select(Transaction).options(
            selectinload(Transaction.model),
            selectinload(Transaction.fan)
        )
        
        # Apply agency filter
        if not user.is_superuser:
            query = query.join(Model).where(Model.agency_id == user.agency_id)
        
        # Apply date range
        if config.date_from:
            query = query.where(Transaction.created_at >= config.date_from)
        if config.date_to:
            query = query.where(Transaction.created_at <= config.date_to)
        
        result = await self.db.execute(query)
        transactions = result.scalars().all()
        
        return [
            self._serialize_transaction(t, config.fields)
            for t in transactions
        ]
    
    async def _fetch_messages(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch message data."""
        query = select(Message).options(
            selectinload(Message.conversation),
            selectinload(Message.sender)
        )
        
        # Apply filters based on user role
        if not user.is_superuser:
            if user.role == "MODEL":
                # Models can export their own messages
                query = query.join(Conversation).where(
                    Conversation.model_id == user.model_profile.id
                )
            else:
                # Agency staff can export agency messages
                query = query.join(Conversation).join(Model).where(
                    Model.agency_id == user.agency_id
                )
        
        # Apply date range
        if config.date_from:
            query = query.where(Message.created_at >= config.date_from)
        if config.date_to:
            query = query.where(Message.created_at <= config.date_to)
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        return [
            self._serialize_message(m, config.fields)
            for m in messages
        ]
    
    async def _fetch_media(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch media file metadata."""
        query = select(MediaFile)
        
        # Apply ownership filter
        if not user.is_superuser:
            query = query.where(MediaFile.uploaded_by == user.id)
        
        # Apply date range
        if config.date_from:
            query = query.where(MediaFile.created_at >= config.date_from)
        if config.date_to:
            query = query.where(MediaFile.created_at <= config.date_to)
        
        result = await self.db.execute(query)
        media_files = result.scalars().all()
        
        return [
            self._serialize_media(m, config.fields)
            for m in media_files
        ]
    
    async def _fetch_analytics(
        self,
        config: ExportConfig,
        user: User
    ) -> List[Dict[str, Any]]:
        """Fetch analytics data."""
        # This would fetch from analytics tables
        # For now, return sample data
        return []
    
    def _serialize_user(
        self,
        user: User,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Serialize user to dict."""
        data = {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }
        
        if fields:
            data = {k: v for k, v in data.items() if k in fields}
        
        return data
    
    def _serialize_model(
        self,
        model: Model,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Serialize model to dict."""
        data = {
            "id": str(model.id),
            "stage_name": model.stage_name,
            "real_name": model.real_name,
            "email": model.email,
            "phone": model.phone,
            "status": model.status,
            "commission_rate": float(model.commission_rate) if model.commission_rate else None,
            "total_revenue": float(model.total_revenue) if model.total_revenue else 0,
            "total_fans": model.total_fans,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
        
        # Add platform data
        if model.platforms:
            for platform in model.platforms:
                data[f"{platform.platform}_username"] = platform.username
                data[f"{platform.platform}_status"] = platform.is_active
        
        if fields:
            data = {k: v for k, v in data.items() if k in fields}
        
        return data
    
    def _serialize_transaction(
        self,
        transaction: Transaction,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Serialize transaction to dict."""
        data = {
            "id": str(transaction.id),
            "type": transaction.type,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
            "status": transaction.status,
            "model_name": transaction.model.stage_name if transaction.model else None,
            "fan_username": transaction.fan.username if transaction.fan else None,
            "description": transaction.description,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        }
        
        if fields:
            data = {k: v for k, v in data.items() if k in fields}
        
        return data
    
    def _serialize_message(
        self,
        message: Message,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Serialize message to dict."""
        data = {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "sender": message.sender.username if message.sender else None,
            "content": message.content,
            "type": message.type,
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }
        
        if fields:
            data = {k: v for k, v in data.items() if k in fields}
        
        return data
    
    def _serialize_media(
        self,
        media: MediaFile,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Serialize media file to dict."""
        data = {
            "id": str(media.id),
            "filename": media.filename,
            "file_type": media.file_type,
            "mime_type": media.mime_type,
            "size": media.size,
            "url": media.url,
            "thumbnail_url": media.thumbnail_url,
            "tags": media.tags,
            "created_at": media.created_at.isoformat() if media.created_at else None,
        }
        
        if fields:
            data = {k: v for k, v in data.items() if k in fields}
        
        return data
    
    async def _export_csv(
        self,
        data: List[Dict[str, Any]],
        config: ExportConfig
    ) -> bytes:
        """Export data to CSV format."""
        if not data:
            return b""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue().encode('utf-8')
    
    async def _export_json(
        self,
        data: List[Dict[str, Any]],
        config: ExportConfig
    ) -> bytes:
        """Export data to JSON format."""
        return json.dumps(data, indent=2, default=str).encode('utf-8')
    
    async def _export_excel(
        self,
        data: List[Dict[str, Any]],
        config: ExportConfig
    ) -> bytes:
        """Export data to Excel format."""
        output = io.BytesIO()
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel writer
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Write data
            df.to_excel(writer, sheet_name=config.entity_type, index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets[config.entity_type]
            
            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            # Apply header formatting
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Auto-fit columns
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_width)
        
        output.seek(0)
        return output.read()
    
    async def _export_pdf(
        self,
        data: List[Dict[str, Any]],
        config: ExportConfig
    ) -> bytes:
        """Export data to PDF format."""
        output = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            output,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Container for elements
        elements = []
        
        # Add title
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#4472C4'),
            spaceAfter=30
        )
        
        title = Paragraph(
            f"{config.entity_type.title()} Export",
            title_style
        )
        elements.append(title)
        
        # Add metadata
        metadata_style = ParagraphStyle(
            'Metadata',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey
        )
        
        metadata = Paragraph(
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
            f"Total Records: {len(data)}",
            metadata_style
        )
        elements.append(metadata)
        elements.append(Spacer(1, 12))
        
        # Create table
        if data:
            # Prepare table data
            table_data = [list(data[0].keys())]  # Headers
            for row in data:
                table_data.append([str(v) if v is not None else '' for v in row.values()])
            
            # Create table
            table = Table(table_data)
            
            # Add table style
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        output.seek(0)
        return output.read()
    
    async def _export_zip(
        self,
        data: List[Dict[str, Any]],
        config: ExportConfig
    ) -> bytes:
        """Export data to ZIP format with multiple files."""
        output = io.BytesIO()
        
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add CSV file
            csv_content = await self._export_csv(data, config)
            zipf.writestr(f"{config.entity_type}.csv", csv_content)
            
            # Add JSON file
            json_content = await self._export_json(data, config)
            zipf.writestr(f"{config.entity_type}.json", json_content)
            
            # Add README
            readme_content = f"""
Data Export Information
======================

Entity Type: {config.entity_type}
Export Date: {datetime.now().isoformat()}
Total Records: {len(data)}

Files Included:
- {config.entity_type}.csv: Data in CSV format
- {config.entity_type}.json: Data in JSON format

Generated by AgencyDark Export System
            """.strip()
            
            zipf.writestr("README.txt", readme_content.encode('utf-8'))
        
        output.seek(0)
        return output.read()
    
    def _apply_filters(
        self,
        data: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to data."""
        filtered_data = data
        
        for field, value in filters.items():
            if isinstance(value, dict):
                # Range filter
                if 'min' in value:
                    filtered_data = [
                        d for d in filtered_data
                        if d.get(field) is not None and d[field] >= value['min']
                    ]
                if 'max' in value:
                    filtered_data = [
                        d for d in filtered_data
                        if d.get(field) is not None and d[field] <= value['max']
                    ]
            elif isinstance(value, list):
                # In filter
                filtered_data = [
                    d for d in filtered_data
                    if d.get(field) in value
                ]
            else:
                # Exact match
                filtered_data = [
                    d for d in filtered_data
                    if d.get(field) == value
                ]
        
        return filtered_data
    
    def _generate_filename(self, config: ExportConfig) -> str:
        """Generate filename for export."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extension = config.format.value
        
        if config.format == ExportFormat.ZIP:
            extension = 'zip'
        
        return f"{config.entity_type}_export_{timestamp}.{extension}"
    
    def _get_mime_type(self, format: ExportFormat) -> str:
        """Get MIME type for export format."""
        mime_types = {
            ExportFormat.CSV: 'text/csv',
            ExportFormat.JSON: 'application/json',
            ExportFormat.EXCEL: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ExportFormat.PDF: 'application/pdf',
            ExportFormat.ZIP: 'application/zip',
        }
        return mime_types.get(format, 'application/octet-stream')
    
    async def _check_export_permissions(
        self,
        user: User,
        config: ExportConfig
    ) -> bool:
        """Check if user has permission to export data."""
        # Superadmins can export anything
        if user.is_superuser:
            return True
        
        # Check entity-specific permissions
        permissions = {
            "users": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN"],
            "models": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN", "AGENCY_STAFF"],
            "transactions": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN"],
            "messages": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN", "MODEL"],
            "media": True,  # All users can export their own media
            "analytics": user.role in ["AGENCY_OWNER", "AGENCY_ADMIN"],
        }
        
        return permissions.get(config.entity_type, False)
    
    async def _log_export(
        self,
        user: User,
        config: ExportConfig,
        record_count: int
    ) -> None:
        """Log export activity."""
        logger.info(
            f"Data export by user {user.id}: "
            f"entity={config.entity_type}, "
            f"format={config.format.value}, "
            f"records={record_count}"
        )