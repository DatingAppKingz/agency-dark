"""Model management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field, HttpUrl

from core.database import get_db
from models.user import User, UserRole
from models.agency import Agency
from models.model import Model, ModelStatus, Platform
from models.model_settings import ModelSettings, ModelSchedule
from models.subscriber import Subscriber
from models.financial import Transaction, TransactionStatus
from api.v1.endpoints.auth_simple import get_current_user, get_password_hash
from core.errors import DuplicateError, NotFoundError, AuthorizationError, ValidationError as AppValidationError
from core.logger import get_logger

logger = get_logger(__name__)


router = APIRouter()


# Request/Response Models
class ModelCreate(BaseModel):
    stage_name: str = Field(..., min_length=1, max_length=100)
    real_name: Optional[str] = None
    bio: Optional[str] = None
    platform: Platform
    platform_username: str
    platform_url: Optional[HttpUrl] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    categories: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    languages: Optional[List[str]] = ["en"]


class ModelUpdate(BaseModel):
    stage_name: Optional[str] = None
    real_name: Optional[str] = None
    bio: Optional[str] = None
    platform: Optional[Platform] = None
    platform_username: Optional[str] = None
    platform_url: Optional[HttpUrl] = None
    status: Optional[ModelStatus] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    chat_enabled: Optional[bool] = None


class ModelSettingsUpdate(BaseModel):
    auto_welcome_enabled: Optional[bool] = None
    welcome_message: Optional[str] = None
    auto_response_enabled: Optional[bool] = None
    response_delay_min: Optional[int] = None
    response_delay_max: Optional[int] = None
    ppv_enabled: Optional[bool] = None
    ppv_min_price: Optional[Decimal] = None
    ppv_max_price: Optional[Decimal] = None
    tip_menu_enabled: Optional[bool] = None
    tip_menu: Optional[Dict[str, Any]] = None
    content_categories: Optional[List[str]] = None
    blocked_words: Optional[List[str]] = None
    ai_personality: Optional[str] = None
    commission_rate: Optional[Decimal] = None


class ModelScheduleCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: str  # HH:MM format
    end_time: str
    timezone: str = "UTC"


class ModelResponse(BaseModel):
    id: int
    user_id: int
    agency_id: int
    stage_name: str
    real_name: Optional[str]
    bio: Optional[str]
    platform: Platform
    platform_username: str
    platform_url: Optional[str]
    status: ModelStatus
    verification_status: str
    profile_photo_url: Optional[str]
    cover_photo_url: Optional[str]
    followers_count: int
    posts_count: int
    total_earnings: Decimal
    pending_payout: Decimal
    categories: List[str]
    tags: List[str]
    languages: List[str]
    chat_enabled: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    models: List[ModelResponse]
    total: int
    page: int
    limit: int


class ModelStatsResponse(BaseModel):
    total_revenue: Decimal
    current_month_revenue: Decimal
    subscriber_count: int
    new_subscribers_this_month: int
    message_count: int
    avg_response_time: float
    conversion_rate: float
    top_earning_content: List[Dict[str, Any]]


# Helper functions
async def get_user_agency(user: User, db: AsyncSession) -> Optional[Agency]:
    """Get the agency for the current user."""
    if user.role == UserRole.SUPER_ADMIN:
        return None  # Super admin can see all data
    
    if user.agency_id:
        stmt = select(Agency).where(Agency.id == user.agency_id)
        return await db.scalar(stmt)
    
    return None


async def verify_model_access(model_id: int, user: User, db: AsyncSession) -> Model:
    """Verify user has access to the model."""
    stmt = select(Model).where(Model.id == model_id)
    
    # Apply agency filter if not super admin
    if user.role != UserRole.SUPER_ADMIN:
        if user.role == UserRole.MODEL:
            # Models can only access their own profile
            stmt = stmt.where(Model.user_id == user.id)
        elif user.agency_id:
            # Agency users can access models in their agency
            stmt = stmt.where(Model.agency_id == user.agency_id)
        else:
            raise HTTPException(status_code=403, detail="Access denied")
    
    model = await db.scalar(stmt)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


# Endpoints
@router.get("/", response_model=ModelListResponse)
async def list_models(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ModelStatus] = None,
    platform: Optional[Platform] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|stage_name|followers_count|total_earnings)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List models with filtering and pagination."""
    # Build base query
    query = select(Model)
    count_query = select(func.count(Model.id))
    
    # Apply access filters
    if current_user.role == UserRole.MODEL:
        # Models can only see their own profile
        query = query.where(Model.user_id == current_user.id)
        count_query = count_query.where(Model.user_id == current_user.id)
    elif current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id:
        # Agency users see only their agency's models
        query = query.where(Model.agency_id == current_user.agency_id)
        count_query = count_query.where(Model.agency_id == current_user.agency_id)
    
    # Apply filters
    if status:
        query = query.where(Model.status == status)
        count_query = count_query.where(Model.status == status)
    
    if platform:
        query = query.where(Model.platform == platform)
        count_query = count_query.where(Model.platform == platform)
    
    if search:
        search_filter = or_(
            Model.stage_name.ilike(f"%{search}%"),
            Model.real_name.ilike(f"%{search}%"),
            Model.platform_username.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Apply sorting
    order_column = getattr(Model, sort_by)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column)
    
    # Get total count
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    models = result.scalars().all()
    
    return ModelListResponse(
        models=[ModelResponse.model_validate(model) for model in models],
        total=total or 0,
        page=page,
        limit=limit
    )


