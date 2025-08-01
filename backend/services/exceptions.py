"""Service-specific exceptions for better error handling."""

from typing import Optional, Dict, Any


class ServiceException(Exception):
    """Base exception for all service errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class NotificationException(ServiceException):
    """Base exception for notification service errors."""
    pass


class NotificationDeliveryException(NotificationException):
    """Raised when notification delivery fails."""
    pass


class InvalidNotificationTokenException(NotificationException):
    """Raised when a push notification token is invalid."""
    
    def __init__(self, token_id: str, provider: str, message: str = None):
        message = message or f"Invalid {provider} token: {token_id}"
        super().__init__(message, {"token_id": token_id, "provider": provider})


class EmailDeliveryException(NotificationDeliveryException):
    """Raised when email delivery fails."""
    pass


class SMSDeliveryException(NotificationDeliveryException):
    """Raised when SMS delivery fails."""
    pass


class PushNotificationException(NotificationDeliveryException):
    """Raised when push notification delivery fails."""
    pass


class WebhookDeliveryException(NotificationDeliveryException):
    """Raised when webhook delivery fails."""
    
    def __init__(self, url: str, status_code: Optional[int] = None, message: str = None):
        message = message or f"Webhook delivery failed to {url}"
        details = {"url": url}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details)


class TemplateProcessingException(NotificationException):
    """Raised when template processing fails."""
    pass


class ExternalAPIException(ServiceException):
    """Base exception for external API errors."""
    pass


class APIValidationException(ExternalAPIException):
    """Raised when API credential validation fails."""
    
    def __init__(self, provider: str, message: str, error_code: Optional[str] = None):
        super().__init__(message, {"provider": provider, "error_code": error_code})


class APIConnectionException(ExternalAPIException):
    """Raised when API connection fails."""
    pass


class APIRateLimitException(ExternalAPIException):
    """Raised when API rate limit is exceeded."""
    
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded for {provider}"
        details = {"provider": provider}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details)


class ChartGenerationException(ServiceException):
    """Raised when chart generation fails."""
    pass


class PDFGenerationException(ServiceException):
    """Raised when PDF generation fails."""
    pass


class CronParsingException(ServiceException):
    """Raised when cron expression parsing fails."""
    
    def __init__(self, expression: str, message: str = None):
        message = message or f"Invalid cron expression: {expression}"
        super().__init__(message, {"expression": expression})


class VideoTranscodingException(ServiceException):
    """Raised when video transcoding fails."""
    
    def __init__(self, file_path: str, message: str = None, error_output: str = None):
        message = message or f"Video transcoding failed for {file_path}"
        details = {"file_path": file_path}
        if error_output:
            details["error_output"] = error_output
        super().__init__(message, details)


class ScheduledTaskException(ServiceException):
    """Raised when scheduled task execution fails."""
    pass


class TaskExecutionException(ScheduledTaskException):
    """Raised when task execution fails."""
    
    def __init__(self, task_id: str, task_type: str, message: str = None):
        message = message or f"Task execution failed: {task_type} (ID: {task_id})"
        super().__init__(message, {"task_id": task_id, "task_type": task_type})