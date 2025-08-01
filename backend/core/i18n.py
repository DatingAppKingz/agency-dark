"""Internationalization support for AgencyDark."""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from functools import lru_cache
import babel
from babel import Locale
from babel.support import Translations
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Default language
DEFAULT_LANGUAGE = "en"

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "ja": "日本語",
    "zh": "中文",
    "ar": "العربية",
}

# RTL languages
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

# Translation directory
TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"


class I18n:
    """Internationalization manager."""
    
    def __init__(self):
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.babel_translations: Dict[str, Translations] = {}
        self._load_translations()
    
    def _load_translations(self):
        """Load all translation files."""
        TRANSLATIONS_DIR.mkdir(exist_ok=True)
        
        for lang_code in SUPPORTED_LANGUAGES:
            lang_dir = TRANSLATIONS_DIR / lang_code
            if lang_dir.exists():
                # Load JSON translations
                json_file = lang_dir / "messages.json"
                if json_file.exists():
                    with open(json_file, "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                else:
                    self.translations[lang_code] = {}
                
                # Load Babel translations for pluralization
                mo_file = lang_dir / "LC_MESSAGES" / "messages.mo"
                if mo_file.exists():
                    self.babel_translations[lang_code] = Translations.load(
                        str(TRANSLATIONS_DIR),
                        [lang_code]
                    )
    
    def get_translation(
        self,
        key: str,
        lang: str = DEFAULT_LANGUAGE,
        **kwargs
    ) -> str:
        """Get translated string."""
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        
        # Get translation
        translations = self.translations.get(lang, {})
        translation = translations.get(key, key)
        
        # Format with variables
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing variable in translation: {e}")
        
        return translation
    
    def get_plural_translation(
        self,
        key: str,
        count: int,
        lang: str = DEFAULT_LANGUAGE,
        **kwargs
    ) -> str:
        """Get plural translation."""
        if lang not in self.babel_translations:
            return self.get_translation(f"{key}.{count}", lang, count=count, **kwargs)
        
        babel_trans = self.babel_translations[lang]
        
        # Get singular and plural forms
        singular = self.get_translation(f"{key}.singular", lang)
        plural = self.get_translation(f"{key}.plural", lang)
        
        # Use Babel for proper pluralization
        result = babel_trans.ngettext(singular, plural, count)
        
        # Format with variables
        kwargs["count"] = count
        try:
            result = result.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in plural translation: {e}")
        
        return result
    
    def get_available_languages(self) -> List[Dict[str, str]]:
        """Get list of available languages."""
        return [
            {
                "code": code,
                "name": name,
                "native_name": self.get_translation("language.native_name", code),
                "rtl": code in RTL_LANGUAGES
            }
            for code, name in SUPPORTED_LANGUAGES.items()
        ]
    
    def is_rtl(self, lang: str) -> bool:
        """Check if language is RTL."""
        return lang in RTL_LANGUAGES
    
    def format_date(
        self,
        date,
        format: str = "medium",
        lang: str = DEFAULT_LANGUAGE
    ) -> str:
        """Format date according to locale."""
        try:
            locale = Locale.parse(lang)
            return babel.dates.format_date(date, format=format, locale=locale)
        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return str(date)
    
    def format_datetime(
        self,
        datetime,
        format: str = "medium",
        lang: str = DEFAULT_LANGUAGE
    ) -> str:
        """Format datetime according to locale."""
        try:
            locale = Locale.parse(lang)
            return babel.dates.format_datetime(datetime, format=format, locale=locale)
        except Exception as e:
            logger.error(f"Error formatting datetime: {e}")
            return str(datetime)
    
    def format_currency(
        self,
        amount: float,
        currency: str = "USD",
        lang: str = DEFAULT_LANGUAGE
    ) -> str:
        """Format currency according to locale."""
        try:
            locale = Locale.parse(lang)
            return babel.numbers.format_currency(amount, currency, locale=locale)
        except Exception as e:
            logger.error(f"Error formatting currency: {e}")
            return f"{currency} {amount}"
    
    def format_number(
        self,
        number: float,
        lang: str = DEFAULT_LANGUAGE
    ) -> str:
        """Format number according to locale."""
        try:
            locale = Locale.parse(lang)
            return babel.numbers.format_decimal(number, locale=locale)
        except Exception as e:
            logger.error(f"Error formatting number: {e}")
            return str(number)
    
    def format_percent(
        self,
        number: float,
        lang: str = DEFAULT_LANGUAGE
    ) -> str:
        """Format percentage according to locale."""
        try:
            locale = Locale.parse(lang)
            return babel.numbers.format_percent(number, locale=locale)
        except Exception as e:
            logger.error(f"Error formatting percent: {e}")
            return f"{number * 100}%"


# Global instance
i18n = I18n()


# Helper functions
def _(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Translate string."""
    return i18n.get_translation(key, lang, **kwargs)


def _n(key: str, count: int, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Translate plural string."""
    return i18n.get_plural_translation(key, count, lang, **kwargs)


def get_language_from_request(request: Request) -> str:
    """Get language from request."""
    # 1. Check query parameter
    lang = request.query_params.get("lang")
    if lang and lang in SUPPORTED_LANGUAGES:
        return lang
    
    # 2. Check custom header
    lang = request.headers.get("X-Language")
    if lang and lang in SUPPORTED_LANGUAGES:
        return lang
    
    # 3. Check Accept-Language header
    accept_language = request.headers.get("Accept-Language", "")
    if accept_language:
        # Parse Accept-Language header
        languages = []
        for lang_range in accept_language.split(","):
            parts = lang_range.strip().split(";")
            lang = parts[0].split("-")[0].lower()
            if lang in SUPPORTED_LANGUAGES:
                return lang
    
    # 4. Check user preference (if authenticated)
    if hasattr(request.state, "user") and request.state.user:
        user_lang = getattr(request.state.user, "language", None)
        if user_lang and user_lang in SUPPORTED_LANGUAGES:
            return user_lang
    
    # 5. Default language
    return DEFAULT_LANGUAGE


class I18nMiddleware(BaseHTTPMiddleware):
    """Middleware to set request language."""
    
    async def dispatch(self, request: Request, call_next):
        # Get language for request
        lang = get_language_from_request(request)
        
        # Store in request state
        request.state.language = lang
        
        # Add to response headers
        response = await call_next(request)
        response.headers["Content-Language"] = lang
        
        return response


def create_translation_key(
    model: str,
    field: str,
    value: str,
    lang: str = DEFAULT_LANGUAGE
) -> str:
    """Create translation key for dynamic content."""
    return f"db.{model}.{field}.{value}"


def translate_model_field(
    model: Any,
    field: str,
    lang: str = DEFAULT_LANGUAGE
) -> str:
    """Translate model field."""
    # Get original value
    value = getattr(model, field, None)
    if not value:
        return ""
    
    # Check for translation
    if hasattr(model, f"{field}_translations"):
        translations = getattr(model, f"{field}_translations", {})
        if lang in translations:
            return translations[lang]
    
    # Check global translations
    key = create_translation_key(
        model.__class__.__name__.lower(),
        field,
        str(value),
        lang
    )
    
    translated = _(key, lang)
    if translated != key:
        return translated
    
    # Return original value
    return str(value)


@lru_cache(maxsize=1000)
def get_locale_info(lang: str) -> Dict[str, Any]:
    """Get locale information."""
    try:
        locale = Locale.parse(lang)
        return {
            "code": lang,
            "name": locale.english_name,
            "native_name": locale.get_display_name(locale),
            "rtl": lang in RTL_LANGUAGES,
            "decimal_symbol": locale.number_symbols.get("decimal", "."),
            "thousands_separator": locale.number_symbols.get("group", ","),
            "currency_symbol": locale.currency_symbols.get("USD", "$"),
            "date_format": locale.date_formats.get("medium", "MMM d, y"),
            "time_format": locale.time_formats.get("medium", "h:mm:ss a"),
            "first_week_day": locale.first_week_day,
        }
    except Exception as e:
        logger.error(f"Error getting locale info: {e}")
        return {
            "code": lang,
            "name": SUPPORTED_LANGUAGES.get(lang, lang),
            "rtl": lang in RTL_LANGUAGES
        }