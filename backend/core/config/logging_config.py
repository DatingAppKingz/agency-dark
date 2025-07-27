"""
Production logging configuration
"""
import os
import logging
import logging.config
from typing import Dict, Any


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', 'json')
    environment = os.getenv('ENVIRONMENT', 'development')
    
    # Base configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'json': {
                'format': '%(asctime)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
                'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'json_fields': [
                    'asctime', 'name', 'levelname', 'message',
                    'filename', 'lineno', 'funcName', 'process',
                    'thread', 'pathname', 'exc_info'
                ]
            },
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'filters': {
            'health_check': {
                '()': 'core.config.logging_config.HealthCheckFilter'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'json' if log_format == 'json' else 'default',
                'stream': 'ext://sys.stdout',
                'filters': ['health_check']
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'json' if log_format == 'json' else 'detailed',
                'filename': '/app/logs/app.log',
                'maxBytes': 104857600,  # 100MB
                'backupCount': 5,
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'filename': '/app/logs/error.log',
                'maxBytes': 52428800,  # 50MB
                'backupCount': 5,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'uvicorn': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'uvicorn.access': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'sqlalchemy': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'sqlalchemy.engine': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'alembic': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False
            },
            'app': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            },
            'core': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            },
            'api': {
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
                'propagate': False
            }
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': log_level
        }
    }
    
    # Production-specific configuration
    if environment == 'production':
        # Add Sentry handler if configured
        sentry_dsn = os.getenv('SENTRY_DSN')
        if sentry_dsn:
            config['handlers']['sentry'] = {
                'class': 'sentry_sdk.integrations.logging.SentryHandler',
                'level': 'ERROR'
            }
            # Add sentry handler to all loggers
            for logger in config['loggers'].values():
                if 'sentry' not in logger['handlers']:
                    logger['handlers'].append('sentry')
    
    return config


class HealthCheckFilter(logging.Filter):
    """Filter out health check logs to reduce noise"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter health check endpoints"""
        # Filter out health check access logs
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            if any(endpoint in msg for endpoint in ['/health', '/health/live', '/health/ready']):
                return False
        return True


class StructuredLogger:
    """Structured logging wrapper"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.hostname = os.getenv('HOSTNAME', 'unknown')
        self.environment = os.getenv('ENVIRONMENT', 'development')
        
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Add standard context to log entries"""
        return {
            **extra,
            'hostname': self.hostname,
            'environment': self.environment,
            'service': 'agencydark-backend'
        }
        
    def debug(self, msg: str, **kwargs):
        """Debug log with context"""
        extra = self._add_context(kwargs)
        self.logger.debug(msg, extra=extra)
        
    def info(self, msg: str, **kwargs):
        """Info log with context"""
        extra = self._add_context(kwargs)
        self.logger.info(msg, extra=extra)
        
    def warning(self, msg: str, **kwargs):
        """Warning log with context"""
        extra = self._add_context(kwargs)
        self.logger.warning(msg, extra=extra)
        
    def error(self, msg: str, exc_info=None, **kwargs):
        """Error log with context"""
        extra = self._add_context(kwargs)
        self.logger.error(msg, exc_info=exc_info, extra=extra)
        
    def critical(self, msg: str, exc_info=None, **kwargs):
        """Critical log with context"""
        extra = self._add_context(kwargs)
        self.logger.critical(msg, exc_info=exc_info, extra=extra)


def setup_logging():
    """Setup logging configuration"""
    config = get_logging_config()
    
    # Create log directory if it doesn't exist
    os.makedirs('/app/logs', exist_ok=True)
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Setup Sentry if configured
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv('ENVIRONMENT', 'development'),
            integrations=[
                sentry_logging,
                SqlalchemyIntegration(),
                AsyncioIntegration()
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,  # 10% of transactions
            attach_stacktrace=True,
            send_default_pii=False
        )


# Create logger instance
def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)