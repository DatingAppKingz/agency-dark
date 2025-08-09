"""Translation API endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import json

from core.database import get_db
from core.dependencies import get_current_active_user
from core.security_v2.authorization import check_permission
from core.i18n import i18n, SUPPORTED_LANGUAGES, get_language_from_request, _
from services.translation_service import TranslationService
from models.user import User
from models.translation import Translation, ModelTranslation, TranslationRequest, LanguagePreference
from schemas.translation import (
    TranslationCreate, TranslationUpdate, TranslationResponse, TranslationBulkCreate,
    ModelTranslationCreate, ModelTranslationResponse,
    LanguagePreferenceUpdate, LanguagePreferenceResponse,
    TranslationRequestCreate, TranslationRequestResponse,
    LanguageInfo, TranslationStats, TranslationExport, TranslationImport
)
from core.logger import get_logger
from fastapi import Request

logger = get_logger(__name__)

router = APIRouter(prefix="/translations", tags=["translations"])


@router.get("/languages", response_model=List[LanguageInfo])
async def get_supported_languages(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get list of supported languages."""
    languages = []
    
    for code, name in SUPPORTED_LANGUAGES.items():
        locale_info = i18n.get_locale_info(code)
        languages.append(LanguageInfo(**locale_info))
    
    return languages


