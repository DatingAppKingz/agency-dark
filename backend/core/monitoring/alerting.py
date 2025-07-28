"""
Alerting and notification system
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import re
import hashlib

import httpx
from jinja2 import Template

from core.redis import redis_client
from core.logging import logger
from core.config import settings
from core.monitoring.metrics import registry
from prometheus_client import Counter, Gauge


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertState(Enum):
    """Alert states"""
    PENDING = "pending"     # Alert condition met, waiting for duration
    FIRING = "firing"       # Alert is active
    RESOLVED = "resolved"   # Alert condition no longer met
    SILENCED = "silenced"   # Alert is silenced


class NotificationChannel(Enum):
    """Notification channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    DISCORD = "discord"


@dataclass
class AlertRule:
    """Alert rule definition"""
    name: str
    description: str
    query: str  # Prometheus query or condition
    severity: AlertSeverity
    for_duration: timedelta = timedelta(minutes=5)  # How long condition must be true
    annotations: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    channels: List[NotificationChannel] = field(default_factory=list)
    silence_duration: Optional[timedelta] = timedelta(hours=4)  # Auto-silence after firing
    
    def __post_init__(self):
        # Generate rule ID
        self.id = hashlib.md5(f"{self.name}:{self.query}".encode()).hexdigest()[:8]


@dataclass
class Alert:
    """Active alert instance"""
    rule: AlertRule
    state: AlertState
    value: Any
    started_at: datetime
    fired_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    last_notification: Optional[datetime] = None
    notification_count: int = 0
    fingerprint: str = ""
    
    def __post_init__(self):
        if not self.fingerprint:
            # Generate fingerprint from rule and labels
            label_str = json.dumps(self.rule.labels, sort_keys=True)
            self.fingerprint = hashlib.md5(
                f"{self.rule.id}:{label_str}".encode()
            ).hexdigest()


# Metrics for alerting
alerts_total = Counter(
    'alerts_total',
    'Total number of alerts',
    ['severity', 'state'],
    registry=registry
)

alerts_firing = Gauge(
    'alerts_firing',
    'Number of currently firing alerts',
    ['severity'],
    registry=registry
)

notifications_sent = Counter(
    'alert_notifications_sent_total',
    'Total notifications sent',
    ['channel', 'severity'],
    registry=registry
)

notification_errors = Counter(
    'alert_notification_errors_total',
    'Total notification errors',
    ['channel'],
    registry=registry
)


class NotificationHandler:
    """Base class for notification handlers"""
    
    async def send(self, alert: Alert, message: str) -> bool:
        """Send notification"""
        raise NotImplementedError


