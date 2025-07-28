"""
Scheduled report generation service.

Handles automatic report generation and distribution on a schedule.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from core.email.email_service import email_service
from core.redis import redis_client
from modules.reporting.domain.models import (
    ReportSchedule, GeneratedReport, ReportTemplate,
    ReportStatus, DeliveryMethod
)
from modules.reporting.domain.schemas import (
    ReportScheduleCreate, ReportScheduleUpdate,
    ReportGenerateRequest
)
from modules.reporting.application.report_builder_service import ReportBuilderService
from modules.reporting.application.export_service import ExportService

logger = logging.getLogger(__name__)


class ScheduledReportService:
    """Service for managing scheduled report generation."""
    
    def __init__(self):
        self.report_builder = ReportBuilderService()
        self.export_service = ExportService()
        self.cache_prefix = "scheduled_report:"
        self.lock_prefix = "report_lock:"
    
    async def create_report_schedule(
        self,
        data: ReportScheduleCreate,
        agency_id: UUID,
        user_id: UUID,
        db: AsyncSession
    ) -> ReportSchedule:
        """Create a new report schedule."""
        # Validate template exists
        template = await db.get(ReportTemplate, data.template_id)
        if not template or (template.agency_id != agency_id and not template.is_public):
            raise NotFoundError("Report template not found")
        
        # Validate cron expression if provided
        if data.schedule_type == "cron" and data.cron_expression:
            try:
                croniter(data.cron_expression)
            except:
                raise BadRequestError("Invalid cron expression")
        
        # Create schedule
        schedule = ReportSchedule(
            agency_id=agency_id,
            template_id=data.template_id,
            created_by_id=user_id,
            name=data.name,
            description=data.description,
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
            timezone=data.timezone,
            parameters=data.parameters.dict() if data.parameters else {},
            delivery_method=data.delivery_method,
            delivery_config=data.delivery_config,
            is_active=data.is_active
        )
        
        # Calculate next run time
        schedule.next_run_at = self._calculate_next_run(schedule)
        
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        
        logger.info(f"Created report schedule '{schedule.name}' for agency {agency_id}")
        return schedule
    
    async def update_report_schedule(
        self,
        schedule_id: UUID,
        data: ReportScheduleUpdate,
        agency_id: UUID,
        db: AsyncSession
    ) -> ReportSchedule:
        """Update a report schedule."""
        # Get schedule
        result = await db.execute(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id,
                ReportSchedule.agency_id == agency_id
            )
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise NotFoundError("Report schedule not found")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        
        # Validate cron expression if updated
        if "cron_expression" in update_data:
            try:
                croniter(update_data["cron_expression"])
            except:
                raise BadRequestError("Invalid cron expression")
        
        for field, value in update_data.items():
            setattr(schedule, field, value)
        
        # Recalculate next run time if schedule changed
        if any(field in update_data for field in ["schedule_type", "cron_expression", "is_active"]):
            schedule.next_run_at = self._calculate_next_run(schedule) if schedule.is_active else None
        
        await db.commit()
        await db.refresh(schedule)
        
        return schedule
    
    async def delete_report_schedule(
        self,
        schedule_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> bool:
        """Delete a report schedule."""
        result = await db.execute(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id,
                ReportSchedule.agency_id == agency_id
            )
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise NotFoundError("Report schedule not found")
        
        await db.delete(schedule)
        await db.commit()
        
        logger.info(f"Deleted report schedule '{schedule.name}'")
        return True
    
    async def process_scheduled_reports(self, db: AsyncSession):
        """Process all due scheduled reports."""
        # Get lock to prevent concurrent processing
        lock_key = f"{self.lock_prefix}process"
        lock_acquired = await redis_client.set(lock_key, "1", nx=True, ex=300)
        
        if not lock_acquired:
            logger.debug("Scheduled report processing already running")
            return
        
        try:
            # Get due schedules
            now = datetime.utcnow()
            result = await db.execute(
                select(ReportSchedule).where(
                    ReportSchedule.is_active == True,
                    ReportSchedule.next_run_at <= now
                ).limit(10)  # Process in batches
            )
            schedules = result.scalars().all()
            
            logger.info(f"Processing {len(schedules)} scheduled reports")
            
            # Process each schedule
            for schedule in schedules:
                await self._process_single_schedule(schedule, db)
            
        finally:
            # Release lock
            await redis_client.delete(lock_key)
    
    async def _process_single_schedule(
        self,
        schedule: ReportSchedule,
        db: AsyncSession
    ):
        """Process a single scheduled report."""
        try:
            logger.info(f"Processing scheduled report '{schedule.name}'")
            
            # Update last run time
            schedule.last_run_at = datetime.utcnow()
            
            # Generate report
            request = ReportGenerateRequest(**schedule.parameters)
            
            generated_report = await self.report_builder.generate_report(
                template_id=schedule.template_id,
                request=request,
                agency_id=schedule.agency_id,
                user_id=schedule.created_by_id,
                db=db
            )
            
            # Deliver report
            if generated_report.status == ReportStatus.COMPLETED:
                await self._deliver_report(schedule, generated_report, db)
                schedule.success_count += 1
            else:
                schedule.failure_count += 1
                logger.error(f"Failed to generate report for schedule {schedule.id}")
            
            # Calculate next run time
            schedule.next_run_at = self._calculate_next_run(schedule)
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error processing scheduled report {schedule.id}: {e}")
            schedule.failure_count += 1
            schedule.last_error = str(e)
            schedule.next_run_at = self._calculate_next_run(schedule)
            await db.commit()
    
    async def _deliver_report(
        self,
        schedule: ReportSchedule,
        report: GeneratedReport,
        db: AsyncSession
    ):
        """Deliver generated report based on delivery method."""
        if schedule.delivery_method == DeliveryMethod.EMAIL:
            await self._deliver_via_email(schedule, report, db)
        elif schedule.delivery_method == DeliveryMethod.WEBHOOK:
            await self._deliver_via_webhook(schedule, report)
        elif schedule.delivery_method == DeliveryMethod.S3:
            await self._deliver_to_s3(schedule, report)
        elif schedule.delivery_method == DeliveryMethod.SFTP:
            await self._deliver_via_sftp(schedule, report)
    
    async def _deliver_via_email(
        self,
        schedule: ReportSchedule,
        report: GeneratedReport,
        db: AsyncSession
    ):
        """Deliver report via email."""
        config = schedule.delivery_config
        recipients = config.get("recipients", [])
        
        if not recipients:
            logger.warning(f"No email recipients configured for schedule {schedule.id}")
            return
        
        # Get template info
        template = await db.get(ReportTemplate, schedule.template_id)
        
        # Export report as PDF
        export_data = {
            "metadata": report.parameters,
            **report.report_data
        }
        
        pdf_file = self.export_service._export_pdf(export_data, template.report_type)
        
        # Send email
        subject = f"{template.name} - {datetime.utcnow().strftime('%Y-%m-%d')}"
        body = f"""
        Your scheduled report '{template.name}' has been generated.
        
        Report Period: {report.parameters.get('date_from', 'N/A')} to {report.parameters.get('date_to', 'N/A')}
        Generated At: {report.created_at}
        
        Please find the report attached.
        """
        
        for recipient in recipients:
            # In production, implement actual email sending with attachment
            logger.info(f"Would send report to {recipient}")
    
    async def _deliver_via_webhook(
        self,
        schedule: ReportSchedule,
        report: GeneratedReport
    ):
        """Deliver report via webhook."""
        config = schedule.delivery_config
        webhook_url = config.get("webhook_url")
        
        if not webhook_url:
            logger.warning(f"No webhook URL configured for schedule {schedule.id}")
            return
        
        # Send webhook
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "schedule_id": str(schedule.id),
                "report_id": str(report.id),
                "template_name": schedule.name,
                "generated_at": report.created_at.isoformat(),
                "report_data": report.report_data
            }
            
            headers = config.get("headers", {})
            
            try:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        logger.error(f"Webhook delivery failed: {response.status}")
            except Exception as e:
                logger.error(f"Webhook delivery error: {e}")
    
    async def _deliver_to_s3(
        self,
        schedule: ReportSchedule,
        report: GeneratedReport
    ):
        """Deliver report to S3."""
        # This would integrate with AWS S3
        logger.info(f"S3 delivery not implemented for schedule {schedule.id}")
    
    async def _deliver_via_sftp(
        self,
        schedule: ReportSchedule,
        report: GeneratedReport
    ):
        """Deliver report via SFTP."""
        # This would integrate with SFTP
        logger.info(f"SFTP delivery not implemented for schedule {schedule.id}")
    
    def _calculate_next_run(self, schedule: ReportSchedule) -> Optional[datetime]:
        """Calculate next run time for a schedule."""
        if not schedule.is_active:
            return None
        
        base_time = schedule.last_run_at or datetime.utcnow()
        
        if schedule.schedule_type == "daily":
            return base_time + timedelta(days=1)
        elif schedule.schedule_type == "weekly":
            return base_time + timedelta(weeks=1)
        elif schedule.schedule_type == "monthly":
            # Add one month (approximation)
            next_month = base_time.month + 1
            year = base_time.year
            if next_month > 12:
                next_month = 1
                year += 1
            try:
                return base_time.replace(month=next_month, year=year)
            except ValueError:
                # Handle end of month cases
                return base_time.replace(month=next_month, year=year, day=1)
        elif schedule.schedule_type == "cron" and schedule.cron_expression:
            cron = croniter(schedule.cron_expression, base_time)
            return cron.get_next(datetime)
        
        return None
    
    async def get_report_schedules(
        self,
        agency_id: UUID,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[ReportSchedule]:
        """Get report schedules for an agency."""
        query = select(ReportSchedule).where(
            ReportSchedule.agency_id == agency_id
        )
        
        if is_active is not None:
            query = query.where(ReportSchedule.is_active == is_active)
        
        query = query.order_by(ReportSchedule.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def run_schedule_now(
        self,
        schedule_id: UUID,
        agency_id: UUID,
        db: AsyncSession
    ) -> GeneratedReport:
        """Run a scheduled report immediately."""
        # Get schedule
        result = await db.execute(
            select(ReportSchedule).where(
                ReportSchedule.id == schedule_id,
                ReportSchedule.agency_id == agency_id
            )
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise NotFoundError("Report schedule not found")
        
        # Generate report
        request = ReportGenerateRequest(**schedule.parameters)
        
        generated_report = await self.report_builder.generate_report(
            template_id=schedule.template_id,
            request=request,
            agency_id=schedule.agency_id,
            user_id=schedule.created_by_id,
            db=db
        )
        
        # Deliver if successful
        if generated_report.status == ReportStatus.COMPLETED:
            await self._deliver_report(schedule, generated_report, db)
        
        return generated_report