"""
Locale detection strategies
"""
import re
from typing import List, Optional
from fastapi import Request
from urllib.parse import parse_qs

from core.logging import get_logger

logger = get_logger(__name__)


class LocaleDetector:
    """Detect user's preferred locale from various sources"""
    
    def __init__(
        self,
        supported_locales: Optional[List[str]] = None,
        default_locale: str = "en"
    ):
        self.supported_locales = supported_locales or ["en", "es", "fr", "de", "zh", "ja"]
        self.default_locale = default_locale
        
        # Regex for parsing Accept-Language header
        self.accept_language_re = re.compile(
            r'([a-zA-Z]{2,3}(?:-[a-zA-Z]{2,3})?)'
            r'(?:;q=([0-9.]+))?'
        )
    
    def detect_locale(self, request: Request) -> str:
        """
        Detect locale from request using various strategies
        
        Priority order:
        1. Query parameter (?locale=xx)
        2. Cookie (locale=xx)
        3. User preference (if authenticated)
        4. Accept-Language header
        5. Default locale
        """
        # 1. Check query parameter
        locale = self._detect_from_query(request)
        if locale:
            return locale
        
        # 2. Check cookie
        locale = self._detect_from_cookie(request)
        if locale:
            return locale
        
        # 3. Check user preference
        locale = self._detect_from_user(request)
        if locale:
            return locale
        
        # 4. Check Accept-Language header
        locale = self._detect_from_header(request)
        if locale:
            return locale
        
        # 5. Return default
        return self.default_locale
    
    def _detect_from_query(self, request: Request) -> Optional[str]:
        """Detect locale from query parameter"""
        query_params = parse_qs(str(request.url.query))
        locale_params = query_params.get('locale', [])
        
        if locale_params:
            locale = locale_params[0]
            if self._is_supported(locale):
                return locale
        
        return None
    
    def _detect_from_cookie(self, request: Request) -> Optional[str]:
        """Detect locale from cookie"""
        locale = request.cookies.get('locale')
        
        if locale and self._is_supported(locale):
            return locale
        
        return None
    
    def _detect_from_user(self, request: Request) -> Optional[str]:
        """Detect locale from authenticated user preference"""
        # Check if user is authenticated
        user = getattr(request.state, 'user', None)
        
        if user and hasattr(user, 'preferred_locale'):
            locale = user.preferred_locale
            if locale and self._is_supported(locale):
                return locale
        
        return None
    
    def _detect_from_header(self, request: Request) -> Optional[str]:
        """Detect locale from Accept-Language header"""
        accept_language = request.headers.get('accept-language', '')
        
        if not accept_language:
            return None
        
        # Parse Accept-Language header
        languages = self._parse_accept_language(accept_language)
        
        # Find best match
        for lang, _ in languages:
            # Try exact match
            if lang in self.supported_locales:
                return lang
            
            # Try language part only (e.g., 'en' from 'en-US')
            lang_part = lang.split('-')[0]
            if lang_part in self.supported_locales:
                return lang_part
            
            # Try to find locale that starts with language
            for supported in self.supported_locales:
                if supported.startswith(lang_part):
                    return supported
        
        return None
    
    def _parse_accept_language(
        self,
        accept_language: str
    ) -> List[tuple[str, float]]:
        """
        Parse Accept-Language header
        
        Returns list of (language, quality) tuples sorted by quality
        """
        languages = []
        
        for match in self.accept_language_re.finditer(accept_language):
            lang = match.group(1)
            quality = float(match.group(2) or 1.0)
            languages.append((lang.lower(), quality))
        
        # Sort by quality (descending)
        languages.sort(key=lambda x: x[1], reverse=True)
        
        return languages
    
    def _is_supported(self, locale: str) -> bool:
        """Check if locale is supported"""
        return locale in self.supported_locales
    
    def get_best_match(
        self,
        requested_locales: List[str]
    ) -> Optional[str]:
        """Get best matching locale from requested list"""
        for locale in requested_locales:
            if self._is_supported(locale):
                return locale
            
            # Try language part
            lang_part = locale.split('-')[0]
            if self._is_supported(lang_part):
                return lang_part
            
            # Try to find locale that starts with language
            for supported in self.supported_locales:
                if supported.startswith(lang_part):
                    return supported
        
        return None
    
    def normalize_locale(self, locale: str) -> str:
        """
        Normalize locale code
        
        Examples:
        - en_US -> en-US
        - EN -> en
        """
        # Replace underscores with hyphens
        locale = locale.replace('_', '-')
        
        # Split into parts
        parts = locale.split('-')
        
        # Lowercase language part
        if parts:
            parts[0] = parts[0].lower()
        
        # Uppercase country part
        if len(parts) > 1:
            parts[1] = parts[1].upper()
        
        return '-'.join(parts)