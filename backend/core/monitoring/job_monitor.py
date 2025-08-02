"""
Job monitoring and alerting for Celery tasks
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio

from sqlalchemy import select, func, and_
from celery import current_app
from celery.result import AsyncResult

from core.tasks.db_context import get_db_context
from core.redis import redis_client
from core.logging import logger
from core.monitoring.models import Alert
# TaskExecution is not used in this file, commenting out for now
# from core.domain.models import TaskExecution


class JobMonitor:
    """Monitor Celery job execution and health"""
    
    def __init__(self):
        self.celery_app = current_app
        self.alert_thresholds = {
            'failure_rate': 0.1,  # 10% failure rate
            'retry_rate': 0.2,    # 20% retry rate
            'queue_size': 1000,   # Max queue size
            'execution_time': 3600  # 1 hour max execution time
        }
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get current queue statistics
        """
        stats = {}
        
        # Get queue sizes
        queues = [
            'default', 'email', 'sync', 'analytics', 
            'ml', 'reports', 'cleanup', 'notifications'
        ]
        
        for queue_name in queues:
            queue_key = f"celery:queue:{queue_name}"
            queue_size = await redis_client.llen(queue_key)
            
            stats[queue_name] = {
                'size': queue_size,
                'status': 'healthy' if queue_size < self.alert_thresholds['queue_size'] else 'overloaded'
            }
        
        return stats
    
    async def get_task_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get task execution statistics
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        stats = {}
        
        # Get all task types
        task_types = [
            'send_email', 'sync_onlyfans_data', 'sync_inflow_transactions',
            'calculate_daily_metrics', 'generate_daily_reports',
            'cleanup_expired_sessions', 'send_push_notification'
        ]
        
        for task_name in task_types:
            # Get metrics from Redis
            success_key = f"task_metrics:{task_name}:success"
            failure_key = f"task_metrics:{task_name}:failure"
            retry_key = f"task_metrics:{task_name}:retry"
            
            success_count = int(await redis_client.get(success_key) or 0)
            failure_count = int(await redis_client.get(failure_key) or 0)
            retry_count = int(await redis_client.get(retry_key) or 0)
            
            total = success_count + failure_count
            
            if total > 0:
                failure_rate = failure_count / total
                retry_rate = retry_count / total
                
                stats[task_name] = {
                    'success': success_count,
                    'failure': failure_count,
                    'retry': retry_count,
                    'total': total,
                    'failure_rate': failure_rate,
                    'retry_rate': retry_rate,
                    'status': self._get_task_health_status(failure_rate, retry_rate)
                }
        
        return stats
    
    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Get currently active tasks
        """
        active_tasks = []
        
        # Get active tasks from Celery
        inspect = self.celery_app.control.inspect()
        active = inspect.active()
        
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    task_info = {
                        'id': task['id'],
                        'name': task['name'],
                        'worker': worker,
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {}),
                        'time_start': task.get('time_start'),
                        'runtime': self._calculate_runtime(task.get('time_start'))
                    }
                    
                    # Check if task is running too long
                    if task_info['runtime'] > self.alert_thresholds['execution_time']:
                        task_info['status'] = 'long_running'
                    else:
                        task_info['status'] = 'active'
                    
                    active_tasks.append(task_info)
        
        return active_tasks
    
    async def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """
        Get scheduled tasks from beat schedule
        """
        scheduled_tasks = []
        
        # Get beat schedule
        schedule = self.celery_app.conf.beat_schedule
        
        for task_name, task_config in schedule.items():
            task_info = {
                'name': task_name,
                'task': task_config['task'],
                'schedule': str(task_config['schedule']),
                'options': task_config.get('options', {})
            }
            
            # Get last execution info
            last_exec_key = f"task_last_execution:{task_config['task']}"
            last_exec = await redis_client.get(last_exec_key)
            
            if last_exec:
                last_exec_data = json.loads(last_exec)
                task_info['last_execution'] = last_exec_data
            
            scheduled_tasks.append(task_info)
        
        return scheduled_tasks
    
    async def check_health_and_alert(self) -> Dict[str, Any]:
        """
        Check overall system health and send alerts if needed
        """
        health_report = {
            'status': 'healthy',
            'checks': {},
            'alerts': []
        }
        
        # Check queue health
        queue_stats = await self.get_queue_stats()
        for queue_name, stats in queue_stats.items():
            if stats['status'] != 'healthy':
                health_report['status'] = 'degraded'
                health_report['alerts'].append({
                    'type': 'queue_overload',
                    'queue': queue_name,
                    'size': stats['size'],
                    'threshold': self.alert_thresholds['queue_size']
                })
        
        health_report['checks']['queues'] = queue_stats
        
        # Check task health
        task_stats = await self.get_task_stats(hours=1)
        unhealthy_tasks = [
            (name, stats) for name, stats in task_stats.items()
            if stats['status'] != 'healthy'
        ]
        
        if unhealthy_tasks:
            health_report['status'] = 'degraded'
            for task_name, stats in unhealthy_tasks:
                if stats['failure_rate'] > self.alert_thresholds['failure_rate']:
                    health_report['alerts'].append({
                        'type': 'high_failure_rate',
                        'task': task_name,
                        'failure_rate': stats['failure_rate'],
                        'threshold': self.alert_thresholds['failure_rate']
                    })
        
        health_report['checks']['tasks'] = task_stats
        
        # Check for long-running tasks
        active_tasks = await self.get_active_tasks()
        long_running = [t for t in active_tasks if t['status'] == 'long_running']
        
        if long_running:
            health_report['status'] = 'warning'
            for task in long_running:
                health_report['alerts'].append({
                    'type': 'long_running_task',
                    'task': task['name'],
                    'task_id': task['id'],
                    'runtime': task['runtime'],
                    'threshold': self.alert_thresholds['execution_time']
                })
        
        health_report['checks']['active_tasks'] = {
            'total': len(active_tasks),
            'long_running': len(long_running)
        }
        
        # Store alerts in database
        if health_report['alerts']:
            await self._store_alerts(health_report['alerts'])
        
        return health_report
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get worker statistics
        """
        inspect = self.celery_app.control.inspect()
        
        stats = {
            'workers': {},
            'total_workers': 0,
            'total_active_tasks': 0
        }
        
        # Get worker stats
        worker_stats = inspect.stats()
        if worker_stats:
            for worker_name, worker_info in worker_stats.items():
                stats['workers'][worker_name] = {
                    'status': 'online',
                    'pool': worker_info.get('pool', {}),
                    'total_tasks': worker_info.get('total', {}),
                    'rusage': worker_info.get('rusage', {})
                }
                stats['total_workers'] += 1
        
        # Get active tasks per worker
        active = inspect.active()
        if active:
            for worker_name, tasks in active.items():
                if worker_name in stats['workers']:
                    stats['workers'][worker_name]['active_tasks'] = len(tasks)
                    stats['total_active_tasks'] += len(tasks)
        
        return stats
    
    async def retry_failed_tasks(self, task_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retry failed tasks
        """
        results = {
            'retried': 0,
            'errors': []
        }
        
        # Get failed tasks from Redis
        pattern = f"task_result:*" if not task_name else f"task_result:*{task_name}*"
        cursor = 0
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                try:
                    result_data = await redis_client.get(key)
                    if result_data:
                        task_result = json.loads(result_data)
                        
                        if task_result.get('status') == 'failed':
                            # Retry the task
                            task_id = key.split(':')[-1]
                            if await self._retry_task(task_id, task_result):
                                results['retried'] += 1
                
                except Exception as exc:
                    results['errors'].append({
                        'key': key,
                        'error': str(exc)
                    })
            
            if cursor == 0:
                break
        
        return results
    
    def _get_task_health_status(self, failure_rate: float, retry_rate: float) -> str:
        """
        Determine task health status based on rates
        """
        if failure_rate > self.alert_thresholds['failure_rate']:
            return 'critical'
        elif retry_rate > self.alert_thresholds['retry_rate']:
            return 'warning'
        else:
            return 'healthy'
    
    def _calculate_runtime(self, time_start: Optional[str]) -> float:
        """
        Calculate task runtime in seconds
        """
        if not time_start:
            return 0
        
        try:
            start_time = datetime.fromisoformat(time_start)
            return (datetime.utcnow() - start_time).total_seconds()
        except:
            return 0
    
    async def _store_alerts(self, alerts: List[Dict[str, Any]]):
        """
        Store alerts in database
        """
        try:
            async with get_db_context() as db:
                for alert_data in alerts:
                    alert = Alert(
                        type=alert_data['type'],
                        severity='high' if 'critical' in alert_data['type'] else 'medium',
                        title=f"{alert_data['type'].replace('_', ' ').title()}",
                        description=json.dumps(alert_data),
                        metadata=alert_data,
                        created_at=datetime.utcnow()
                    )
                    db.add(alert)
                
                await db.commit()
        
        except Exception as exc:
            logger.error(f"Failed to store alerts: {exc}")
    
    async def _retry_task(self, task_id: str, task_result: Dict[str, Any]) -> bool:
        """
        Retry a failed task
        """
        try:
            # Get task function
            task_name = task_result.get('task_name')
            if not task_name:
                return False
            
            # Import and retry task
            task_func = self.celery_app.tasks.get(task_name)
            if task_func:
                # Retry with original args/kwargs if available
                task_func.apply_async(
                    args=task_result.get('args', []),
                    kwargs=task_result.get('kwargs', {}),
                    retry=True
                )
                return True
            
            return False
        
        except Exception as exc:
            logger.error(f"Failed to retry task {task_id}: {exc}")
            return False


# Global monitor instance
job_monitor = JobMonitor()


async def monitor_jobs():
    """
    Run job monitoring (called periodically)
    """
    try:
        health_report = await job_monitor.check_health_and_alert()
        
        # Log health status
        if health_report['status'] != 'healthy':
            logger.warning(f"Job system health degraded: {health_report}")
        
        # Store health report
        await redis_client.setex(
            "job_health:latest",
            300,  # 5 minutes
            json.dumps({
                **health_report,
                'timestamp': datetime.utcnow().isoformat()
            })
        )
        
        return health_report
    
    except Exception as exc:
        logger.error(f"Job monitoring failed: {exc}")
        raise