"""
Internationalization (i18n) module
"""
from .translations import (
    TranslationManager,
    translation_manager,
    _,
    _t,
    _n,
    i18n,
    SUPPORTED_LANGUAGES,
    get_language_from_request,
    set_current_language
)
from .middleware import I18nMiddleware
from .locale_detector import LocaleDetector

__all__ = [
    "TranslationManager",
    "translation_manager",
    "_",
    "_t",
    "_n",
    "i18n",
    "SUPPORTED_LANGUAGES",
    "get_language_from_request",
    "set_current_language",
    "I18nMiddleware",
    "LocaleDetector"
]