@router.get("/current", response_model=Dict[str, str])
async def get_current_language(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get current language from request."""
    lang = get_language_from_request(request)
    return {
        "language": lang,
        "name": SUPPORTED_LANGUAGES.get(lang, lang),
        "rtl": str(i18n.is_rtl(lang)).lower()
    }


# Translation CRUD
@router.post("", response_model=TranslationResponse)
async def create_translation(
    translation_data: TranslationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new translation.
    
    Permissions:
    - translations:create
    """
    check_permission(current_user, "translations", "create")
    
    service = TranslationService(db)
    translation = await service.create_translation(
        translation_data,
        verified_by=str(current_user.id) if translation_data.is_verified else None
    )
    
    return TranslationResponse.from_orm(translation)


@router.post("/bulk", response_model=List[TranslationResponse])
async def bulk_create_translations(
    bulk_data: TranslationBulkCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk create translations.
    
    Permissions:
    - translations:create
    """
    check_permission(current_user, "translations", "create")
    
    service = TranslationService(db)
    translations = await service.bulk_create_translations(
        bulk_data,
        verified_by=str(current_user.id)
    )
    
    return [TranslationResponse.from_orm(t) for t in translations]


@router.get("", response_model=List[TranslationResponse])
async def list_translations(
    language: Optional[str] = Query(None),
    context: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List translations.
    
    Permissions:
    - translations:read
    """
    check_permission(current_user, "translations", "read")
    
    query = select(Translation)
    
    # Apply filters
    if language:
        query = query.where(Translation.language == language)
    if context:
        query = query.where(Translation.context == context)
    if verified is not None:
        query = query.where(Translation.is_verified == verified)
    if search:
        query = query.where(
            Translation.key.ilike(f"%{search}%") |
            Translation.value.ilike(f"%{search}%")
        )
    
    # Paginate
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    translations = result.scalars().all()
    
    return [TranslationResponse.from_orm(t) for t in translations]


@router.get("/{translation_id}", response_model=TranslationResponse)
async def get_translation(
    translation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get translation by ID.
    
    Permissions:
    - translations:read
    """
    check_permission(current_user, "translations", "read")
    
    translation = await db.get(Translation, translation_id)
    
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found"
        )
    
    return TranslationResponse.from_orm(translation)


@router.patch("/{translation_id}", response_model=TranslationResponse)
async def update_translation(
    translation_id: str,
    update_data: TranslationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update translation.
    
    Permissions:
    - translations:update
    """
    check_permission(current_user, "translations", "update")
    
    translation = await db.get(Translation, translation_id)
    
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(translation, field, value)
    
    if update_data.is_verified:
        translation.verified_by = current_user.id
    
    await db.commit()
    await db.refresh(translation)
    
    return TranslationResponse.from_orm(translation)


@router.delete("/{translation_id}")
async def delete_translation(
    translation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete translation.
    
    Permissions:
    - translations:delete
    """
    check_permission(current_user, "translations", "delete")
    
    translation = await db.get(Translation, translation_id)
    
    if not translation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found"
        )
    
    await db.delete(translation)
    await db.commit()
    
    return {"message": "Translation deleted successfully"}


# Model translations
@router.post("/models", response_model=ModelTranslationResponse)
async def create_model_translation(
    translation_data: ModelTranslationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create model field translation.
    
    Permissions:
    - translations:create
    """
    check_permission(current_user, "translations", "create")
    
    service = TranslationService(db)
    translation = await service.create_model_translation(translation_data)
    
    return ModelTranslationResponse.from_orm(translation)


@router.get("/models", response_model=List[ModelTranslationResponse])
async def list_model_translations(
    model_name: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    field_name: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List model translations.
    
    Permissions:
    - translations:read
    """
    check_permission(current_user, "translations", "read")
    
    query = select(ModelTranslation)
    
    # Apply filters
    if model_name:
        query = query.where(ModelTranslation.model_name == model_name)
    if model_id:
        query = query.where(ModelTranslation.model_id == model_id)
    if field_name:
        query = query.where(ModelTranslation.field_name == field_name)
    if language:
        query = query.where(ModelTranslation.language == language)
    
    # Paginate
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    translations = result.scalars().all()
    
    return [ModelTranslationResponse.from_orm(t) for t in translations]


# Language preferences
@router.get("/preferences", response_model=LanguagePreferenceResponse)
async def get_language_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's language preferences."""
    result = await db.execute(
        select(LanguagePreference).where(
            LanguagePreference.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        # Create default preferences
        preferences = LanguagePreference(
            user_id=current_user.id,
            primary_language=current_user.language or "en",
            auto_translate=True,
            show_original=False,
            currency="USD",
            timezone="UTC"
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    
    return LanguagePreferenceResponse.from_orm(preferences)


@router.patch("/preferences", response_model=LanguagePreferenceResponse)
async def update_language_preferences(
    update_data: LanguagePreferenceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update language preferences."""
    # Get or create preferences
    result = await db.execute(
        select(LanguagePreference).where(
            LanguagePreference.user_id == current_user.id
        )
    )
    preferences = result.scalar_one_or_none()
    
    if not preferences:
        preferences = LanguagePreference(user_id=current_user.id)
        db.add(preferences)
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(preferences, field, value)
    
    # Update user's primary language
    if update_data.primary_language:
        current_user.language = update_data.primary_language
    
    await db.commit()
    await db.refresh(preferences)
    
    return LanguagePreferenceResponse.from_orm(preferences)


# Translation requests
@router.post("/requests", response_model=TranslationRequestResponse)
async def create_translation_request(
    request_data: TranslationRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create translation request.
    
    Permissions:
    - translation_requests:create
    """
    check_permission(current_user, "translation_requests", "create")
    
    service = TranslationService(db)
    translation_request = await service.create_translation_request(
        request_data,
        str(current_user.id),
        str(current_user.agency_id)
    )
    
    return TranslationRequestResponse.from_orm(translation_request)


@router.get("/requests", response_model=List[TranslationRequestResponse])
async def list_translation_requests(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List translation requests.
    
    Permissions:
    - translation_requests:read
    """
    check_permission(current_user, "translation_requests", "read")
    
    query = select(TranslationRequest).where(
        TranslationRequest.agency_id == current_user.agency_id
    )
    
    # Apply filters
    if status:
        query = query.where(TranslationRequest.status == status)
    if priority:
        query = query.where(TranslationRequest.priority == priority)
    if language:
        query = query.where(TranslationRequest.target_language == language)
    
    # Order by priority and date
    query = query.order_by(
        TranslationRequest.priority.desc(),
        TranslationRequest.requested_at.asc()
    )
    
    # Paginate
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    requests = result.scalars().all()
    
    return [TranslationRequestResponse.from_orm(r) for r in requests]


@router.post("/requests/{request_id}/complete", response_model=TranslationRequestResponse)
async def complete_translation_request(
    request_id: str,
    translated_text: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete translation request.
    
    Permissions:
    - translation_requests:update
    """
    check_permission(current_user, "translation_requests", "update")
    
    service = TranslationService(db)
    translation_request = await service.complete_translation_request(
        request_id,
        translated_text,
        str(current_user.id)
    )
    
    return TranslationRequestResponse.from_orm(translation_request)


# Missing translations
@router.get("/missing/{language}", response_model=List[Dict[str, Any]])
async def get_missing_translations(
    language: str,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get missing translations for a language.
    
    Permissions:
    - translations:read
    """
    check_permission(current_user, "translations", "read")
    
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language"
        )
    
    service = TranslationService(db)
    missing = await service.get_missing_translations(language, limit)
    
    return missing


# Auto-translate
@router.post("/auto-translate", response_model=Dict[str, str])
async def auto_translate(
    text: str,
    target_language: str,
    source_language: str = "en",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-translate text.
    
    Permissions:
    - translations:create
    """
    check_permission(current_user, "translations", "create")
    
    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported target language"
        )
    
    service = TranslationService(db)
    translated = await service.auto_translate(
        text,
        target_language,
        source_language
    )
    
    return {
        "source_language": source_language,
        "target_language": target_language,
        "source_text": text,
        "translated_text": translated
    }


# Statistics
@router.get("/stats", response_model=TranslationStats)
async def get_translation_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get translation statistics.
    
    Permissions:
    - translations:stats
    """
    check_permission(current_user, "translations", "stats")
    
    service = TranslationService(db)
    stats = await service.get_translation_stats()
    
    # Calculate totals
    total_keys = len(set())
    total_translations = 0
    languages_complete = []
    languages_incomplete = []
    
    for lang, data in stats.items():
        total_translations += data["total"]
        if data["percentage"] >= 90:
            languages_complete.append(lang)
        else:
            languages_incomplete.append(lang)
    
    return TranslationStats(
        stats=stats,
        total_keys=total_keys,
        total_translations=total_translations,
        languages_complete=languages_complete,
        languages_incomplete=languages_incomplete
    )


# Export/Import
@router.get("/export/{language}", response_model=TranslationExport)
async def export_translations(
    language: str,
    format: str = Query("json", pattern="^(json|po)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export translations for a language.
    
    Permissions:
    - translations:export
    """
    check_permission(current_user, "translations", "export")
    
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language"
        )
    
    service = TranslationService(db)
    export_data = await service.export_translations(language, format)
    
    if format == "json":
        return TranslationExport(
            language=language,
            format=format,
            translations=export_data,
            count=len(export_data)
        )
    else:
        return TranslationExport(
            language=language,
            format=format,
            content=export_data["content"],
            count=export_data.get("count", 0)
        )


@router.post("/import", response_model=Dict[str, Any])
async def import_translations(
    import_data: TranslationImport,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import translations for a language.
    
    Permissions:
    - translations:import
    """
    check_permission(current_user, "translations", "import")
    
    if import_data.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language"
        )
    
    service = TranslationService(db)
    count = await service.import_translations(
        import_data.language,
        import_data.translations,
        import_data.verified,
        str(current_user.id) if import_data.verified else None
    )
    
    return {
        "language": import_data.language,
        "imported": count,
        "verified": import_data.verified
    }


@router.post("/import/file", response_model=Dict[str, Any])
async def import_translations_file(
    language: str,
    file: UploadFile = File(...),
    verified: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Import translations from file.
    
    Permissions:
    - translations:import
    """
    check_permission(current_user, "translations", "import")
    
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language"
        )
    
    # Read file content
    content = await file.read()
    
    try:
        # Parse JSON
        translations = json.loads(content)
        
        if not isinstance(translations, dict):
            raise ValueError("Invalid file format")
        
        service = TranslationService(db)
        count = await service.import_translations(
            language,
            translations,
            verified,
            str(current_user.id) if verified else None
        )
        
        return {
            "language": language,
            "imported": count,
            "verified": verified,
            "filename": file.filename
        }
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )