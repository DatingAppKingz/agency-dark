"""Export and import background tasks."""

import os
import json
import csv
import zipfile
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import asyncio
import pandas as pd
from io import BytesIO, StringIO

from core.database_sync import get_db_sync
from core.logger import get_logger
from core.config import settings
from models.user import User
from models.agency import Agency
from models.model import Model
from models.message import Message
from models.transaction import Transaction
from models.media import Media

logger = get_logger(__name__)


class ExportTask(Task):
    """Base task for export operations."""
    _db = None

    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            self._db = get_db_sync()
        return self._db


@shared_task(bind=True, base=ExportTask, name='tasks.export_tasks.export_agency_data')
def export_agency_data(
    self, 
    agency_id: str, 
    user_id: str,
    export_options: Optional[Dict[str, Any]] = None
):
    """
    Export all agency data to a ZIP file.
    
    Includes:
    - Agency settings
    - Users and models
    - Messages
    - Transactions
    - Media metadata
    - Analytics data
    """
    try:
        logger.info(f"Starting agency data export for {agency_id}")
        
        # Default options
        options = {
            'include_media': False,
            'date_from': None,
            'date_to': None,
            'format': 'json',  # json, csv, excel
            **export_options or {}
        }
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            export_files = []
            
            # Export agency info
            agency_data = asyncio.run(self._export_agency_info(agency_id))
            agency_file = os.path.join(temp_dir, f'agency.{options["format"]}')
            self._save_data(agency_data, agency_file, options['format'])
            export_files.append(('agency', agency_file))
            
            # Export users
            users_data = asyncio.run(self._export_users(agency_id))
            users_file = os.path.join(temp_dir, f'users.{options["format"]}')
            self._save_data(users_data, users_file, options['format'])
            export_files.append(('users', users_file))
            
            # Export models
            models_data = asyncio.run(self._export_models(agency_id))
            models_file = os.path.join(temp_dir, f'models.{options["format"]}')
            self._save_data(models_data, models_file, options['format'])
            export_files.append(('models', models_file))
            
            # Export messages (with date filter)
            messages_data = asyncio.run(self._export_messages(
                agency_id, 
                options['date_from'], 
                options['date_to']
            ))
            messages_file = os.path.join(temp_dir, f'messages.{options["format"]}')
            self._save_data(messages_data, messages_file, options['format'])
            export_files.append(('messages', messages_file))
            
            # Export transactions
            transactions_data = asyncio.run(self._export_transactions(
                agency_id,
                options['date_from'],
                options['date_to']
            ))
            transactions_file = os.path.join(temp_dir, f'transactions.{options["format"]}')
            self._save_data(transactions_data, transactions_file, options['format'])
            export_files.append(('transactions', transactions_file))
            
            # Export media metadata
            media_data = asyncio.run(self._export_media_metadata(agency_id))
            media_file = os.path.join(temp_dir, f'media.{options["format"]}')
            self._save_data(media_data, media_file, options['format'])
            export_files.append(('media', media_file))
            
            # Export analytics
            analytics_data = asyncio.run(self._export_analytics(
                agency_id,
                options['date_from'],
                options['date_to']
            ))
            analytics_file = os.path.join(temp_dir, f'analytics.{options["format"]}')
            self._save_data(analytics_data, analytics_file, options['format'])
            export_files.append(('analytics', analytics_file))
            
            # Create ZIP file
            export_filename = f"agency_export_{agency_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
            export_path = os.path.join(settings.EXPORT_DIR, export_filename)
            
            os.makedirs(settings.EXPORT_DIR, exist_ok=True)
            
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, filepath in export_files:
                    arcname = f"{name}.{options['format']}"
                    zipf.write(filepath, arcname)
                
                # Add export metadata
                metadata = {
                    'export_date': datetime.utcnow().isoformat(),
                    'agency_id': agency_id,
                    'exported_by': user_id,
                    'options': options,
                    'files': [name for name, _ in export_files]
                }
                zipf.writestr('export_metadata.json', json.dumps(metadata, indent=2))
            
            # Generate download URL
            download_url = f"{settings.API_URL}/exports/{export_filename}"
            
            # Send notification
            asyncio.run(self._send_export_notification(
                user_id, 
                download_url, 
                export_filename
            ))
            
            logger.info(f"Successfully exported agency data to {export_filename}")
            
            return {
                "success": True,
                "filename": export_filename,
                "download_url": download_url,
                "size": os.path.getsize(export_path)
            }
            
    except SoftTimeLimitExceeded:
        logger.error(f"Export timeout for agency {agency_id}")
        asyncio.run(self._send_export_failure_notification(
            user_id, 
            "Export timed out. Please try with a smaller date range."
        ))
        raise
        
    except Exception as e:
        logger.error(f"Error exporting agency data: {e}")
        asyncio.run(self._send_export_failure_notification(user_id, str(e)))
        return {"success": False, "error": str(e)}
    
    async def _export_agency_info(self, agency_id: str) -> Dict[str, Any]:
        """Export agency information."""
        async with self.db as session:
            agency = await session.get(Agency, agency_id)
            if not agency:
                raise ValueError(f"Agency {agency_id} not found")
            
            return {
                'id': str(agency.id),
                'name': agency.name,
                'email': agency.email,
                'created_at': agency.created_at.isoformat(),
                'settings': agency.settings,
                'subscription_tier': agency.subscription_tier,
                'storage_quota_gb': agency.storage_quota_gb,
                'is_active': agency.is_active
            }
    
    async def _export_users(self, agency_id: str) -> List[Dict[str, Any]]:
        """Export agency users."""
        async with self.db as session:
            result = await session.execute(
                select(User).where(User.agency_id == agency_id)
            )
            users = result.scalars().all()
            
            return [
                {
                    'id': str(user.id),
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
                for user in users
            ]
    
    async def _export_models(self, agency_id: str) -> List[Dict[str, Any]]:
        """Export agency models."""
        async with self.db as session:
            result = await session.execute(
                select(Model).where(Model.agency_id == agency_id)
            )
            models = result.scalars().all()
            
            return [
                {
                    'id': str(model.id),
                    'platform_id': model.platform_id,
                    'username': model.username,
                    'display_name': model.display_name,
                    'platform': model.platform,
                    'is_active': model.is_active,
                    'created_at': model.created_at.isoformat(),
                    'stats': {
                        'total_fans': model.total_fans,
                        'total_revenue': float(model.total_revenue) if model.total_revenue else 0,
                        'message_count': model.message_count
                    }
                }
                for model in models
            ]
    
    async def _export_messages(
        self, 
        agency_id: str, 
        date_from: Optional[str], 
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Export messages with optional date filter."""
        async with self.db as session:
            query = select(Message).join(Model).where(Model.agency_id == agency_id)
            
            if date_from:
                query = query.where(Message.created_at >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.where(Message.created_at <= datetime.fromisoformat(date_to))
            
            query = query.limit(10000)  # Limit to prevent memory issues
            
            result = await session.execute(query)
            messages = result.scalars().all()
            
            return [
                {
                    'id': str(msg.id),
                    'model_id': str(msg.model_id),
                    'fan_id': str(msg.fan_id),
                    'content': msg.content,
                    'is_from_fan': msg.is_from_fan,
                    'platform': msg.platform,
                    'created_at': msg.created_at.isoformat(),
                    'has_media': msg.has_media,
                    'tip_amount': float(msg.tip_amount) if msg.tip_amount else 0
                }
                for msg in messages
            ]
    
    async def _export_transactions(
        self,
        agency_id: str,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Export transactions."""
        async with self.db as session:
            query = select(Transaction).join(Model).where(Model.agency_id == agency_id)
            
            if date_from:
                query = query.where(Transaction.created_at >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.where(Transaction.created_at <= datetime.fromisoformat(date_to))
            
            result = await session.execute(query)
            transactions = result.scalars().all()
            
            return [
                {
                    'id': str(tx.id),
                    'model_id': str(tx.model_id),
                    'fan_id': str(tx.fan_id),
                    'type': tx.type,
                    'amount': float(tx.amount),
                    'currency': tx.currency,
                    'status': tx.status,
                    'platform': tx.platform,
                    'created_at': tx.created_at.isoformat(),
                    'commission_amount': float(tx.commission_amount) if tx.commission_amount else 0
                }
                for tx in transactions
            ]
    
    async def _export_media_metadata(self, agency_id: str) -> List[Dict[str, Any]]:
        """Export media metadata (not actual files)."""
        async with self.db as session:
            result = await session.execute(
                select(Media).where(Media.agency_id == agency_id)
            )
            media_items = result.scalars().all()
            
            return [
                {
                    'id': str(media.id),
                    'filename': media.original_filename,
                    'media_type': media.media_type.value,
                    'file_size': media.file_size,
                    'mime_type': media.mime_type,
                    'width': media.width,
                    'height': media.height,
                    'duration': media.duration,
                    'created_at': media.created_at.isoformat(),
                    'uploaded_by': str(media.uploaded_by),
                    'tags': media.tags,
                    'view_count': media.view_count,
                    'download_count': media.download_count
                }
                for media in media_items
            ]
    
    async def _export_analytics(
        self,
        agency_id: str,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> Dict[str, Any]:
        """Export analytics summary."""
        # Implement analytics export
        # This would aggregate various metrics
        return {
            'period': {
                'from': date_from or 'all_time',
                'to': date_to or 'current'
            },
            'summary': {
                'total_revenue': 0,
                'total_messages': 0,
                'total_fans': 0,
                'active_models': 0
            },
            'daily_metrics': []
        }
    
    def _save_data(self, data: Any, filepath: str, format: str):
        """Save data in specified format."""
        if format == 'json':
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        
        elif format == 'csv':
            if isinstance(data, list) and data:
                df = pd.DataFrame(data)
                df.to_csv(filepath, index=False)
            elif isinstance(data, dict):
                # For single records, convert to list
                df = pd.DataFrame([data])
                df.to_csv(filepath, index=False)
        
        elif format == 'excel':
            if isinstance(data, list) and data:
                df = pd.DataFrame(data)
                df.to_excel(filepath, index=False)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
                df.to_excel(filepath, index=False)
    
    async def _send_export_notification(self, user_id: str, download_url: str, filename: str):
        """Send notification when export is ready."""
        # Implement notification sending
        logger.info(f"Export ready for user {user_id}: {filename}")
    
    async def _send_export_failure_notification(self, user_id: str, error: str):
        """Send notification when export fails."""
        logger.error(f"Export failed for user {user_id}: {error}")


@shared_task(bind=True, base=ExportTask, name='tasks.export_tasks.export_model_data')
def export_model_data(
    self,
    model_id: str,
    user_id: str,
    export_options: Optional[Dict[str, Any]] = None
):
    """Export data for a specific model."""
    try:
        logger.info(f"Starting model data export for {model_id}")
        
        options = {
            'include_messages': True,
            'include_transactions': True,
            'include_media': False,
            'date_from': None,
            'date_to': None,
            'format': 'json',
            **export_options or {}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            export_files = []
            
            # Export model info
            model_data = asyncio.run(self._export_model_info(model_id))
            model_file = os.path.join(temp_dir, f'model.{options["format"]}')
            self._save_data(model_data, model_file, options['format'])
            export_files.append(('model', model_file))
            
            # Export fans
            fans_data = asyncio.run(self._export_model_fans(model_id))
            fans_file = os.path.join(temp_dir, f'fans.{options["format"]}')
            self._save_data(fans_data, fans_file, options['format'])
            export_files.append(('fans', fans_file))
            
            if options['include_messages']:
                # Export messages
                messages_data = asyncio.run(self._export_model_messages(
                    model_id,
                    options['date_from'],
                    options['date_to']
                ))
                messages_file = os.path.join(temp_dir, f'messages.{options["format"]}')
                self._save_data(messages_data, messages_file, options['format'])
                export_files.append(('messages', messages_file))
            
            if options['include_transactions']:
                # Export transactions
                transactions_data = asyncio.run(self._export_model_transactions(
                    model_id,
                    options['date_from'],
                    options['date_to']
                ))
                transactions_file = os.path.join(temp_dir, f'transactions.{options["format"]}')
                self._save_data(transactions_data, transactions_file, options['format'])
                export_files.append(('transactions', transactions_file))
            
            # Create ZIP file
            export_filename = f"model_export_{model_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
            export_path = os.path.join(settings.EXPORT_DIR, export_filename)
            
            os.makedirs(settings.EXPORT_DIR, exist_ok=True)
            
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, filepath in export_files:
                    arcname = f"{name}.{options['format']}"
                    zipf.write(filepath, arcname)
            
            download_url = f"{settings.API_URL}/exports/{export_filename}"
            
            asyncio.run(self._send_export_notification(
                user_id,
                download_url,
                export_filename
            ))
            
            return {
                "success": True,
                "filename": export_filename,
                "download_url": download_url,
                "size": os.path.getsize(export_path)
            }
            
    except Exception as e:
        logger.error(f"Error exporting model data: {e}")
        return {"success": False, "error": str(e)}
    
    async def _export_model_info(self, model_id: str) -> Dict[str, Any]:
        """Export model information."""
        async with self.db as session:
            model = await session.get(Model, model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            return {
                'id': str(model.id),
                'platform_id': model.platform_id,
                'username': model.username,
                'display_name': model.display_name,
                'platform': model.platform,
                'created_at': model.created_at.isoformat(),
                'stats': {
                    'total_fans': model.total_fans,
                    'total_revenue': float(model.total_revenue) if model.total_revenue else 0,
                    'message_count': model.message_count,
                    'media_count': model.media_count
                }
            }
    
    async def _export_model_fans(self, model_id: str) -> List[Dict[str, Any]]:
        """Export model's fans."""
        # Implement fan export
        return []
    
    async def _export_model_messages(
        self,
        model_id: str,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Export model's messages."""
        async with self.db as session:
            query = select(Message).where(Message.model_id == model_id)
            
            if date_from:
                query = query.where(Message.created_at >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.where(Message.created_at <= datetime.fromisoformat(date_to))
            
            query = query.limit(10000)
            
            result = await session.execute(query)
            messages = result.scalars().all()
            
            return [
                {
                    'id': str(msg.id),
                    'fan_id': str(msg.fan_id),
                    'content': msg.content,
                    'is_from_fan': msg.is_from_fan,
                    'created_at': msg.created_at.isoformat(),
                    'tip_amount': float(msg.tip_amount) if msg.tip_amount else 0
                }
                for msg in messages
            ]
    
    async def _export_model_transactions(
        self,
        model_id: str,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Export model's transactions."""
        async with self.db as session:
            query = select(Transaction).where(Transaction.model_id == model_id)
            
            if date_from:
                query = query.where(Transaction.created_at >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.where(Transaction.created_at <= datetime.fromisoformat(date_to))
            
            result = await session.execute(query)
            transactions = result.scalars().all()
            
            return [
                {
                    'id': str(tx.id),
                    'fan_id': str(tx.fan_id),
                    'type': tx.type,
                    'amount': float(tx.amount),
                    'currency': tx.currency,
                    'status': tx.status,
                    'created_at': tx.created_at.isoformat()
                }
                for tx in transactions
            ]


@shared_task(bind=True, base=ExportTask, name='tasks.export_tasks.generate_financial_report')
def generate_financial_report(
    self,
    agency_id: str,
    user_id: str,
    report_type: str,
    date_from: str,
    date_to: str
):
    """
    Generate financial reports.
    
    Report types:
    - revenue_summary
    - commission_report
    - payout_report
    - tax_report
    """
    try:
        logger.info(f"Generating {report_type} for agency {agency_id}")
        
        if report_type == 'revenue_summary':
            report_data = asyncio.run(self._generate_revenue_summary(
                agency_id, date_from, date_to
            ))
        elif report_type == 'commission_report':
            report_data = asyncio.run(self._generate_commission_report(
                agency_id, date_from, date_to
            ))
        elif report_type == 'payout_report':
            report_data = asyncio.run(self._generate_payout_report(
                agency_id, date_from, date_to
            ))
        elif report_type == 'tax_report':
            report_data = asyncio.run(self._generate_tax_report(
                agency_id, date_from, date_to
            ))
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # Generate PDF report
        report_filename = f"{report_type}_{agency_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        report_path = os.path.join(settings.EXPORT_DIR, report_filename)
        
        # Use reportlab or weasyprint to generate PDF
        # For now, save as JSON
        with open(report_path.replace('.pdf', '.json'), 'w') as f:
            json.dump(report_data, f, indent=2)
        
        download_url = f"{settings.API_URL}/exports/{report_filename}"
        
        asyncio.run(self._send_export_notification(
            user_id,
            download_url,
            report_filename
        ))
        
        return {
            "success": True,
            "filename": report_filename,
            "download_url": download_url
        }
        
    except Exception as e:
        logger.error(f"Error generating financial report: {e}")
        return {"success": False, "error": str(e)}
    
    async def _generate_revenue_summary(
        self,
        agency_id: str,
        date_from: str,
        date_to: str
    ) -> Dict[str, Any]:
        """Generate revenue summary report."""
        async with self.db as session:
            # Aggregate revenue data
            # This is a simplified version
            return {
                'report_type': 'revenue_summary',
                'period': {
                    'from': date_from,
                    'to': date_to
                },
                'total_revenue': 0,
                'revenue_by_model': [],
                'revenue_by_type': {
                    'subscriptions': 0,
                    'tips': 0,
                    'messages': 0,
                    'posts': 0
                },
                'top_performers': []
            }
    
    async def _generate_commission_report(
        self,
        agency_id: str,
        date_from: str,
        date_to: str
    ) -> Dict[str, Any]:
        """Generate commission report."""
        return {
            'report_type': 'commission_report',
            'period': {
                'from': date_from,
                'to': date_to
            },
            'total_commissions': 0,
            'commissions_by_model': []
        }
    
    async def _generate_payout_report(
        self,
        agency_id: str,
        date_from: str,
        date_to: str
    ) -> Dict[str, Any]:
        """Generate payout report."""
        return {
            'report_type': 'payout_report',
            'period': {
                'from': date_from,
                'to': date_to
            },
            'total_payouts': 0,
            'payouts_by_model': []
        }
    
    async def _generate_tax_report(
        self,
        agency_id: str,
        date_from: str,
        date_to: str
    ) -> Dict[str, Any]:
        """Generate tax report."""
        return {
            'report_type': 'tax_report',
            'period': {
                'from': date_from,
                'to': date_to
            },
            'gross_revenue': 0,
            'deductions': 0,
            'net_revenue': 0
        }


@shared_task(name='tasks.export_tasks.cleanup_old_exports')
def cleanup_old_exports():
    """Clean up export files older than 30 days."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        if os.path.exists(settings.EXPORT_DIR):
            for filename in os.listdir(settings.EXPORT_DIR):
                filepath = os.path.join(settings.EXPORT_DIR, filename)
                
                # Check file modification time
                if os.path.getmtime(filepath) < cutoff_date.timestamp():
                    os.remove(filepath)
                    logger.info(f"Deleted old export file: {filename}")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error cleaning up old exports: {e}")
        return {"success": False, "error": str(e)}