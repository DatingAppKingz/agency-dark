"""
Dependencies compatibility layer.
Maps the existing dependencies to the expected dependency structure.
"""

from core.database import get_db
from api.v1.endpoints.auth_simple import get_current_user

# Re-export dependencies
__all__ = ["get_db", "get_current_user"]