@router.post("/", response_model=ModelResponse)
async def create_model(
    model_data: ModelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new model profile."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get agency
    agency = await get_user_agency(current_user, db)
    if not agency and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="No agency associated with user")
    
    # Check if model with same platform username exists
    existing_stmt = select(Model).where(
        and_(
            Model.platform == model_data.platform,
            Model.platform_username == model_data.platform_username
        )
    )
    if agency:
        existing_stmt = existing_stmt.where(Model.agency_id == agency.id)
    
    existing = await db.scalar(existing_stmt)
    if existing:
        raise HTTPException(status_code=400, detail="Model with this platform username already exists")
    
    # Create user account for the model
    email = model_data.email or f"{model_data.platform_username}@{model_data.platform.value}.com"
    username = f"{model_data.platform_username}_{model_data.platform.value}"
    
    # Check if user exists
    user_stmt = select(User).where(
        or_(User.email == email, User.username == username)
    )
    model_user = await db.scalar(user_stmt)
    
    if not model_user:
        # Create new user
        model_user = User(
            email=email,
            username=username,
            password_hash=get_password_hash("model123"),  # Default password
            first_name=model_data.stage_name.split()[0] if model_data.stage_name else "Model",
            last_name=model_data.stage_name.split()[-1] if len(model_data.stage_name.split()) > 1 else "",
            role=UserRole.MODEL,
            agency_id=agency.id if agency else None,
            is_active=True,
            is_verified=False
        )
        db.add(model_user)
        await db.flush()
    
    # Create model profile
    model = Model(
        user_id=model_user.id,
        agency_id=agency.id if agency else current_user.agency_id,
        stage_name=model_data.stage_name,
        real_name=model_data.real_name,
        bio=model_data.bio,
        platform=model_data.platform,
        platform_username=model_data.platform_username,
        platform_url=str(model_data.platform_url) if model_data.platform_url else None,
        status=ModelStatus.PENDING,
        verification_status="pending",
        email=model_data.email,
        phone=model_data.phone,
        date_of_birth=datetime.fromisoformat(model_data.date_of_birth) if model_data.date_of_birth else None,
        categories=model_data.categories or [],
        tags=model_data.tags or [],
        languages=model_data.languages or ["en"],
        chat_enabled=True
    )
    
    db.add(model)
    await db.commit()
    await db.refresh(model)
    
    # Create default settings
    settings = ModelSettings(
        model_id=model.id,
        auto_welcome_enabled=True,
        welcome_message="Hey there! Thanks for subscribing! What would you like to see?",
        auto_response_enabled=False,
        response_delay_min=1,
        response_delay_max=3,
        ppv_enabled=True,
        ppv_min_price=Decimal("5.00"),
        ppv_max_price=Decimal("100.00"),
        tip_menu_enabled=True,
        tip_menu={
            "items": [
                {"name": "Coffee", "price": 5},
                {"name": "Lunch", "price": 20},
                {"name": "Spa Day", "price": 100}
            ]
        },
        commission_rate=agency.default_commission_rate if agency else Decimal("20.00")
    )
    
    db.add(settings)
    await db.commit()
    
    return ModelResponse.model_validate(model)


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific model's details."""
    model = await verify_model_access(model_id, current_user, db)
    return ModelResponse.model_validate(model)