class SlackNotificationHandler(NotificationHandler):
    """Slack notification handler"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, alert: Alert, message: str) -> bool:
        """Send Slack notification"""
        try:
            # Format message for Slack
            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9900",
                AlertSeverity.ERROR: "#ff0000",
                AlertSeverity.CRITICAL: "#990000"
            }.get(alert.rule.severity, "#808080")
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"🚨 {alert.rule.severity.value.upper()}: {alert.rule.name}",
                    "text": message,
                    "fields": [
                        {"title": "Description", "value": alert.rule.description, "short": False},
                        {"title": "Started", "value": alert.started_at.isoformat(), "short": True},
                        {"title": "Value", "value": str(alert.value), "short": True}
                    ],
                    "footer": "Agency Platform Alerting",
                    "ts": int(datetime.utcnow().timestamp())
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            
            return True
            
        except Exception as exc:
            logger.error(f"Failed to send Slack notification: {exc}")
            return False


class EmailNotificationHandler(NotificationHandler):
    """Email notification handler"""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        self.smtp_config = smtp_config
    
    async def send(self, alert: Alert, message: str) -> bool:
        """Send email notification"""
        try:
            import aiosmtplib
            from email.message import EmailMessage
            
            msg = EmailMessage()
            msg["Subject"] = f"[{alert.rule.severity.value.upper()}] {alert.rule.name}"
            msg["From"] = self.smtp_config["from"]
            msg["To"] = self.smtp_config["to"]
            
            # Create HTML body
            html_template = """
            <html>
                <body>
                    <h2 style="color: {{ color }}">{{ severity }} Alert: {{ name }}</h2>
                    <p>{{ message }}</p>
                    <hr>
                    <table>
                        <tr><td><strong>Description:</strong></td><td>{{ description }}</td></tr>
                        <tr><td><strong>Started:</strong></td><td>{{ started_at }}</td></tr>
                        <tr><td><strong>Value:</strong></td><td>{{ value }}</td></tr>
                    </table>
                </body>
            </html>
            """
            
            template = Template(html_template)
            html_body = template.render(
                color={"info": "blue", "warning": "orange", "error": "red", "critical": "darkred"}
                      .get(alert.rule.severity.value, "gray"),
                severity=alert.rule.severity.value.upper(),
                name=alert.rule.name,
                message=message,
                description=alert.rule.description,
                started_at=alert.started_at.isoformat(),
                value=alert.value
            )
            
            msg.set_content(message)
            msg.add_alternative(html_body, subtype="html")
            
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_config["host"],
                port=self.smtp_config["port"],
                username=self.smtp_config.get("username"),
                password=self.smtp_config.get("password"),
                use_tls=self.smtp_config.get("use_tls", True)
            )
            
            return True
            
        except Exception as exc:
            logger.error(f"Failed to send email notification: {exc}")
            return False


class WebhookNotificationHandler(NotificationHandler):
    """Generic webhook notification handler"""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
    
    async def send(self, alert: Alert, message: str) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                "alert": {
                    "name": alert.rule.name,
                    "description": alert.rule.description,
                    "severity": alert.rule.severity.value,
                    "state": alert.state.value,
                    "value": alert.value,
                    "started_at": alert.started_at.isoformat(),
                    "fired_at": alert.fired_at.isoformat() if alert.fired_at else None,
                    "labels": alert.rule.labels,
                    "annotations": alert.rule.annotations
                },
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
            
            return True
            
        except Exception as exc:
            logger.error(f"Failed to send webhook notification: {exc}")
            return False


class AlertManager:
    """Main alert management service"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, Alert] = {}
        self.handlers: Dict[NotificationChannel, NotificationHandler] = {}
        self.silenced_alerts: Dict[str, datetime] = {}
        self._evaluation_task = None
        self._evaluation_interval = 30  # seconds
    
    def register_rule(self, rule: AlertRule):
        """Register an alert rule"""
        self.rules[rule.id] = rule
        logger.info(f"Registered alert rule: {rule.name}")
    
    def register_handler(self, channel: NotificationChannel, handler: NotificationHandler):
        """Register a notification handler"""
        self.handlers[channel] = handler
        logger.info(f"Registered handler for channel: {channel.value}")
    
    async def start(self):
        """Start alert evaluation"""
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        logger.info("Alert manager started")
    
    async def stop(self):
        """Stop alert evaluation"""
        if self._evaluation_task:
            self._evaluation_task.cancel()
            await asyncio.gather(self._evaluation_task, return_exceptions=True)
    
    async def _evaluation_loop(self):
        """Main evaluation loop"""
        while True:
            try:
                await self._evaluate_all_rules()
                await asyncio.sleep(self._evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in alert evaluation: {exc}")
    
    async def _evaluate_all_rules(self):
        """Evaluate all alert rules"""
        for rule in self.rules.values():
            try:
                await self._evaluate_rule(rule)
            except Exception as exc:
                logger.error(f"Error evaluating rule {rule.name}: {exc}")
    
    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule"""
        # This is a simplified evaluation - in production, you'd query Prometheus
        # or evaluate the condition properly
        
        # For demonstration, use random conditions
        import random
        condition_met = random.random() < 0.1  # 10% chance
        value = random.randint(1, 100)
        
        alert_key = rule.id
        existing_alert = self.alerts.get(alert_key)
        
        if condition_met:
            if not existing_alert:
                # New alert
                alert = Alert(
                    rule=rule,
                    state=AlertState.PENDING,
                    value=value,
                    started_at=datetime.utcnow()
                )
                self.alerts[alert_key] = alert
                alerts_total.labels(severity=rule.severity.value, state="pending").inc()
                logger.info(f"Alert {rule.name} is pending")
                
            elif existing_alert.state == AlertState.PENDING:
                # Check if duration exceeded
                if datetime.utcnow() - existing_alert.started_at >= rule.for_duration:
                    # Fire alert
                    existing_alert.state = AlertState.FIRING
                    existing_alert.fired_at = datetime.utcnow()
                    alerts_total.labels(severity=rule.severity.value, state="firing").inc()
                    alerts_firing.labels(severity=rule.severity.value).inc()
                    
                    await self._send_notifications(existing_alert)
                    logger.warning(f"Alert {rule.name} is firing")
                    
        else:
            if existing_alert and existing_alert.state in [AlertState.PENDING, AlertState.FIRING]:
                # Resolve alert
                existing_alert.state = AlertState.RESOLVED
                existing_alert.resolved_at = datetime.utcnow()
                alerts_total.labels(severity=rule.severity.value, state="resolved").inc()
                
                if existing_alert.fired_at:
                    alerts_firing.labels(severity=rule.severity.value).dec()
                    await self._send_resolution_notification(existing_alert)
                
                # Remove from active alerts
                del self.alerts[alert_key]
                logger.info(f"Alert {rule.name} resolved")
    
    async def _send_notifications(self, alert: Alert):
        """Send notifications for an alert"""
        # Check if alert is silenced
        if alert.fingerprint in self.silenced_alerts:
            silence_until = self.silenced_alerts[alert.fingerprint]
            if datetime.utcnow() < silence_until:
                logger.info(f"Alert {alert.rule.name} is silenced until {silence_until}")
                return
        
        # Generate message
        message = self._generate_alert_message(alert)
        
        # Send to all configured channels
        for channel in alert.rule.channels:
            handler = self.handlers.get(channel)
            if handler:
                try:
                    success = await handler.send(alert, message)
                    if success:
                        notifications_sent.labels(
                            channel=channel.value,
                            severity=alert.rule.severity.value
                        ).inc()
                        alert.last_notification = datetime.utcnow()
                        alert.notification_count += 1
                    else:
                        notification_errors.labels(channel=channel.value).inc()
                except Exception as exc:
                    logger.error(f"Error sending {channel.value} notification: {exc}")
                    notification_errors.labels(channel=channel.value).inc()
        
        # Auto-silence if configured
        if alert.rule.silence_duration:
            self.silenced_alerts[alert.fingerprint] = (
                datetime.utcnow() + alert.rule.silence_duration
            )
    
    async def _send_resolution_notification(self, alert: Alert):
        """Send notification when alert is resolved"""
        message = f"✅ RESOLVED: {alert.rule.name}\n\n"
        message += f"The alert condition is no longer met.\n"
        message += f"Alert was active for: {alert.resolved_at - alert.started_at}"
        
        # Send to all configured channels
        for channel in alert.rule.channels:
            handler = self.handlers.get(channel)
            if handler:
                try:
                    await handler.send(alert, message)
                except Exception as exc:
                    logger.error(f"Error sending resolution notification: {exc}")
    
    def _generate_alert_message(self, alert: Alert) -> str:
        """Generate alert message"""
        template = Template(alert.rule.annotations.get("message", """
🚨 {{ severity }} Alert: {{ name }}

{{ description }}

Current value: {{ value }}
Started at: {{ started_at }}
{% if labels %}
Labels:
{% for key, value in labels.items() %}
  {{ key }}: {{ value }}
{% endfor %}
{% endif %}
        """))
        
        return template.render(
            severity=alert.rule.severity.value.upper(),
            name=alert.rule.name,
            description=alert.rule.description,
            value=alert.value,
            started_at=alert.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            labels=alert.rule.labels
        )
    
    async def silence_alert(self, alert_id: str, duration: timedelta, reason: str):
        """Silence an alert"""
        alert = self.alerts.get(alert_id)
        if alert:
            self.silenced_alerts[alert.fingerprint] = datetime.utcnow() + duration
            logger.info(f"Silenced alert {alert.rule.name} for {duration}: {reason}")
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.alerts.values())
    
    async def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history from Redis"""
        history = []
        pattern = "alerts:history:*"
        keys = await redis_client.keys(pattern)
        
        for key in keys:
            data = await redis_client.get(key)
            if data:
                alert_data = json.loads(data)
                # Filter by time
                if datetime.fromisoformat(alert_data['started_at']) > datetime.utcnow() - timedelta(hours=hours):
                    history.append(alert_data)
        
        # Sort by start time
        history.sort(key=lambda x: x['started_at'], reverse=True)
        return history


# Global alert manager
alert_manager = AlertManager()


# Default alert rules
def create_default_alert_rules() -> List[AlertRule]:
    """Create default alert rules"""
    return [
        # High Error Rate
        AlertRule(
            name="High Error Rate",
            description="API error rate is above 5%",
            query='rate(http_requests_total{status=~"5.."}[5m]) > 0.05',
            severity=AlertSeverity.ERROR,
            for_duration=timedelta(minutes=5),
            annotations={"message": "API error rate is {{ value }}%"},
            labels={"team": "backend", "component": "api"},
            channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL]
        ),
        
        # High Response Time
        AlertRule(
            name="High Response Time",
            description="API response time p95 is above 1 second",
            query='histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1',
            severity=AlertSeverity.WARNING,
            for_duration=timedelta(minutes=10),
            annotations={"message": "API response time p95 is {{ value }}s"},
            labels={"team": "backend", "component": "api"},
            channels=[NotificationChannel.SLACK]
        ),
        
        # Database Connection Pool Exhausted
        AlertRule(
            name="Database Connection Pool Exhausted",
            description="Database connection pool is at capacity",
            query='database_connections_active / database_connections_max > 0.9',
            severity=AlertSeverity.CRITICAL,
            for_duration=timedelta(minutes=2),
            annotations={"message": "Database connection pool is {{ value }}% full"},
            labels={"team": "backend", "component": "database"},
            channels=[NotificationChannel.SLACK, NotificationChannel.PAGERDUTY]
        ),
        
        # High Memory Usage
        AlertRule(
            name="High Memory Usage",
            description="Memory usage is above 90%",
            query='system_memory_usage_percent > 90',
            severity=AlertSeverity.WARNING,
            for_duration=timedelta(minutes=15),
            annotations={"message": "Memory usage is {{ value }}%"},
            labels={"team": "infrastructure", "component": "system"},
            channels=[NotificationChannel.SLACK]
        ),
        
        # Disk Space Low
        AlertRule(
            name="Low Disk Space",
            description="Disk space is below 10%",
            query='system_disk_available_bytes / system_disk_total_bytes < 0.1',
            severity=AlertSeverity.CRITICAL,
            for_duration=timedelta(minutes=5),
            annotations={"message": "Only {{ value }}% disk space remaining"},
            labels={"team": "infrastructure", "component": "system"},
            channels=[NotificationChannel.SLACK, NotificationChannel.PAGERDUTY]
        ),
        
        # Task Queue Backlog
        AlertRule(
            name="Task Queue Backlog",
            description="Task queue has more than 1000 pending tasks",
            query='queue_size > 1000',
            severity=AlertSeverity.WARNING,
            for_duration=timedelta(minutes=10),
            annotations={"message": "Task queue has {{ value }} pending tasks"},
            labels={"team": "backend", "component": "celery"},
            channels=[NotificationChannel.SLACK]
        ),
        
        # SLO Violation
        AlertRule(
            name="SLO Violation",
            description="Service Level Objective is not being met",
            query='slo_compliance{slo_name="api_availability"} < 99.9',
            severity=AlertSeverity.ERROR,
            for_duration=timedelta(minutes=15),
            annotations={"message": "SLO compliance is {{ value }}%"},
            labels={"team": "backend", "component": "slo"},
            channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL]
        )
    ]


