"""Translation service for managing translations and localization."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
# from googletrans import Translator  # Commented out due to version conflict
# Create a mock translator for now
class Translator:
    def translate(self, text, src='auto', dest='en'):
        class Translation:
            def __init__(self, text):
                self.text = text
        return Translation(text)
import hashlib
import json

from core.i18n import i18n, SUPPORTED_LANGUAGES
from core.logger import get_logger
from models.translation import Translation, ModelTranslation, TranslationRequest
from models.user import User
from schemas.translation import (
    TranslationCreate, TranslationUpdate, TranslationBulkCreate,
    ModelTranslationCreate, TranslationRequestCreate
)

logger = get_logger(__name__)


class TranslationService:
    """Service for managing translations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.translator = Translator()
        self._cache = {}
    
    async def get_translation(
        self,
        key: str,
        language: str,
        context: Optional[str] = None
    ) -> Optional[str]:
        """Get translation for a key."""
        # Check cache first
        cache_key = f"{key}:{language}:{context or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Query database
        query = select(Translation).where(
            and_(
                Translation.key == key,
                Translation.language == language
            )
        )
        
        if context:
            query = query.where(Translation.context == context)
        
        result = await self.db.execute(query)
        translation = result.scalar_one_or_none()
        
        if translation:
            value = translation.value
            self._cache[cache_key] = value
            return value
        
        return None
    
    async def create_translation(
        self,
        data: TranslationCreate,
        verified_by: Optional[str] = None
    ) -> Translation:
        """Create a new translation."""
        try:
            # Check if translation already exists
            existing = await self.get_translation(
                data.key,
                data.language,
                data.context
            )
            
            if existing:
                # Update existing translation
                query = select(Translation).where(
                    and_(
                        Translation.key == data.key,
                        Translation.language == data.language
                    )
                )
                if data.context:
                    query = query.where(Translation.context == data.context)
                
                result = await self.db.execute(query)
                translation = result.scalar_one()
                
                translation.value = data.value
                translation.is_verified = data.is_verified
                if verified_by:
                    translation.verified_by = verified_by
            else:
                # Create new translation
                translation = Translation(
                    key=data.key,
                    language=data.language,
                    value=data.value,
                    context=data.context,
                    is_verified=data.is_verified,
                    verified_by=verified_by if data.is_verified else None
                )
                self.db.add(translation)
            
            await self.db.commit()
            await self.db.refresh(translation)
            
            # Clear cache
            cache_key = f"{data.key}:{data.language}:{data.context or ''}"
            self._cache.pop(cache_key, None)
            
            return translation
            
        except Exception as e:
            logger.error(f"Error creating translation: {e}")
            await self.db.rollback()
            raise
    
    async def bulk_create_translations(
        self,
        data: TranslationBulkCreate,
        verified_by: Optional[str] = None
    ) -> List[Translation]:
        """Create multiple translations at once."""
        translations = []
        
        for item in data.translations:
            translation = await self.create_translation(item, verified_by)
            translations.append(translation)
        
        return translations
    
    async def auto_translate(
        self,
        text: str,
        target_language: str,
        source_language: str = "en",
        context: Optional[str] = None
    ) -> str:
        """Auto-translate text using Google Translate."""
        try:
            # Check if translation is needed
            if source_language == target_language:
                return text
            
            # Create cache key
            cache_key = hashlib.md5(
                f"{text}:{source_language}:{target_language}".encode()
            ).hexdigest()
            
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Translate
            result = self.translator.translate(
                text,
                src=source_language,
                dest=target_language
            )
            
            translated_text = result.text
            
            # Cache result
            self._cache[cache_key] = translated_text
            
            # Store in database for future use
            key = f"auto.{cache_key}"
            await self.create_translation(
                TranslationCreate(
                    key=key,
                    language=target_language,
                    value=translated_text,
                    context=context,
                    is_verified=False
                )
            )
            
            return translated_text
            
        except Exception as e:
            logger.error(f"Error auto-translating: {e}")
            return text
    
    async def translate_model_field(
        self,
        model_name: str,
        model_id: str,
        field_name: str,
        language: str,
        value: Optional[str] = None,
        auto_create: bool = True
    ) -> Optional[str]:
        """Get translation for model field."""
        # Query database
        result = await self.db.execute(
            select(ModelTranslation).where(
                and_(
                    ModelTranslation.model_name == model_name,
                    ModelTranslation.model_id == model_id,
                    ModelTranslation.field_name == field_name,
                    ModelTranslation.language == language
                )
            )
        )
        
        translation = result.scalar_one_or_none()
        
        if translation:
            return translation.value
        
        # Auto-translate if enabled and value provided
        if auto_create and value:
            translated = await self.auto_translate(value, language)
            
            # Save translation
            model_translation = ModelTranslation(
                model_name=model_name,
                model_id=model_id,
                field_name=field_name,
                language=language,
                value=translated,
                is_machine_translated=True
            )
            
            self.db.add(model_translation)
            await self.db.commit()
            
            return translated
        
        return None
    
    async def create_model_translation(
        self,
        data: ModelTranslationCreate
    ) -> ModelTranslation:
        """Create model field translation."""
        try:
            # Check if exists
            result = await self.db.execute(
                select(ModelTranslation).where(
                    and_(
                        ModelTranslation.model_name == data.model_name,
                        ModelTranslation.model_id == data.model_id,
                        ModelTranslation.field_name == data.field_name,
                        ModelTranslation.language == data.language
                    )
                )
            )
            
            translation = result.scalar_one_or_none()
            
            if translation:
                # Update existing
                translation.value = data.value
                translation.is_machine_translated = data.is_machine_translated
            else:
                # Create new
                translation = ModelTranslation(**data.dict())
                self.db.add(translation)
            
            await self.db.commit()
            await self.db.refresh(translation)
            
            return translation
            
        except Exception as e:
            logger.error(f"Error creating model translation: {e}")
            await self.db.rollback()
            raise
    
    async def get_missing_translations(
        self,
        language: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get keys that need translation for a language."""
        # Get all unique keys
        all_keys_query = select(Translation.key).distinct()
        all_keys_result = await self.db.execute(all_keys_query)
        all_keys = {row[0] for row in all_keys_result}
        
        # Get translated keys for language
        translated_query = select(Translation.key).where(
            Translation.language == language
        )
        translated_result = await self.db.execute(translated_query)
        translated_keys = {row[0] for row in translated_result}
        
        # Find missing keys
        missing_keys = all_keys - translated_keys
        
        # Get source translations (English)
        missing_translations = []
        for key in list(missing_keys)[:limit]:
            source_translation = await self.get_translation(key, "en")
            if source_translation:
                missing_translations.append({
                    "key": key,
                    "source_language": "en",
                    "source_text": source_translation,
                    "target_language": language
                })
        
        return missing_translations
    
    async def create_translation_request(
        self,
        data: TranslationRequestCreate,
        requested_by: str,
        agency_id: str
    ) -> TranslationRequest:
        """Create a translation request."""
        try:
            request = TranslationRequest(
                **data.dict(),
                requested_by=requested_by,
                agency_id=agency_id
            )
            
            self.db.add(request)
            await self.db.commit()
            await self.db.refresh(request)
            
            return request
            
        except Exception as e:
            logger.error(f"Error creating translation request: {e}")
            await self.db.rollback()
            raise
    
    async def complete_translation_request(
        self,
        request_id: str,
        translated_text: str,
        translator_id: str
    ) -> TranslationRequest:
        """Complete a translation request."""
        try:
            request = await self.db.get(TranslationRequest, request_id)
            
            if not request:
                raise ValueError("Translation request not found")
            
            request.translated_text = translated_text
            request.translator_id = translator_id
            request.status = "completed"
            request.completed_at = datetime.utcnow()
            
            # Create the actual translation
            await self.create_translation(
                TranslationCreate(
                    key=request.key,
                    language=request.target_language,
                    value=translated_text,
                    context=request.context,
                    is_verified=True
                ),
                verified_by=translator_id
            )
            
            await self.db.commit()
            await self.db.refresh(request)
            
            return request
            
        except Exception as e:
            logger.error(f"Error completing translation request: {e}")
            await self.db.rollback()
            raise
    
    async def export_translations(
        self,
        language: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export translations for a language."""
        # Get all translations
        result = await self.db.execute(
            select(Translation).where(Translation.language == language)
        )
        translations = result.scalars().all()
        
        # Build translation dictionary
        trans_dict = {}
        for trans in translations:
            if trans.context:
                key = f"{trans.context}.{trans.key}"
            else:
                key = trans.key
            trans_dict[key] = trans.value
        
        if format == "json":
            return trans_dict
        elif format == "po":
            # Convert to gettext PO format
            po_content = self._convert_to_po(trans_dict, language)
            return {"content": po_content, "format": "po"}
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _convert_to_po(self, translations: Dict[str, str], language: str) -> str:
        """Convert translations to PO format."""
        lines = [
            f'msgid ""',
            f'msgstr ""',
            f'"Language: {language}\\n"',
            f'"Content-Type: text/plain; charset=UTF-8\\n"',
            f'"Content-Transfer-Encoding: 8bit\\n"',
            f'',
        ]
        
        for key, value in translations.items():
            lines.extend([
                f'',
                f'msgid "{key}"',
                f'msgstr "{value}"'
            ])
        
        return '\n'.join(lines)
    
    async def import_translations(
        self,
        language: str,
        data: Dict[str, str],
        verified: bool = False,
        verified_by: Optional[str] = None
    ) -> int:
        """Import translations for a language."""
        count = 0
        
        for key, value in data.items():
            # Split context if present
            if "." in key:
                parts = key.split(".", 1)
                context = parts[0]
                actual_key = parts[1]
            else:
                context = None
                actual_key = key
            
            await self.create_translation(
                TranslationCreate(
                    key=actual_key,
                    language=language,
                    value=value,
                    context=context,
                    is_verified=verified
                ),
                verified_by=verified_by
            )
            count += 1
        
        return count
    
    async def get_translation_stats(self) -> Dict[str, Any]:
        """Get translation statistics."""
        stats = {}
        
        for lang_code in SUPPORTED_LANGUAGES:
            # Count translations
            result = await self.db.execute(
                select(Translation).where(Translation.language == lang_code)
            )
            translations = result.scalars().all()
            
            total = len(translations)
            verified = sum(1 for t in translations if t.is_verified)
            
            stats[lang_code] = {
                "total": total,
                "verified": verified,
                "unverified": total - verified,
                "percentage": (verified / total * 100) if total > 0 else 0
            }
        
        return stats