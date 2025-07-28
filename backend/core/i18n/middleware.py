"""
i18n middleware for handling locale detection and setting
"""
from typing import Callable, Optional
from fastapi import Request, Response
from contextvars import ContextVar

from core.i18n.translations import translation_manager
from core.i18n.locale_detector import LocaleDetector
from core.logging import get_logger

logger = get_logger(__name__)

# Context variable for storing current locale
current_locale: ContextVar[str] = ContextVar("current_locale", default="en")


class I18nMiddleware:
    """Middleware for internationalization support"""
    
    def __init__(
        self,
        app,
        default_locale: str = "en",
        locale_detector: Optional[LocaleDetector] = None
    ):
        self.app = app
        self.default_locale = default_locale
        self.locale_detector = locale_detector or LocaleDetector()
        
        # Update translation manager's default locale
        translation_manager.default_locale = default_locale
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Detect locale
        locale = self.locale_detector.detect_locale(request)
        
        # Validate locale
        if locale not in translation_manager.supported_locales:
            locale = self.default_locale
        
        # Set locale in context
        token = current_locale.set(locale)
        
        # Add locale to request state
        request.state.locale = locale
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add locale header to response
            response.headers["Content-Language"] = locale
            
            return response
        finally:
            # Reset context
            current_locale.reset(token)


def get_current_locale() -> str:
    """Get the current locale from context"""
    return current_locale.get()


def set_locale(locale: str):
    """Set the current locale in context"""
    if locale in translation_manager.supported_locales:
        current_locale.set(locale)
    else:
        logger.warning(f"Unsupported locale: {locale}")


# Update LazyTranslation to use context locale
def patch_lazy_translation():
    """Patch LazyTranslation to use context locale"""
    from core.i18n.translations import LazyTranslation
    
    original_get_locale = LazyTranslation._get_current_locale
    
    def _get_current_locale(self) -> str:
        """Get current locale from context"""
        try:
            return get_current_locale()
        except Exception:
            return original_get_locale(self)
    
    LazyTranslation._get_current_locale = _get_current_locale


# Apply patch on import
patch_lazy_translation()