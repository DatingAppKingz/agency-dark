"""Internationalization middleware for FastAPI."""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.i18n import get_language_from_request, set_current_language, i18n
from core.logger import get_logger

logger = get_logger(__name__)


class I18nMiddleware(BaseHTTPMiddleware):
    """Middleware to handle internationalization."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and set the language context."""
        # Get language from request
        language = get_language_from_request(request)
        
        # Set current language for this request
        set_current_language(language)
        
        # Add language to request state
        request.state.language = language
        request.state.i18n = i18n
        
        # Process request
        response = await call_next(request)
        
        # Add language header to response
        response.headers["Content-Language"] = language
        
        return response