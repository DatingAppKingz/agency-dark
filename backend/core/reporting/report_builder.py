"""
Report builder service for creating and executing custom reports.
"""
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_, func
from sqlalchemy.orm import selectinload
import pandas as pd
from io import BytesIO
import logging

from core.redis import redis_client
from core.database import get_db
from core.reporting.models import (
    Report, ReportExecution, ReportSchedule, ReportTemplate,
    ReportWidget, ReportCache, ReportAuditLog,
    ReportType, ReportFormat, ReportStatus
)
from core.domain.models import User, Agency
from core.cache import cache_service

logger = logging.getLogger(__name__)


class ReportBuilder:
    """Main report builder service."""
    
    def __init__(self):
        self.redis = redis_client
        self._query_templates = self._load_query_templates()
        self._formatters = {
            ReportFormat.CSV: self._format_csv,
            ReportFormat.EXCEL: self._format_excel,
            ReportFormat.JSON: self._format_json,
            ReportFormat.PDF: self._format_pdf,
            ReportFormat.HTML: self._format_html
        }
    
    async def create_report(
        self,
        name: str,
        report_type: ReportType,
        query_config: Dict[str, Any],
        user: User,
        session: AsyncSession,
        description: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        grouping: Optional[List[str]] = None,
        sorting: Optional[Dict[str, str]] = None,
        aggregations: Optional[Dict[str, Any]] = None,
        chart_config: Optional[Dict[str, Any]] = None
    ) -> Report:
        """Create a new report definition."""
        # Validate query configuration
        self._validate_query_config(query_config, report_type)
        
        # Create report
        report = Report(
            name=name,
            description=description,
            report_type=report_type,
            query_config=query_config,
            filters=filters or {},
            columns=columns,
            grouping=grouping,
            sorting=sorting,
            aggregations=aggregations,
            chart_config=chart_config,
            created_by_id=user.id,
            agency_id=user.agency_id
        )
        
        session.add(report)
        await session.commit()
        
        # Log creation
        await self._log_action(
            report.id,
            "created",
            user.id,
            {"report_type": report_type.value},
            session
        )
        
        return report
    
    async def execute_report(
        self,
        report_id: str,
        format: ReportFormat,
        user: User,
        session: AsyncSession,
        parameters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> ReportExecution:
        """Execute a report and generate output."""
        # Get report
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Check permissions
        if not await self._can_access_report(report, user, session):
            raise PermissionError("Access denied to this report")
        
        # Check cache
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(report, parameters, format)
            cached = await self._get_cached_result(cache_key, session)
            if cached:
                return cached
        
        # Create execution record
        execution = ReportExecution(
            report_id=report.id,
            format=format,
            parameters=parameters,
            status=ReportStatus.GENERATING,
            executed_by_id=user.id,
            started_at=datetime.utcnow(),
            cache_key=cache_key
        )
        session.add(execution)
        await session.commit()
        
        try:
            # Execute report
            await self._execute_report_async(
                report,
                execution,
                format,
                parameters,
                session
            )
            
            # Update report metadata
            report.last_run_at = datetime.utcnow()
            report.run_count += 1
            await session.commit()
            
            # Log execution
            await self._log_action(
                report.id,
                "executed",
                user.id,
                {"format": format.value, "execution_id": str(execution.id)},
                session
            )
            
        except Exception as e:
            logger.error(f"Error executing report {report_id}: {e}")
            execution.status = ReportStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await session.commit()
        
        return execution
    
    async def create_from_template(
        self,
        template_id: str,
        name: str,
        user: User,
        session: AsyncSession,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Report:
        """Create a report from a template."""
        # Get template
        result = await session.execute(
            select(ReportTemplate).where(ReportTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Apply customizations
        query_config = json.loads(json.dumps(template.base_query))  # Deep copy
        filters = template.default_filters.copy() if template.default_filters else {}
        columns = template.default_columns.copy() if template.default_columns else None
        
        if customizations:
            # Validate customizations against template rules
            self._validate_customizations(customizations, template.customizable_fields)
            
            # Apply customizations
            if "filters" in customizations:
                filters.update(customizations["filters"])
            if "columns" in customizations:
                columns = customizations["columns"]
        
        # Create report
        report = await self.create_report(
            name=name,
            report_type=template.report_type,
            query_config=query_config,
            user=user,
            session=session,
            description=f"Created from template: {template.name}",
            filters=filters,
            columns=columns,
            grouping=template.default_grouping,
            sorting=template.default_sorting,
            aggregations=template.default_aggregations,
            chart_config=template.default_chart_config
        )
        
        # Update template usage
        template.usage_count += 1
        await session.commit()
        
        return report
    
    async def share_report(
        self,
        report_id: str,
        user_ids: List[str],
        permission: str,
        shared_by: User,
        session: AsyncSession
    ) -> bool:
        """Share a report with other users."""
        # Get report
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            return False
        
        # Check permissions
        if report.created_by_id != shared_by.id and shared_by.role != "super_admin":
            raise PermissionError("Only report owner can share")
        
        # Get users to share with
        result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = result.scalars().all()
        
        # Share report
        for user in users:
            if user not in report.shared_with:
                report.shared_with.append(user)
        
        await session.commit()
        
        # Log sharing
        await self._log_action(
            report.id,
            "shared",
            shared_by.id,
            {"shared_with": user_ids, "permission": permission},
            session
        )
        
        return True
    
    async def schedule_report(
        self,
        report_id: str,
        cron_expression: str,
        format: ReportFormat,
        delivery_config: Dict[str, Any],
        user: User,
        session: AsyncSession,
        parameters: Optional[Dict[str, Any]] = None,
        recipient_users: Optional[List[str]] = None,
        recipient_emails: Optional[List[str]] = None
    ) -> ReportSchedule:
        """Schedule a report for periodic generation."""
        # Get report
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Create schedule
        schedule = ReportSchedule(
            report_id=report.id,
            cron_expression=cron_expression,
            format=format,
            delivery_config=delivery_config,
            parameters=parameters,
            recipient_users=recipient_users,
            recipient_emails=recipient_emails,
            created_by_id=user.id
        )
        
        # Calculate next run time
        # TODO: Implement cron parsing
        schedule.next_run_at = datetime.utcnow() + timedelta(days=1)
        
        session.add(schedule)
        await session.commit()
        
        return schedule
    
    async def get_report_data(
        self,
        report: Report,
        session: AsyncSession,
        parameters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Get report data as DataFrame."""
        # Build query
        query = self._build_query(report, parameters)
        
        # Execute query
        start_time = datetime.utcnow()
        result = await session.execute(text(query))
        rows = result.fetchall()
        query_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Convert to DataFrame
        if rows:
            df = pd.DataFrame(rows, columns=result.keys())
        else:
            df = pd.DataFrame()
        
        # Apply post-processing
        df = self._apply_post_processing(df, report)
        
        return df
    
    def _build_query(
        self,
        report: Report,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build SQL query from report configuration."""
        query_config = report.query_config
        
        # Get base query
        if report.report_type in self._query_templates:
            base_query = self._query_templates[report.report_type]
        else:
            base_query = query_config.get("custom_query", "")
        
        # Apply filters
        filters = report.filters.copy()
        if parameters and "filters" in parameters:
            filters.update(parameters["filters"])
        
        where_clauses = []
        for field, condition in filters.items():
            where_clauses.append(self._build_where_clause(field, condition))
        
        if where_clauses:
            if "WHERE" in base_query.upper():
                base_query += f" AND {' AND '.join(where_clauses)}"
            else:
                base_query += f" WHERE {' AND '.join(where_clauses)}"
        
        # Apply grouping
        if report.grouping:
            base_query += f" GROUP BY {', '.join(report.grouping)}"
        
        # Apply sorting
        if report.sorting:
            order_clauses = []
            for field, direction in report.sorting.items():
                order_clauses.append(f"{field} {direction.upper()}")
            base_query += f" ORDER BY {', '.join(order_clauses)}"
        
        # Apply limit
        limit = query_config.get("limit", 10000)
        base_query += f" LIMIT {limit}"
        
        return base_query
    
    def _build_where_clause(self, field: str, condition: Dict[str, Any]) -> str:
        """Build WHERE clause for a field."""
        operator = condition.get("operator", "=")
        value = condition.get("value")
        
        if operator == "in":
            values = ", ".join([f"'{v}'" for v in value])
            return f"{field} IN ({values})"
        elif operator == "between":
            return f"{field} BETWEEN '{value[0]}' AND '{value[1]}'"
        elif operator == "like":
            return f"{field} LIKE '%{value}%'"
        elif operator == "is_null":
            return f"{field} IS NULL"
        elif operator == "is_not_null":
            return f"{field} IS NOT NULL"
        else:
            return f"{field} {operator} '{value}'"
    
    def _apply_post_processing(
        self,
        df: pd.DataFrame,
        report: Report
    ) -> pd.DataFrame:
        """Apply post-processing to DataFrame."""
        # Apply column selection
        if report.columns and df.shape[0] > 0:
            available_cols = [col for col in report.columns if col in df.columns]
            df = df[available_cols]
        
        # Apply aggregations
        if report.aggregations and df.shape[0] > 0:
            for col, agg_func in report.aggregations.items():
                if col in df.columns:
                    if agg_func == "sum":
                        df[f"{col}_sum"] = df[col].sum()
                    elif agg_func == "avg":
                        df[f"{col}_avg"] = df[col].mean()
                    elif agg_func == "count":
                        df[f"{col}_count"] = df[col].count()
        
        return df
    
    async def _format_csv(
        self,
        df: pd.DataFrame,
        report: Report,
        execution: ReportExecution
    ) -> str:
        """Format data as CSV."""
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        
        # Save to file
        file_path = f"reports/{execution.id}.csv"
        # TODO: Save to actual file storage
        
        execution.file_path = file_path
        execution.file_size_bytes = buffer.tell()
        
        return file_path
    
    async def _format_excel(
        self,
        df: pd.DataFrame,
        report: Report,
        execution: ReportExecution
    ) -> str:
        """Format data as Excel."""
        buffer = BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
            
            # Add formatting
            worksheet = writer.sheets['Data']
            # TODO: Add Excel formatting
        
        # Save to file
        file_path = f"reports/{execution.id}.xlsx"
        # TODO: Save to actual file storage
        
        execution.file_path = file_path
        execution.file_size_bytes = buffer.tell()
        
        return file_path
    
    async def _format_json(
        self,
        df: pd.DataFrame,
        report: Report,
        execution: ReportExecution
    ) -> str:
        """Format data as JSON."""
        data = df.to_dict(orient='records')
        execution.preview_data = data[:100]  # Store preview
        
        # Save to file
        file_path = f"reports/{execution.id}.json"
        # TODO: Save to actual file storage
        
        execution.file_path = file_path
        
        return file_path
    
    async def _format_pdf(
        self,
        df: pd.DataFrame,
        report: Report,
        execution: ReportExecution
    ) -> str:
        """Format data as PDF."""
        # TODO: Implement PDF generation
        file_path = f"reports/{execution.id}.pdf"
        execution.file_path = file_path
        return file_path
    
    async def _format_html(
        self,
        df: pd.DataFrame,
        report: Report,
        execution: ReportExecution
    ) -> str:
        """Format data as HTML."""
        html = df.to_html(index=False, classes=['table', 'table-striped'])
        
        # Add styling and charts
        if report.chart_config:
            # TODO: Add chart rendering
            pass
        
        # Save to file
        file_path = f"reports/{execution.id}.html"
        # TODO: Save to actual file storage
        
        execution.file_path = file_path
        
        return file_path
    
    async def _execute_report_async(
        self,
        report: Report,
        execution: ReportExecution,
        format: ReportFormat,
        parameters: Optional[Dict[str, Any]],
        session: AsyncSession
    ):
        """Execute report asynchronously."""
        try:
            # Get data
            df = await self.get_report_data(report, parameters, session)
            execution.row_count = len(df)
            
            # Format output
            formatter = self._formatters.get(format)
            if formatter:
                await formatter(df, report, execution)
            
            # Update execution
            execution.status = ReportStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
            
            # Cache result if configured
            if report.cache_duration_minutes > 0:
                await self._cache_result(execution, df, session)
            
        except Exception as e:
            logger.error(f"Error in async report execution: {e}")
            execution.status = ReportStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
        
        finally:
            await session.commit()
    
    async def _can_access_report(
        self,
        report: Report,
        user: User,
        session: AsyncSession
    ) -> bool:
        """Check if user can access report."""
        # Owner always has access
        if report.created_by_id == user.id:
            return True
        
        # Super admin has access
        if user.role == "super_admin":
            return True
        
        # Same agency has access
        if report.agency_id == user.agency_id:
            return True
        
        # Check if shared
        if user in report.shared_with:
            return True
        
        # Public reports
        if report.is_public:
            return True
        
        return False
    
    def _generate_cache_key(
        self,
        report: Report,
        parameters: Optional[Dict[str, Any]],
        format: ReportFormat
    ) -> str:
        """Generate cache key for report."""
        key_parts = [
            str(report.id),
            format.value,
            json.dumps(parameters or {}, sort_keys=True)
        ]
        
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def _get_cached_result(
        self,
        cache_key: str,
        session: AsyncSession
    ) -> Optional[ReportExecution]:
        """Get cached report result."""
        result = await session.execute(
            select(ReportCache)
            .where(
                and_(
                    ReportCache.cache_key == cache_key,
                    ReportCache.expires_at > datetime.utcnow()
                )
            )
        )
        cache = result.scalar_one_or_none()
        
        if cache:
            # Update hit count
            cache.hit_count += 1
            cache.last_accessed_at = datetime.utcnow()
            await session.commit()
            
            # Return cached execution
            # TODO: Reconstruct execution from cache
            return None
        
        return None
    
    async def _cache_result(
        self,
        execution: ReportExecution,
        data: pd.DataFrame,
        session: AsyncSession
    ):
        """Cache report result."""
        if not execution.cache_key:
            return
        
        cache = ReportCache(
            cache_key=execution.cache_key,
            report_id=execution.report_id,
            data_type="file" if execution.file_path else "data",
            file_path=execution.file_path,
            data=data.to_dict(orient='records')[:1000] if len(data) < 1000 else None,
            expires_at=datetime.utcnow() + timedelta(minutes=60),
            parameters=execution.parameters,
            filters=execution.filters_applied,
            size_bytes=execution.file_size_bytes
        )
        
        session.add(cache)
        await session.commit()
    
    async def _log_action(
        self,
        report_id: str,
        action: str,
        user_id: str,
        details: Dict[str, Any],
        session: AsyncSession
    ):
        """Log report action."""
        log = ReportAuditLog(
            report_id=report_id,
            action=action,
            user_id=user_id,
            action_details=details
        )
        
        session.add(log)
        await session.commit()
    
    def _validate_query_config(
        self,
        query_config: Dict[str, Any],
        report_type: ReportType
    ):
        """Validate query configuration."""
        # TODO: Implement validation based on report type
        pass
    
    def _validate_customizations(
        self,
        customizations: Dict[str, Any],
        allowed_fields: Optional[List[str]]
    ):
        """Validate template customizations."""
        if not allowed_fields:
            return
        
        for field in customizations:
            if field not in allowed_fields:
                raise ValueError(f"Field {field} is not customizable")
    
    def _load_query_templates(self) -> Dict[ReportType, str]:
        """Load SQL query templates for standard reports."""
        return {
            ReportType.REVENUE: """
                SELECT 
                    DATE_TRUNC('day', created_at) as date,
                    SUM(amount) as revenue,
                    COUNT(*) as transaction_count,
                    AVG(amount) as avg_transaction
                FROM transactions
                WHERE status = 'completed'
            """,
            ReportType.USER_ACTIVITY: """
                SELECT 
                    u.id,
                    u.email,
                    u.created_at,
                    COUNT(DISTINCT t.id) as transaction_count,
                    SUM(t.amount) as total_spent,
                    MAX(t.created_at) as last_transaction
                FROM users u
                LEFT JOIN transactions t ON u.id = t.user_id
            """,
            ReportType.MODEL_PERFORMANCE: """
                SELECT 
                    m.id,
                    m.stage_name,
                    COUNT(DISTINCT t.id) as transaction_count,
                    SUM(t.amount) as total_revenue,
                    AVG(t.amount) as avg_transaction,
                    COUNT(DISTINCT t.user_id) as unique_customers
                FROM models m
                LEFT JOIN transactions t ON m.id = t.model_id
            """
        }


# Singleton instance
report_builder = ReportBuilder()