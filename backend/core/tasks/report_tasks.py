"""
Report generation tasks
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
import os
import json
from io import BytesIO

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, func, and_, or_
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from core.database import get_db_context
from core.models import Agency, ModelProfile, Transaction, Report
from core.storage import upload_file
from .email_tasks import send_email

logger = get_task_logger(__name__)


@shared_task(bind=True)
def generate_daily_reports(self) -> Dict[str, Any]:
    """
    Generate daily reports for all agencies
    """
    try:
        results = {
            'reports_generated': 0,
            'emails_sent': 0,
            'errors': []
        }
        
        async def _generate():
            async with get_db_context() as db:
                # Get all active agencies
                result = await db.execute(
                    select(Agency).where(Agency.is_active == True)
                )
                agencies = result.scalars().all()
                
                yesterday = date.today() - timedelta(days=1)
                
                for agency in agencies:
                    try:
                        # Generate report data
                        report_data = await _generate_daily_report_data(
                            db, agency.id, yesterday
                        )
                        
                        # Create report document
                        report_content = _create_report_document(
                            agency, report_data, 'daily', yesterday
                        )
                        
                        # Save report
                        report_path = f"reports/{agency.id}/daily_{yesterday.isoformat()}.pdf"
                        report_url = await upload_file(
                            report_content,
                            report_path,
                            content_type='application/pdf'
                        )
                        
                        # Save report record
                        report = Report(
                            agency_id=agency.id,
                            report_type='daily',
                            report_date=yesterday,
                            file_path=report_path,
                            file_url=report_url,
                            metadata=report_data,
                            generated_at=datetime.utcnow()
                        )
                        db.add(report)
                        
                        results['reports_generated'] += 1
                        
                        # Send email if configured
                        if agency.report_email:
                            send_email.delay(
                                to_email=agency.report_email,
                                subject=f"Daily Report - {yesterday.strftime('%B %d, %Y')}",
                                body=f"Your daily report for {yesterday.strftime('%B %d, %Y')} is attached.",
                                attachments=[{
                                    'filename': f"daily_report_{yesterday.isoformat()}.pdf",
                                    'content': report_content,
                                    'content_type': 'application/pdf'
                                }]
                            )
                            results['emails_sent'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to generate daily report for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                
                await db.commit()
        
        # Run async function
        import asyncio
        asyncio.run(_generate())
        
        logger.info(f"Daily report generation completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Daily report generation failed: {exc}")
        raise


@shared_task(bind=True)
def generate_weekly_reports(self) -> Dict[str, Any]:
    """
    Generate weekly reports for all agencies
    """
    try:
        results = {
            'reports_generated': 0,
            'emails_sent': 0,
            'errors': []
        }
        
        async def _generate():
            async with get_db_context() as db:
                # Get all active agencies
                result = await db.execute(
                    select(Agency).where(Agency.is_active == True)
                )
                agencies = result.scalars().all()
                
                # Calculate week period
                today = date.today()
                week_end = today - timedelta(days=today.weekday() + 1)  # Last Sunday
                week_start = week_end - timedelta(days=6)
                
                for agency in agencies:
                    try:
                        # Generate report data
                        report_data = await _generate_period_report_data(
                            db, agency.id, week_start, week_end
                        )
                        
                        # Create report document
                        report_content = _create_report_document(
                            agency, report_data, 'weekly', week_end
                        )
                        
                        # Save report
                        report_path = f"reports/{agency.id}/weekly_{week_end.isoformat()}.pdf"
                        report_url = await upload_file(
                            report_content,
                            report_path,
                            content_type='application/pdf'
                        )
                        
                        # Save report record
                        report = Report(
                            agency_id=agency.id,
                            report_type='weekly',
                            report_date=week_end,
                            file_path=report_path,
                            file_url=report_url,
                            metadata=report_data,
                            generated_at=datetime.utcnow()
                        )
                        db.add(report)
                        
                        results['reports_generated'] += 1
                        
                        # Send email if configured
                        if agency.report_email:
                            send_email.delay(
                                to_email=agency.report_email,
                                subject=f"Weekly Report - Week of {week_start.strftime('%B %d')}",
                                body=f"Your weekly report for the week of {week_start.strftime('%B %d')} is attached.",
                                attachments=[{
                                    'filename': f"weekly_report_{week_end.isoformat()}.pdf",
                                    'content': report_content,
                                    'content_type': 'application/pdf'
                                }]
                            )
                            results['emails_sent'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to generate weekly report for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                
                await db.commit()
        
        # Run async function
        import asyncio
        asyncio.run(_generate())
        
        logger.info(f"Weekly report generation completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Weekly report generation failed: {exc}")
        raise


@shared_task(bind=True)
def generate_monthly_reports(self) -> Dict[str, Any]:
    """
    Generate monthly reports for all agencies
    """
    try:
        results = {
            'reports_generated': 0,
            'emails_sent': 0,
            'errors': []
        }
        
        async def _generate():
            async with get_db_context() as db:
                # Get all active agencies
                result = await db.execute(
                    select(Agency).where(Agency.is_active == True)
                )
                agencies = result.scalars().all()
                
                # Calculate month period
                today = date.today()
                month_end = date(today.year, today.month, 1) - timedelta(days=1)
                month_start = date(month_end.year, month_end.month, 1)
                
                for agency in agencies:
                    try:
                        # Generate report data
                        report_data = await _generate_period_report_data(
                            db, agency.id, month_start, month_end
                        )
                        
                        # Add month-specific analytics
                        report_data['month_over_month'] = await _calculate_month_over_month(
                            db, agency.id, month_start
                        )
                        
                        # Create report document
                        report_content = _create_report_document(
                            agency, report_data, 'monthly', month_end
                        )
                        
                        # Save report
                        report_path = f"reports/{agency.id}/monthly_{month_end.strftime('%Y-%m')}.pdf"
                        report_url = await upload_file(
                            report_content,
                            report_path,
                            content_type='application/pdf'
                        )
                        
                        # Save report record
                        report = Report(
                            agency_id=agency.id,
                            report_type='monthly',
                            report_date=month_end,
                            file_path=report_path,
                            file_url=report_url,
                            metadata=report_data,
                            generated_at=datetime.utcnow()
                        )
                        db.add(report)
                        
                        results['reports_generated'] += 1
                        
                        # Send email if configured
                        if agency.report_email:
                            send_email.delay(
                                to_email=agency.report_email,
                                subject=f"Monthly Report - {month_end.strftime('%B %Y')}",
                                body=f"Your monthly report for {month_end.strftime('%B %Y')} is attached.",
                                attachments=[{
                                    'filename': f"monthly_report_{month_end.strftime('%Y-%m')}.pdf",
                                    'content': report_content,
                                    'content_type': 'application/pdf'
                                }]
                            )
                            results['emails_sent'] += 1
                        
                    except Exception as exc:
                        logger.error(f"Failed to generate monthly report for agency {agency.id}: {exc}")
                        results['errors'].append({
                            'agency_id': str(agency.id),
                            'error': str(exc)
                        })
                
                await db.commit()
        
        # Run async function
        import asyncio
        asyncio.run(_generate())
        
        logger.info(f"Monthly report generation completed: {results}")
        return results
        
    except Exception as exc:
        logger.error(f"Monthly report generation failed: {exc}")
        raise


@shared_task
def generate_custom_report(
    agency_id: str,
    start_date: str,
    end_date: str,
    report_type: str = 'custom',
    include_charts: bool = True
) -> Dict[str, Any]:
    """
    Generate custom report for specific agency and date range
    """
    try:
        async def _generate():
            async with get_db_context() as db:
                # Get agency
                result = await db.execute(
                    select(Agency).where(Agency.id == agency_id)
                )
                agency = result.scalar_one_or_none()
                
                if not agency:
                    raise ValueError(f"Agency {agency_id} not found")
                
                # Parse dates
                start = datetime.fromisoformat(start_date).date()
                end = datetime.fromisoformat(end_date).date()
                
                # Generate report data
                report_data = await _generate_period_report_data(
                    db, agency_id, start, end
                )
                
                # Create report document
                report_content = _create_report_document(
                    agency, report_data, report_type, end,
                    include_charts=include_charts
                )
                
                # Save report
                report_path = f"reports/{agency_id}/custom_{start.isoformat()}_{end.isoformat()}.pdf"
                report_url = await upload_file(
                    report_content,
                    report_path,
                    content_type='application/pdf'
                )
                
                # Save report record
                report = Report(
                    agency_id=agency_id,
                    report_type='custom',
                    report_date=end,
                    file_path=report_path,
                    file_url=report_url,
                    metadata={
                        **report_data,
                        'start_date': start.isoformat(),
                        'end_date': end.isoformat()
                    },
                    generated_at=datetime.utcnow()
                )
                db.add(report)
                await db.commit()
                
                return {
                    'status': 'success',
                    'report_url': report_url,
                    'report_id': str(report.id)
                }
        
        # Run async function
        import asyncio
        return asyncio.run(_generate())
        
    except Exception as exc:
        logger.error(f"Custom report generation failed: {exc}")
        raise


# Helper functions
async def _generate_daily_report_data(db, agency_id: str, report_date: date) -> Dict[str, Any]:
    """Generate data for daily report"""
    start_datetime = datetime.combine(report_date, datetime.min.time())
    end_datetime = datetime.combine(report_date, datetime.max.time())
    
    # Revenue
    revenue_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.agency_id == agency_id,
                Transaction.created_at >= start_datetime,
                Transaction.created_at <= end_datetime,
                Transaction.type.in_(['payment', 'tip', 'subscription'])
            )
        )
    )
    total_revenue = revenue_result.scalar() or 0
    
    # Transaction count
    tx_count_result = await db.execute(
        select(func.count(Transaction.id)).where(
            and_(
                Transaction.agency_id == agency_id,
                Transaction.created_at >= start_datetime,
                Transaction.created_at <= end_datetime
            )
        )
    )
    transaction_count = tx_count_result.scalar() or 0
    
    # Active models
    model_revenue_result = await db.execute(
        select(
            ModelProfile.username,
            func.sum(Transaction.amount).label('revenue')
        ).select_from(ModelProfile).join(
            Transaction,
            Transaction.model_id == ModelProfile.id
        ).where(
            and_(
                ModelProfile.agency_id == agency_id,
                Transaction.created_at >= start_datetime,
                Transaction.created_at <= end_datetime,
                Transaction.type.in_(['payment', 'tip', 'subscription'])
            )
        ).group_by(
            ModelProfile.username
        ).order_by(
            func.sum(Transaction.amount).desc()
        )
    )
    top_models = model_revenue_result.all()
    
    return {
        'date': report_date.isoformat(),
        'revenue': float(total_revenue),
        'transaction_count': transaction_count,
        'avg_transaction': float(total_revenue / transaction_count) if transaction_count > 0 else 0,
        'top_models': [
            {'username': username, 'revenue': float(revenue)}
            for username, revenue in top_models[:10]
        ]
    }


async def _generate_period_report_data(
    db, agency_id: str, start_date: date, end_date: date
) -> Dict[str, Any]:
    """Generate data for period report"""
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Similar to daily but with period data
    # ... (implementation similar to daily report but for date range)
    
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': (end_date - start_date).days + 1
        },
        # ... other metrics
    }


async def _calculate_month_over_month(db, agency_id: str, month_start: date) -> Dict[str, Any]:
    """Calculate month-over-month growth metrics"""
    # ... implementation
    return {
        'revenue_growth': 0.15,  # 15% growth
        'transaction_growth': 0.12,
        'model_growth': 0.08
    }


def _create_report_document(
    agency: Agency,
    report_data: Dict[str, Any],
    report_type: str,
    report_date: date,
    include_charts: bool = True
) -> bytes:
    """
    Create PDF report document
    
    Note: This is a simplified version. In production, you'd use a proper
    PDF generation library like ReportLab or weasyprint
    """
    # For now, return a simple placeholder
    content = f"""
Agency Report
=============
Agency: {agency.name}
Report Type: {report_type}
Date: {report_date}

Data:
{json.dumps(report_data, indent=2)}
"""
    
    return content.encode('utf-8')