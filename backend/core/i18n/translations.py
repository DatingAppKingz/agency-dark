"""
Internationalization (i18n) support for multi-language functionality
"""
import json
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from functools import lru_cache
import yaml
from babel import Locale
from babel.support import Translations as BabelTranslations

from core.config import settings
from core.logger import get_logger

# settings already imported
logger = get_logger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = [
    "en",  # English
    "es",  # Spanish
    "fr",  # French
    "de",  # German
    "it",  # Italian
    "pt",  # Portuguese
    "ru",  # Russian
    "zh",  # Chinese
    "ja",  # Japanese
    "ko",  # Korean
]


class TranslationManager:
    """Manage translations for multiple languages"""
    
    def __init__(self, translations_dir: str = None):
        self.translations_dir = Path(translations_dir or "translations")
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.supported_locales: List[str] = []
        self.default_locale = "en"
        self._babel_translations: Dict[str, BabelTranslations] = {}
        
        # Load translations on initialization
        self.load_translations()
    
    def load_translations(self):
        """Load all translation files"""
        if not self.translations_dir.exists():
            logger.warning(f"Translations directory not found: {self.translations_dir}")
            return
        
        # Load each locale directory
        for locale_dir in self.translations_dir.iterdir():
            if locale_dir.is_dir():
                locale_code = locale_dir.name
                self.supported_locales.append(locale_code)
                
                # Load JSON translations
                json_file = locale_dir / "messages.json"
                if json_file.exists():
                    with open(json_file, 'r', encoding='utf-8') as f:
                        self.translations[locale_code] = json.load(f)
                
                # Load YAML translations (alternative format)
                yaml_file = locale_dir / "messages.yaml"
                if yaml_file.exists():
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        yaml_data = yaml.safe_load(f)
                        if locale_code in self.translations:
                            self.translations[locale_code].update(yaml_data)
                        else:
                            self.translations[locale_code] = yaml_data
                
                # Load compiled .mo files for Babel
                mo_file = locale_dir / "LC_MESSAGES" / "messages.mo"
                if mo_file.exists():
                    self._babel_translations[locale_code] = BabelTranslations.load(
                        str(locale_dir),
                        domain='messages'
                    )
        
        logger.info(f"Loaded translations for locales: {self.supported_locales}")
    
    def get(
        self,
        key: str,
        locale: str = None,
        default: str = None,
        **kwargs
    ) -> str:
        """
        Get translated string
        
        Args:
            key: Translation key
            locale: Target locale
            default: Default value if translation not found
            **kwargs: Variables for string formatting
            
        Returns:
            Translated string
        """
        locale = locale or self.default_locale
        
        # Get translation
        translation = self._get_nested_value(
            self.translations.get(locale, {}),
            key
        )
        
        # Fallback to default locale
        if translation is None and locale != self.default_locale:
            translation = self._get_nested_value(
                self.translations.get(self.default_locale, {}),
                key
            )
        
        # Use default if provided
        if translation is None:
            translation = default or key
        
        # Format with variables
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError) as e:
                logger.warning(f"Translation formatting error: {e}")
        
        return translation
    
    def _get_nested_value(self, data: Dict, key: str) -> Optional[str]:
        """Get value from nested dictionary using dot notation"""
        keys = key.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    @lru_cache(maxsize=128)
    def get_locale_info(self, locale: str) -> Dict[str, Any]:
        """Get information about a locale"""
        try:
            babel_locale = Locale.parse(locale)
            return {
                "code": locale,
                "display_name": babel_locale.display_name,
                "english_name": babel_locale.english_name,
                "native_name": babel_locale.get_display_name(locale),
                "direction": "rtl" if babel_locale.text_direction == "rtl" else "ltr",
                "territory": babel_locale.territory,
                "language": babel_locale.language
            }
        except Exception as e:
            logger.error(f"Error parsing locale {locale}: {e}")
            return {"code": locale, "display_name": locale}
    
    def get_available_locales(self) -> List[Dict[str, Any]]:
        """Get list of available locales with metadata"""
        return [
            self.get_locale_info(locale)
            for locale in self.supported_locales
        ]
    
    def add_translation(
        self,
        key: str,
        translations: Dict[str, str],
        persist: bool = False
    ):
        """
        Add or update a translation
        
        Args:
            key: Translation key
            translations: Dict of locale -> translation
            persist: Whether to save to file
        """
        for locale, translation in translations.items():
            if locale not in self.translations:
                self.translations[locale] = {}
            
            # Set nested value
            self._set_nested_value(self.translations[locale], key, translation)
            
            if persist:
                self._save_translations(locale)
    
    def _set_nested_value(self, data: Dict, key: str, value: Any):
        """Set value in nested dictionary using dot notation"""
        keys = key.split('.')
        
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        
        data[keys[-1]] = value
    
    def _save_translations(self, locale: str):
        """Save translations to file"""
        locale_dir = self.translations_dir / locale
        locale_dir.mkdir(parents=True, exist_ok=True)
        
        json_file = locale_dir / "messages.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(
                self.translations[locale],
                f,
                ensure_ascii=False,
                indent=2
            )
    
    def format_number(
        self,
        number: Union[int, float],
        locale: str = None
    ) -> str:
        """Format number according to locale"""
        from babel.numbers import format_decimal
        
        locale = locale or self.default_locale
        return format_decimal(number, locale=locale)
    
    def format_currency(
        self,
        amount: float,
        currency: str,
        locale: str = None
    ) -> str:
        """Format currency according to locale"""
        from babel.numbers import format_currency as babel_format_currency
        
        locale = locale or self.default_locale
        return babel_format_currency(amount, currency, locale=locale)
    
    def format_date(
        self,
        date,
        format: str = "medium",
        locale: str = None
    ) -> str:
        """Format date according to locale"""
        from babel.dates import format_date as babel_format_date
        
        locale = locale or self.default_locale
        return babel_format_date(date, format=format, locale=locale)
    
    def format_datetime(
        self,
        datetime,
        format: str = "medium",
        locale: str = None,
        tzinfo=None
    ) -> str:
        """Format datetime according to locale"""
        from babel.dates import format_datetime as babel_format_datetime
        
        locale = locale or self.default_locale
        return babel_format_datetime(
            datetime,
            format=format,
            locale=locale,
            tzinfo=tzinfo
        )
    
    def format_time(
        self,
        time,
        format: str = "medium",
        locale: str = None
    ) -> str:
        """Format time according to locale"""
        from babel.dates import format_time as babel_format_time
        
        locale = locale or self.default_locale
        return babel_format_time(time, format=format, locale=locale)
    
    def format_relative_time(
        self,
        datetime,
        locale: str = None
    ) -> str:
        """Format relative time (e.g., '2 hours ago')"""
        from babel.dates import format_timedelta
        from datetime import datetime as dt
        
        locale = locale or self.default_locale
        delta = dt.now() - datetime
        
        return format_timedelta(delta, locale=locale, add_direction=True)
    
    def pluralize(
        self,
        key: str,
        count: int,
        locale: str = None,
        **kwargs
    ) -> str:
        """
        Get pluralized translation
        
        The translation should be a dict with keys: zero, one, few, many, other
        """
        locale = locale or self.default_locale
        
        # Get plural rules for locale
        babel_locale = Locale.parse(locale)
        plural_form = babel_locale.plural_form(count)
        
        # Get translation object
        translation_obj = self._get_nested_value(
            self.translations.get(locale, {}),
            key
        )
        
        if isinstance(translation_obj, dict):
            # Map Babel plural forms to common keys
            plural_map = {
                'zero': 'zero',
                'one': 'one',
                'two': 'few',
                'few': 'few',
                'many': 'many',
                'other': 'other'
            }
            
            plural_key = plural_map.get(plural_form.name, 'other')
            translation = translation_obj.get(plural_key, translation_obj.get('other', key))
        else:
            translation = translation_obj or key
        
        # Format with count and additional variables
        kwargs['count'] = count
        
        try:
            return translation.format(**kwargs)
        except (KeyError, ValueError):
            return translation