# Setup function
def setup_alerting():
    """Setup alerting with default rules and handlers"""
    # Register default rules
    for rule in create_default_alert_rules():
        alert_manager.register_rule(rule)
    
    # Register handlers based on configuration
    if hasattr(settings, 'SLACK_WEBHOOK_URL'):
        alert_manager.register_handler(
            NotificationChannel.SLACK,
            SlackNotificationHandler(settings.SLACK_WEBHOOK_URL)
        )
    
    if hasattr(settings, 'SMTP_CONFIG'):
        alert_manager.register_handler(
            NotificationChannel.EMAIL,
            EmailNotificationHandler(settings.SMTP_CONFIG)
        )
    
    logger.info("Alerting system configured")


# FastAPI integration
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response


def setup_alerting_api(app: FastAPI):
    """Setup alerting API endpoints"""
    
    @app.on_event("startup")
    async def startup_alerting():
        setup_alerting()
        await alert_manager.start()
    
    @app.on_event("shutdown")
    async def shutdown_alerting():
        await alert_manager.stop()
    
    # API endpoints
    @app.get("/api/v1/alerts")
    async def get_active_alerts():
        """Get all active alerts"""
        alerts = await alert_manager.get_active_alerts()
        return {
            "alerts": [
                {
                    "id": alert.rule.id,
                    "name": alert.rule.name,
                    "severity": alert.rule.severity.value,
                    "state": alert.state.value,
                    "value": alert.value,
                    "started_at": alert.started_at.isoformat(),
                    "fired_at": alert.fired_at.isoformat() if alert.fired_at else None
                }
                for alert in alerts
            ],
            "count": len(alerts)
        }
    
    @app.get("/api/v1/alerts/history")
    async def get_alert_history(hours: int = 24):
        """Get alert history"""
        history = await alert_manager.get_alert_history(hours)
        return {"history": history, "count": len(history)}
    
    @app.post("/api/v1/alerts/{alert_id}/silence")
    async def silence_alert(
        alert_id: str,
        hours: int = 4,
        reason: str = "Manual silence"
    ):
        """Silence an alert"""
        await alert_manager.silence_alert(
            alert_id,
            timedelta(hours=hours),
            reason
        )
        return {"message": f"Alert {alert_id} silenced for {hours} hours"}
    
    @app.get("/api/v1/alerts/rules")
    async def get_alert_rules():
        """Get all alert rules"""
        return {
            "rules": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "description": rule.description,
                    "severity": rule.severity.value,
                    "query": rule.query,
                    "for_duration": rule.for_duration.total_seconds(),
                    "channels": [ch.value for ch in rule.channels]
                }
                for rule in alert_manager.rules.values()
            ]
        }
    
    @app.post("/api/v1/alerts/test")
    async def test_alert(rule_name: str):
        """Test an alert rule by triggering it manually"""
        rule = next(
            (r for r in alert_manager.rules.values() if r.name == rule_name),
            None
        )
        
        if not rule:
            raise HTTPException(404, "Alert rule not found")
        
        # Create test alert
        test_alert = Alert(
            rule=rule,
            state=AlertState.FIRING,
            value="TEST",
            started_at=datetime.utcnow(),
            fired_at=datetime.utcnow()
        )
        
        await alert_manager._send_notifications(test_alert)
        
        return {"message": f"Test alert sent for rule: {rule_name}"}
