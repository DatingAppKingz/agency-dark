"""Logging configuration for structured logging."""

import logging
import logging.config
import sys
from core.config import settings
from core.logging_context import JSONFormatter


def configure_structured_logging():
    """Configure structured logging for the application."""
    
    # Determine log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if settings.LOG_FORMAT == "json" else "standard",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console"],
                "level": log_level,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": logging.WARNING,  # Reduce access log verbosity
                "propagate": False,
            },
            "sqlalchemy": {
                "handlers": ["console"],
                "level": logging.WARNING,  # Reduce SQLAlchemy verbosity
                "propagate": False,
            },
            "httpx": {
                "handlers": ["console"],
                "level": logging.WARNING,  # Reduce httpx verbosity
                "propagate": False,
            },
        },
    }
    
    # Add file handler if configured
    if settings.LOG_FILE:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": settings.LOG_FILE,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }
        logging_config["loggers"][""]["handlers"].append("file")
    
    # Apply configuration
    logging.config.dictConfig(logging_config)
    
    # Log configuration complete
    logger = logging.getLogger(__name__)
    logger.info(
        "Structured logging configured",
        extra={
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "log_file": settings.LOG_FILE,
            "environment": settings.ENVIRONMENT,
        }
    )