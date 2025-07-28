"""
Background tasks module for async operations.
"""

# Import all tasks to register them
from .email_tasks import *
from .sync_tasks import *
from .analytics_tasks import *
from .cleanup_tasks import *
from .ml_tasks import *
from .report_tasks import *
from .notification_tasks import *
from .callbacks import *