"""Cron expression parser and scheduler service."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from croniter import croniter
import pytz

from core.logger import get_logger

logger = get_logger(__name__)


class CronParser:
    """Service for parsing and validating cron expressions."""
    
    # Predefined schedules
    PREDEFINED_SCHEDULES = {
        'hourly': '0 * * * *',
        'daily': '0 8 * * *',
        'daily_midnight': '0 0 * * *',
        'weekly': '0 8 * * 1',  # Monday at 8 AM
        'monthly': '0 8 1 * *',  # First day of month at 8 AM
        'quarterly': '0 8 1 */3 *',  # First day of quarter at 8 AM
        'yearly': '0 8 1 1 *',  # January 1st at 8 AM
        'business_days': '0 8 * * 1-5',  # Monday-Friday at 8 AM
        'weekends': '0 10 * * 0,6',  # Saturday-Sunday at 10 AM
        'twice_daily': '0 8,20 * * *',  # 8 AM and 8 PM
        'every_6_hours': '0 */6 * * *',  # Every 6 hours
        'every_30_minutes': '*/30 * * * *',  # Every 30 minutes
        'every_15_minutes': '*/15 * * * *',  # Every 15 minutes
    }
    
    # Human-readable descriptions
    SCHEDULE_DESCRIPTIONS = {
        'hourly': 'Every hour at the beginning of the hour',
        'daily': 'Every day at 8:00 AM',
        'daily_midnight': 'Every day at midnight',
        'weekly': 'Every Monday at 8:00 AM',
        'monthly': 'First day of every month at 8:00 AM',
        'quarterly': 'First day of every quarter at 8:00 AM',
        'yearly': 'January 1st at 8:00 AM',
        'business_days': 'Monday through Friday at 8:00 AM',
        'weekends': 'Saturday and Sunday at 10:00 AM',
        'twice_daily': 'Twice daily at 8:00 AM and 8:00 PM',
        'every_6_hours': 'Every 6 hours',
        'every_30_minutes': 'Every 30 minutes',
        'every_15_minutes': 'Every 15 minutes',
    }
    
    def __init__(self, timezone: str = 'UTC'):
        self.timezone = pytz.timezone(timezone)
    
    def parse(self, cron_expression: str) -> Dict[str, Any]:
        """
        Parse a cron expression and return details.
        
        Args:
            cron_expression: Cron expression or predefined schedule name
            
        Returns:
            Dictionary with parsed information
        """
        # Check if it's a predefined schedule
        if cron_expression.lower() in self.PREDEFINED_SCHEDULES:
            schedule_name = cron_expression.lower()
            actual_cron = self.PREDEFINED_SCHEDULES[schedule_name]
            description = self.SCHEDULE_DESCRIPTIONS[schedule_name]
        else:
            actual_cron = cron_expression
            description = self._generate_description(actual_cron)
            schedule_name = None
        
        # Validate cron expression
        is_valid, error = self.validate(actual_cron)
        if not is_valid:
            return {
                'valid': False,
                'error': error,
                'expression': cron_expression
            }
        
        # Get next runs
        next_runs = self.get_next_runs(actual_cron, count=5)
        
        return {
            'valid': True,
            'expression': cron_expression,
            'cron': actual_cron,
            'schedule_name': schedule_name,
            'description': description,
            'next_runs': next_runs,
            'timezone': str(self.timezone),
            'fields': self._parse_fields(actual_cron)
        }
    
    def validate(self, cron_expression: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a cron expression.
        
        Args:
            cron_expression: Cron expression to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to create croniter instance
            croniter(cron_expression)
            return True, None
        except (ValueError, TypeError) as e:
            return False, str(e)
    
    def get_next_runs(
        self,
        cron_expression: str,
        count: int = 10,
        start_time: Optional[datetime] = None
    ) -> List[str]:
        """
        Get next scheduled run times.
        
        Args:
            cron_expression: Cron expression
            count: Number of next runs to return
            start_time: Start time for calculation
            
        Returns:
            List of next run times as ISO strings
        """
        if start_time is None:
            start_time = datetime.now(self.timezone)
        
        try:
            cron = croniter(cron_expression, start_time)
            next_runs = []
            
            for _ in range(count):
                next_run = cron.get_next(datetime)
                next_runs.append(next_run.isoformat())
            
            return next_runs
        except Exception as e:
            logger.error(f"Error calculating next runs: {e}")
            return []
    
    def get_previous_run(
        self,
        cron_expression: str,
        reference_time: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Get the previous scheduled run time.
        
        Args:
            cron_expression: Cron expression
            reference_time: Reference time for calculation
            
        Returns:
            Previous run time as ISO string or None
        """
        if reference_time is None:
            reference_time = datetime.now(self.timezone)
        
        try:
            cron = croniter(cron_expression, reference_time)
            prev_run = cron.get_prev(datetime)
            return prev_run.isoformat()
        except Exception as e:
            logger.error(f"Error calculating previous run: {e}")
            return None
    
    def is_due(
        self,
        cron_expression: str,
        last_run: Optional[datetime] = None,
        reference_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if a task is due based on cron expression.
        
        Args:
            cron_expression: Cron expression
            last_run: Last run time
            reference_time: Current time to check against
            
        Returns:
            True if task is due
        """
        if reference_time is None:
            reference_time = datetime.now(self.timezone)
        
        if last_run is None:
            # If never run, it's due
            return True
        
        try:
            # Get next run time after last run
            cron = croniter(cron_expression, last_run)
            next_run = cron.get_next(datetime)
            
            # Check if next run is before or at reference time
            return next_run <= reference_time
        except Exception as e:
            logger.error(f"Error checking if due: {e}")
            return False
    
    def _parse_fields(self, cron_expression: str) -> Dict[str, str]:
        """Parse individual cron fields."""
        parts = cron_expression.split()
        if len(parts) < 5:
            return {}
        
        field_names = ['minute', 'hour', 'day', 'month', 'weekday']
        fields = {}
        
        for i, (name, value) in enumerate(zip(field_names, parts[:5])):
            fields[name] = {
                'value': value,
                'description': self._describe_field(name, value)
            }
        
        # Handle optional fields
        if len(parts) > 5:
            fields['year'] = {
                'value': parts[5],
                'description': self._describe_field('year', parts[5])
            }
        
        return fields
    
    def _describe_field(self, field_name: str, value: str) -> str:
        """Generate human-readable description for a cron field."""
        if value == '*':
            return f"Every {field_name}"
        elif value.startswith('*/'):
            interval = value[2:]
            return f"Every {interval} {field_name}s"
        elif ',' in value:
            values = value.split(',')
            return f"{field_name}s: {', '.join(values)}"
        elif '-' in value:
            start, end = value.split('-')
            return f"{field_name}s from {start} to {end}"
        else:
            return f"{field_name} {value}"
    
    def _generate_description(self, cron_expression: str) -> str:
        """Generate human-readable description for cron expression."""
        try:
            from cron_descriptor import get_description
            return get_description(cron_expression)
        except Exception:
            # Fallback to basic description
            parts = cron_expression.split()
            if len(parts) >= 5:
                return f"Runs at {parts[1]}:{parts[0]} on day {parts[2]} of month {parts[3]}, weekday {parts[4]}"
            return "Custom schedule"
    
    def get_frequency_stats(
        self,
        cron_expression: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get frequency statistics for a cron expression.
        
        Args:
            cron_expression: Cron expression
            period_days: Period to analyze
            
        Returns:
            Dictionary with frequency statistics
        """
        start_time = datetime.now(self.timezone)
        end_time = start_time + timedelta(days=period_days)
        
        try:
            cron = croniter(cron_expression, start_time)
            runs = []
            
            while True:
                next_run = cron.get_next(datetime)
                if next_run > end_time:
                    break
                runs.append(next_run)
            
            if not runs:
                return {
                    'total_runs': 0,
                    'daily_average': 0,
                    'weekly_average': 0,
                    'runs_per_day': {}
                }
            
            # Calculate statistics
            total_runs = len(runs)
            daily_average = total_runs / period_days
            weekly_average = daily_average * 7
            
            # Count runs per day of week
            runs_per_day = {}
            for run in runs:
                day_name = run.strftime('%A')
                runs_per_day[day_name] = runs_per_day.get(day_name, 0) + 1
            
            # Calculate intervals
            intervals = []
            for i in range(1, len(runs)):
                interval = (runs[i] - runs[i-1]).total_seconds() / 60  # in minutes
                intervals.append(interval)
            
            return {
                'total_runs': total_runs,
                'daily_average': round(daily_average, 2),
                'weekly_average': round(weekly_average, 2),
                'runs_per_day': runs_per_day,
                'min_interval_minutes': min(intervals) if intervals else None,
                'max_interval_minutes': max(intervals) if intervals else None,
                'avg_interval_minutes': sum(intervals) / len(intervals) if intervals else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating frequency stats: {e}")
            return {
                'error': str(e),
                'total_runs': 0,
                'daily_average': 0,
                'weekly_average': 0
            }


class ScheduleManager:
    """Manager for scheduled tasks using cron expressions."""
    
    def __init__(self, timezone: str = 'UTC'):
        self.parser = CronParser(timezone)
        self.scheduled_tasks = {}
    
    def add_task(
        self,
        task_id: str,
        cron_expression: str,
        task_function: callable,
        task_args: tuple = (),
        task_kwargs: dict = None,
        description: str = ""
    ) -> bool:
        """
        Add a scheduled task.
        
        Args:
            task_id: Unique task identifier
            cron_expression: Cron expression for scheduling
            task_function: Function to execute
            task_args: Positional arguments for function
            task_kwargs: Keyword arguments for function
            description: Task description
            
        Returns:
            True if task added successfully
        """
        # Validate cron expression
        is_valid, error = self.parser.validate(cron_expression)
        if not is_valid:
            logger.error(f"Invalid cron expression for task {task_id}: {error}")
            return False
        
        self.scheduled_tasks[task_id] = {
            'cron': cron_expression,
            'function': task_function,
            'args': task_args,
            'kwargs': task_kwargs or {},
            'description': description,
            'last_run': None,
            'next_run': self.parser.get_next_runs(cron_expression, count=1)[0],
            'created_at': datetime.utcnow().isoformat(),
            'enabled': True
        }
        
        logger.info(f"Added scheduled task: {task_id}")
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        if task_id in self.scheduled_tasks:
            del self.scheduled_tasks[task_id]
            logger.info(f"Removed scheduled task: {task_id}")
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id]['enabled'] = True
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id]['enabled'] = False
            return True
        return False
    
    def get_due_tasks(self) -> List[str]:
        """Get list of tasks that are due to run."""
        due_tasks = []
        current_time = datetime.now(self.parser.timezone)
        
        for task_id, task_info in self.scheduled_tasks.items():
            if not task_info['enabled']:
                continue
            
            if self.parser.is_due(
                task_info['cron'],
                task_info['last_run'],
                current_time
            ):
                due_tasks.append(task_id)
        
        return due_tasks
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a scheduled task."""
        if task_id not in self.scheduled_tasks:
            return None
        
        task = self.scheduled_tasks[task_id].copy()
        # Remove function reference from returned data
        task.pop('function', None)
        
        # Add parsed cron info
        task['cron_info'] = self.parser.parse(task['cron'])
        task['frequency_stats'] = self.parser.get_frequency_stats(task['cron'])
        
        return task
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all scheduled tasks."""
        tasks = []
        for task_id in self.scheduled_tasks:
            task_info = self.get_task_info(task_id)
            if task_info:
                task_info['id'] = task_id
                tasks.append(task_info)
        return tasks


# Singleton instances
_cron_parser = None
_schedule_manager = None


def get_cron_parser(timezone: str = 'UTC') -> CronParser:
    """Get singleton instance of cron parser."""
    global _cron_parser
    if _cron_parser is None or _cron_parser.timezone.zone != timezone:
        _cron_parser = CronParser(timezone)
    return _cron_parser


def get_schedule_manager(timezone: str = 'UTC') -> ScheduleManager:
    """Get singleton instance of schedule manager."""
    global _schedule_manager
    if _schedule_manager is None or _schedule_manager.parser.timezone.zone != timezone:
        _schedule_manager = ScheduleManager(timezone)
    return _schedule_manager