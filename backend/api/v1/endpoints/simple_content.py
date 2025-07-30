"""Simple content/media endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from core.database import get_db
from models.content import Content, ContentType, ContentStatus
from models.model import Model
from models.user import User
from api.v1.endpoints.auth_simple import get_current_user


router = APIRouter()


class ContentCreate(BaseModel):
    model_id: int
    type: str
    url: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price: Optional[float] = None


class ContentResponse(BaseModel):
    id: int
    model_id: int
    type: str
    status: str
    media_urls: List[str]
    title: Optional[str]
    description: Optional[str]
    thumbnail_url: Optional[str]
    price: Optional[float]
    is_free: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class MediaLibraryResponse(BaseModel):
    content: List[ContentResponse]
    total: int


@router.post("/", response_model=ContentResponse)
async def create_content(
    content: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new content."""
    # Verify model exists
    stmt = select(Model).where(Model.id == content.model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Convert type to enum
    try:
        content_type = ContentType[content.type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid content type")
    
    new_content = Content(
        model_id=content.model_id,
        type=content_type,
        status=ContentStatus.PUBLISHED,
        media_urls=[content.url],  # Content uses media_urls as a list
        title=content.title,
        description=content.description,
        thumbnail_url=content.thumbnail_url,
        price=content.price,
        is_free=content.price is None or content.price == 0
    )
    
    db.add(new_content)
    await db.commit()
    await db.refresh(new_content)
    
    return new_content


@router.get("/", response_model=List[ContentResponse])
async def list_content(
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of content."""
    stmt = select(Content)
    
    if model_id:
        stmt = stmt.where(Content.model_id == model_id)
    
    stmt = stmt.where(Content.status == ContentStatus.PUBLISHED)
    stmt = stmt.offset(skip).limit(limit).order_by(Content.created_at.desc())
    
    result = await db.execute(stmt)
    content = result.scalars().all()
    return content


@router.get("/library/model/{model_id}", response_model=MediaLibraryResponse)
async def get_media_library(
    model_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get media library for a model."""
    # Get content
    stmt = select(Content).where(
        Content.model_id == model_id,
        Content.status == ContentStatus.PUBLISHED
    ).offset(skip).limit(limit).order_by(Content.created_at.desc())
    
    result = await db.execute(stmt)
    content = result.scalars().all()
    
    # Get total count
    count_stmt = select(func.count(Content.id)).where(
        Content.model_id == model_id,
        Content.status == ContentStatus.PUBLISHED
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    return MediaLibraryResponse(
        content=content,
        total=total
    )