@router.patch("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: int,
    update_data: ModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a model's profile."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Check permissions for status changes
    if update_data.status and current_user.role not in [
        UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN
    ]:
        raise HTTPException(status_code=403, detail="Insufficient permissions to change status")
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(model, field, value)
    
    model.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(model)
    
    return ModelResponse.model_validate(model)


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a model (soft delete by setting status to deleted)."""
    # Check permissions
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    model = await verify_model_access(model_id, current_user, db)
    
    # Soft delete
    model.status = ModelStatus.DELETED
    model.updated_at = datetime.utcnow()
    
    # Also deactivate the user account
    user_stmt = select(User).where(User.id == model.user_id)
    model_user = await db.scalar(user_stmt)
    if model_user:
        model_user.is_active = False
    
    await db.commit()
    
    return {"message": "Model deleted successfully"}


@router.get("/{model_id}/stats", response_model=ModelStatsResponse)
async def get_model_stats(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed statistics for a model."""
    model = await verify_model_access(model_id, current_user, db)
    
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Total revenue
    total_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.model_id == model_id,
            Transaction.status == TransactionStatus.COMPLETED
        )
    )
    total_revenue = await db.scalar(total_revenue_stmt) or Decimal('0')
    
    # Current month revenue
    month_revenue_stmt = select(func.coalesce(func.sum(Transaction.gross_amount), 0)).where(
        and_(
            Transaction.model_id == model_id,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.created_at >= month_start
        )
    )
    current_month_revenue = await db.scalar(month_revenue_stmt) or Decimal('0')
    
    # Subscriber count
    sub_count_stmt = select(func.count(Subscriber.id)).where(
        and_(
            Subscriber.model_id == model_id,
            Subscriber.is_active == True
        )
    )
    subscriber_count = await db.scalar(sub_count_stmt) or 0
    
    # New subscribers this month
    new_subs_stmt = select(func.count(Subscriber.id)).where(
        and_(
            Subscriber.model_id == model_id,
            Subscriber.created_at >= month_start
        )
    )
    new_subscribers_this_month = await db.scalar(new_subs_stmt) or 0
    
    # Message count (mock data)
    message_count = 1250
    avg_response_time = 4.5
    conversion_rate = 18.5
    
    # Top earning content (mock data)
    top_earning_content = [
        {"type": "ppv", "title": "Exclusive Photoshoot", "earnings": 850.00},
        {"type": "tip", "title": "Birthday Special", "earnings": 620.00},
        {"type": "subscription", "title": "Monthly Subscription", "earnings": 2400.00}
    ]
    
    return ModelStatsResponse(
        total_revenue=total_revenue,
        current_month_revenue=current_month_revenue,
        subscriber_count=subscriber_count,
        new_subscribers_this_month=new_subscribers_this_month,
        message_count=message_count,
        avg_response_time=avg_response_time,
        conversion_rate=conversion_rate,
        top_earning_content=top_earning_content
    )


@router.get("/{model_id}/settings")
async def get_model_settings(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get model settings."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Get settings
    stmt = select(ModelSettings).where(ModelSettings.model_id == model_id)
    settings = await db.scalar(stmt)
    
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    
    return settings


@router.patch("/{model_id}/settings")
async def update_model_settings(
    model_id: int,
    settings_data: ModelSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update model settings."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Get settings
    stmt = select(ModelSettings).where(ModelSettings.model_id == model_id)
    settings = await db.scalar(stmt)
    
    if not settings:
        # Create default settings if not exist
        settings = ModelSettings(model_id=model_id)
        db.add(settings)
    
    # Update settings
    update_dict = settings_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(settings, field, value)
    
    settings.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(settings)
    
    return settings


@router.get("/{model_id}/schedule", response_model=List[Dict[str, Any]])
async def get_model_schedule(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get model's availability schedule."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Get schedule
    stmt = select(ModelSchedule).where(
        ModelSchedule.model_id == model_id
    ).order_by(ModelSchedule.day_of_week, ModelSchedule.start_time)
    
    result = await db.execute(stmt)
    schedules = result.scalars().all()
    
    return [
        {
            "id": schedule.id,
            "day_of_week": schedule.day_of_week,
            "start_time": schedule.start_time.strftime("%H:%M"),
            "end_time": schedule.end_time.strftime("%H:%M"),
            "timezone": schedule.timezone
        }
        for schedule in schedules
    ]


@router.post("/{model_id}/schedule")
async def add_model_schedule(
    model_id: int,
    schedule_data: ModelScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a schedule entry for a model."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Parse times
    start_hour, start_min = map(int, schedule_data.start_time.split(":"))
    end_hour, end_min = map(int, schedule_data.end_time.split(":"))
    
    from datetime import time
    schedule = ModelSchedule(
        model_id=model_id,
        day_of_week=schedule_data.day_of_week,
        start_time=time(start_hour, start_min),
        end_time=time(end_hour, end_min),
        timezone=schedule_data.timezone
    )
    
    db.add(schedule)
    await db.commit()
    
    return {"message": "Schedule added successfully", "id": schedule.id}


@router.post("/{model_id}/upload-photo")
async def upload_model_photo(
    model_id: int,
    photo_type: str = Query(..., regex="^(profile|cover)$"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload profile or cover photo for a model."""
    model = await verify_model_access(model_id, current_user, db)
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # In production, you would upload to S3 or similar
    # For now, we'll just simulate it
    file_url = f"https://storage.agencydark.com/models/{model_id}/{photo_type}_{file.filename}"
    
    if photo_type == "profile":
        model.profile_photo_url = file_url
    else:
        model.cover_photo_url = file_url
    
    model.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"url": file_url, "message": f"{photo_type.capitalize()} photo uploaded successfully"}