class LazyTranslation:
    """Lazy translation that evaluates when accessed"""
    
    def __init__(
        self,
        key: str,
        manager: TranslationManager,
        **kwargs
    ):
        self.key = key
        self.manager = manager
        self.kwargs = kwargs
    
    def __str__(self) -> str:
        """Evaluate translation when converted to string"""
        # Get locale from context (e.g., request context)
        locale = self._get_current_locale()
        return self.manager.get(self.key, locale=locale, **self.kwargs)
    
    def _get_current_locale(self) -> str:
        """Get current locale from context"""
        # This would typically get locale from request context
        # For now, return default
        return self.manager.default_locale


# Translation shortcuts
class TranslationShortcuts:
    """Convenient shortcuts for common translations"""
    
    def __init__(self, manager: TranslationManager):
        self.manager = manager
    
    def _(self, key: str, **kwargs) -> LazyTranslation:
        """Lazy translation shortcut"""
        return LazyTranslation(key, self.manager, **kwargs)
    
    def _t(self, key: str, locale: str = None, **kwargs) -> str:
        """Immediate translation shortcut"""
        return self.manager.get(key, locale=locale, **kwargs)
    
    def _n(self, key: str, count: int, locale: str = None, **kwargs) -> str:
        """Pluralized translation shortcut"""
        return self.manager.pluralize(key, count, locale=locale, **kwargs)


# Global translation manager
translation_manager = TranslationManager()

# Shortcuts
_ = TranslationShortcuts(translation_manager)._
_t = TranslationShortcuts(translation_manager)._t
_n = TranslationShortcuts(translation_manager)._n

# Create i18n alias for backward compatibility
i18n = translation_manager

# Helper function to get language from request
def get_language_from_request(request) -> str:
    """
    Get language from request headers or query params.
    
    Checks in order:
    1. Accept-Language header
    2. lang query parameter
    3. Default language
    """
    # Check query parameter first
    if hasattr(request, 'query_params') and 'lang' in request.query_params:
        lang = request.query_params['lang']
        if lang in SUPPORTED_LANGUAGES:
            return lang
    
    # Check Accept-Language header
    if hasattr(request, 'headers'):
        accept_language = request.headers.get('accept-language', '')
        # Parse the header and get the best match
        for lang in accept_language.split(','):
            lang_code = lang.split(';')[0].strip().split('-')[0]
            if lang_code in SUPPORTED_LANGUAGES:
                return lang_code
    
    # Return default
    return translation_manager.default_locale


# Thread-local storage for current language
import threading
_thread_local = threading.local()


def set_current_language(language: str):
    """
    Set the current language for the current thread/request.
    
    Args:
        language: Language code to set
    """
    if language not in SUPPORTED_LANGUAGES:
        language = translation_manager.default_locale
    _thread_local.language = language