"""
Simple logging module for backward compatibility
"""
import logging
import sys

def get_logger(name: str):
    """Get a simple logger instance"""
    logger = logging.getLogger(name)
    
    # Configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger

# Create a default logger instance for backward compatibility
logger = get_logger(__name__)

__all__ = ['get_logger', 'logger']