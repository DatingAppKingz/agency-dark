"""External API credential validation endpoints."""

from typing import Dict, Any, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from schemas.pagination import PaginatedResponse
from utils.pagination import paginate_params, PaginationParams

from core.database import get_db
from core.security_v2 import get_current_user
from core.logger import get_logger
from models.user import User
from models.external_api import ExternalAPICredential, APIProvider
from services.external_api_validator import get_external_api_validator
from schemas.external_api import (
    ExternalAPICredentialCreate,
    ExternalAPICredentialUpdate,
    ExternalAPICredentialResponse,
    ValidationResult,
    TestAllCredentialsResponse
)

logger = get_logger(__name__)
router = APIRouter(prefix="/external-api", tags=["external-api"])


@router.post("/validate/{provider}", response_model=ValidationResult)
async def validate_credentials(
    provider: APIProvider,
    credentials: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ValidationResult:
    """
    Validate credentials for an external API provider.
    
    This endpoint tests the provided credentials without storing them.
    """
    validator = get_external_api_validator()
    
    is_valid, error, metadata = await validator.validate_credentials(
        provider,
        credentials,
        current_user
    )
    
    return ValidationResult(
        provider=provider,
        is_valid=is_valid,
        error=error,
        metadata=metadata
    )


@router.post("/credentials", response_model=ExternalAPICredentialResponse)
async def create_credentials(
    credential_data: ExternalAPICredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExternalAPICredentialResponse:
    """
    Create or update external API credentials.
    
    This will validate the credentials before storing them.
    """
    # Check if credentials already exist for this provider
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.provider == credential_data.provider
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    # Validate credentials
    validator = get_external_api_validator()
    is_valid, error, metadata = await validator.validate_credentials(
        credential_data.provider,
        credential_data.credentials,
        current_user
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credentials: {error}"
        )
    
    if existing:
        # Update existing credentials
        existing.credentials = credential_data.credentials
        existing.is_valid = is_valid
        existing.validation_error = error
        existing.metadata = metadata
        existing.last_validated = datetime.utcnow()
        credential = existing
    else:
        # Create new credentials
        credential = ExternalAPICredential(
            user_id=current_user.id,
            agency_id=current_user.agency_id,
            provider=credential_data.provider,
            credentials=credential_data.credentials,
            is_valid=is_valid,
            validation_error=error,
            metadata=metadata,
            last_validated=datetime.utcnow()
        )
        db.add(credential)
    
    await db.commit()
    await db.refresh(credential)
    
    return ExternalAPICredentialResponse.from_orm(credential)


@router.get("/credentials", response_model=PaginatedResponse[ExternalAPICredentialResponse])
async def list_credentials(
    pagination: PaginationParams = Depends(paginate_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[ExternalAPICredentialResponse]:
    """List all external API credentials for the current user with pagination."""
    # Build base query
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.is_active == True
    ).order_by(ExternalAPICredential.created_at.desc())
    
    # Get total count
    count_stmt = select(func.count()).select_from(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.is_active == True
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Apply pagination
    stmt = stmt.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(stmt)
    credentials = result.scalars().all()
    
    # Convert to response models
    items = [ExternalAPICredentialResponse.from_orm(cred) for cred in credentials]
    
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        limit=pagination.limit
    )


@router.get("/credentials/{provider}", response_model=ExternalAPICredentialResponse)
async def get_credentials(
    provider: APIProvider,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExternalAPICredentialResponse:
    """Get credentials for a specific provider."""
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.provider == provider,
        ExternalAPICredential.is_active == True
    )
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials found for provider {provider}"
        )
    
    return ExternalAPICredentialResponse.from_orm(credential)


@router.put("/credentials/{provider}", response_model=ExternalAPICredentialResponse)
async def update_credentials(
    provider: APIProvider,
    credential_update: ExternalAPICredentialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExternalAPICredentialResponse:
    """Update credentials for a specific provider."""
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.provider == provider
    )
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials found for provider {provider}"
        )
    
    # Validate new credentials if provided
    if credential_update.credentials:
        validator = get_external_api_validator()
        is_valid, error, metadata = await validator.validate_credentials(
            provider,
            credential_update.credentials,
            current_user
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid credentials: {error}"
            )
        
        credential.credentials = credential_update.credentials
        credential.is_valid = is_valid
        credential.validation_error = error
        credential.metadata = metadata
        credential.last_validated = datetime.utcnow()
    
    if credential_update.is_active is not None:
        credential.is_active = credential_update.is_active
    
    await db.commit()
    await db.refresh(credential)
    
    return ExternalAPICredentialResponse.from_orm(credential)


@router.delete("/credentials/{provider}")
async def delete_credentials(
    provider: APIProvider,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete credentials for a specific provider."""
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.provider == provider
    )
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials found for provider {provider}"
        )
    
    await db.delete(credential)
    await db.commit()
    
    return {"message": f"Credentials for {provider} deleted successfully"}


@router.post("/test-all", response_model=TestAllCredentialsResponse)
async def test_all_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TestAllCredentialsResponse:
    """Test all stored credentials for the current user."""
    validator = get_external_api_validator()
    results = await validator.test_all_credentials(current_user)
    
    return TestAllCredentialsResponse(results=results)


@router.post("/revalidate/{provider}", response_model=ValidationResult)
async def revalidate_credentials(
    provider: APIProvider,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ValidationResult:
    """Revalidate stored credentials for a specific provider."""
    stmt = select(ExternalAPICredential).where(
        ExternalAPICredential.user_id == current_user.id,
        ExternalAPICredential.provider == provider,
        ExternalAPICredential.is_active == True
    )
    result = await db.execute(stmt)
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials found for provider {provider}"
        )
    
    validator = get_external_api_validator()
    is_valid, error, metadata = await validator.validate_credentials(
        provider,
        credential.credentials,
        current_user
    )
    
    # Update credential status
    credential.is_valid = is_valid
    credential.validation_error = error
    credential.last_validated = datetime.utcnow()
    if metadata:
        credential.metadata = {**credential.metadata, **metadata} if credential.metadata else metadata
    
    await db.commit()
    
    return ValidationResult(
        provider=provider,
        is_valid=is_valid,
        error=error,
        metadata=metadata
    )