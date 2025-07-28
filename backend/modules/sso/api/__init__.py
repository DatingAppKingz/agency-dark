"""
SSO API Module
"""
from .endpoints import router
from .scim_endpoints import router as scim_router

__all__ = ['router', 'scim_router']