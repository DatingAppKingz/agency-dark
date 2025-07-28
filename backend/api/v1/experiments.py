"""
A/B Testing API Endpoints
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from core.database import get_db
from core.auth import get_current_user
from core.permissions import check_agency_permission
from modules.ab_testing.core.experiment_manager import experiment_manager
from modules.ab_testing.domain.models import (
    Experiment, ExperimentVariant, ExperimentType, 
    ExperimentStatus, AllocationMethod, StatisticalTest
)

router = APIRouter(tags=["experiments"])


# Request/Response Models
class VariantConfig(BaseModel):
    name: str
    description: Optional[str] = None
    is_control: bool = False
    config: Dict[str, Any]
    allocation_percentage: float = Field(gt=0, le=100)


class CreateExperimentRequest(BaseModel):
    name: str
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    experiment_type: ExperimentType
    target_audience: Optional[Dict[str, Any]] = None
    model_ids: Optional[List[str]] = None
    primary_metric: str
    secondary_metrics: Optional[List[str]] = None
    minimum_sample_size: int = 100
    allocation_method: AllocationMethod = AllocationMethod.RANDOM
    allocation_config: Optional[Dict[str, Any]] = None
    statistical_test: StatisticalTest = StatisticalTest.T_TEST
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)
    minimum_detectable_effect: float = Field(default=0.05, gt=0, le=1)
    variants: List[VariantConfig]


class ExperimentResponse(BaseModel):
    id: UUID
    agency_id: str
    name: str
    description: Optional[str]
    hypothesis: Optional[str]
    experiment_type: str
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    allocation_method: str
    primary_metric: str
    secondary_metrics: List[str]
    minimum_sample_size: int
    confidence_level: float
    minimum_detectable_effect: float
    created_at: datetime
    updated_at: datetime
    variants: List[Dict[str, Any]]
    results_summary: Optional[Dict[str, Any]]


class TrackEventRequest(BaseModel):
    participant_type: str
    participant_id: str
    event_type: str
    event_value: Optional[float] = None
    event_data: Optional[Dict[str, Any]] = None


class AssignmentResponse(BaseModel):
    experiment_id: UUID
    variant_id: UUID
    variant_name: str
    variant_config: Dict[str, Any]


@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    request: CreateExperimentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new A/B testing experiment"""
    # Check permissions
    await check_agency_permission(
        db, current_user["id"], current_user["agency_id"], "experiments.create"
    )
    
    # Validate variant allocation
    total_allocation = sum(v.allocation_percentage for v in request.variants)
    if abs(total_allocation - 100.0) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Total variant allocation must equal 100%, got {total_allocation}%"
        )
    
    # Create experiment
    try:
        experiment = await experiment_manager.create_experiment(
            agency_id=current_user["agency_id"],
            created_by=current_user["id"],
            name=request.name,
            experiment_type=request.experiment_type,
            config=request.dict(exclude={"name", "experiment_type"}),
            db=db
        )
        
        # Load variants for response
        variants_query = select(ExperimentVariant).where(
            ExperimentVariant.experiment_id == experiment.id
        )
        result = await db.execute(variants_query)
        variants = result.scalars().all()
        
        return ExperimentResponse(
            id=experiment.id,
            agency_id=experiment.agency_id,
            name=experiment.name,
            description=experiment.description,
            hypothesis=experiment.hypothesis,
            experiment_type=experiment.experiment_type,
            status=experiment.status,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            allocation_method=experiment.allocation_method,
            primary_metric=experiment.primary_metric,
            secondary_metrics=experiment.secondary_metrics or [],
            minimum_sample_size=experiment.minimum_sample_size,
            confidence_level=experiment.confidence_level,
            minimum_detectable_effect=experiment.minimum_detectable_effect,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            variants=[{
                "id": str(v.id),
                "name": v.name,
                "description": v.description,
                "is_control": v.is_control,
                "allocation_percentage": v.allocation_percentage,
                "config": v.config
            } for v in variants],
            results_summary=experiment.results_summary
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create experiment: {str(e)}")


@router.get("/experiments", response_model=List[ExperimentResponse])
async def list_experiments(
    status: Optional[ExperimentStatus] = Query(None),
    experiment_type: Optional[ExperimentType] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List experiments for the agency"""
    # Build query
    query = select(Experiment).where(
        Experiment.agency_id == current_user["agency_id"]
    )
    
    if status:
        query = query.where(Experiment.status == status.value)
    
    if experiment_type:
        query = query.where(Experiment.experiment_type == experiment_type.value)
    
    query = query.order_by(Experiment.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    experiments = result.scalars().all()
    
    # Load variants for each experiment
    response = []
    for experiment in experiments:
        variants_query = select(ExperimentVariant).where(
            ExperimentVariant.experiment_id == experiment.id
        )
        variants_result = await db.execute(variants_query)
        variants = variants_result.scalars().all()
        
        response.append(ExperimentResponse(
            id=experiment.id,
            agency_id=experiment.agency_id,
            name=experiment.name,
            description=experiment.description,
            hypothesis=experiment.hypothesis,
            experiment_type=experiment.experiment_type,
            status=experiment.status,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            allocation_method=experiment.allocation_method,
            primary_metric=experiment.primary_metric,
            secondary_metrics=experiment.secondary_metrics or [],
            minimum_sample_size=experiment.minimum_sample_size,
            confidence_level=experiment.confidence_level,
            minimum_detectable_effect=experiment.minimum_detectable_effect,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            variants=[{
                "id": str(v.id),
                "name": v.name,
                "description": v.description,
                "is_control": v.is_control,
                "allocation_percentage": v.allocation_percentage,
                "config": v.config
            } for v in variants],
            results_summary=experiment.results_summary
        ))
    
    return response


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get experiment details"""
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.agency_id != current_user["agency_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Load variants
    variants_query = select(ExperimentVariant).where(
        ExperimentVariant.experiment_id == experiment.id
    )
    result = await db.execute(variants_query)
    variants = result.scalars().all()
    
    return ExperimentResponse(
        id=experiment.id,
        agency_id=experiment.agency_id,
        name=experiment.name,
        description=experiment.description,
        hypothesis=experiment.hypothesis,
        experiment_type=experiment.experiment_type,
        status=experiment.status,
        start_date=experiment.start_date,
        end_date=experiment.end_date,
        allocation_method=experiment.allocation_method,
        primary_metric=experiment.primary_metric,
        secondary_metrics=experiment.secondary_metrics or [],
        minimum_sample_size=experiment.minimum_sample_size,
        confidence_level=experiment.confidence_level,
        minimum_detectable_effect=experiment.minimum_detectable_effect,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
        variants=[{
            "id": str(v.id),
            "name": v.name,
            "description": v.description,
            "is_control": v.is_control,
            "allocation_percentage": v.allocation_percentage,
            "config": v.config,
            "participant_count": v.participant_count,
            "conversion_count": v.conversion_count,
            "conversion_rate": v.conversion_rate
        } for v in variants],
        results_summary=experiment.results_summary
    )


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(
    experiment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start an experiment"""
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.agency_id != current_user["agency_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await check_agency_permission(
        db, current_user["id"], current_user["agency_id"], "experiments.manage"
    )
    
    try:
        await experiment_manager.start_experiment(experiment_id, db)
        return {"status": "started", "experiment_id": experiment_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(
    experiment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Pause a running experiment"""
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.agency_id != current_user["agency_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await check_agency_permission(
        db, current_user["id"], current_user["agency_id"], "experiments.manage"
    )
    
    try:
        await experiment_manager.pause_experiment(experiment_id, db)
        return {"status": "paused", "experiment_id": experiment_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/experiments/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Complete an experiment and analyze results"""
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.agency_id != current_user["agency_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    await check_agency_permission(
        db, current_user["id"], current_user["agency_id"], "experiments.manage"
    )
    
    try:
        results = await experiment_manager.complete_experiment(experiment_id, db)
        return {
            "status": "completed",
            "experiment_id": experiment_id,
            "results": results
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(
    experiment_id: UUID,
    segment_by: Optional[List[str]] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get experiment results and analysis"""
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.agency_id != current_user["agency_id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        results = await experiment_manager.analyze_experiment(
            experiment_id, db, segment_by=segment_by
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/experiments/{experiment_id}/assign")
async def assign_to_experiment(
    experiment_id: UUID,
    participant_type: str = Query(..., regex="^(fan|model|user)$"),
    participant_id: str = Query(...),
    context: Optional[Dict[str, Any]] = Body(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign a participant to an experiment variant"""
    # For public endpoints, verify experiment is running
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if experiment.status != ExperimentStatus.RUNNING.value:
        raise HTTPException(
            status_code=400,
            detail="Experiment is not currently running"
        )
    
    # Assign participant
    variant = await experiment_manager.assign_participant(
        experiment_id=experiment_id,
        participant_type=participant_type,
        participant_id=participant_id,
        context=context,
        db=db
    )
    
    if not variant:
        raise HTTPException(
            status_code=400,
            detail="Could not assign participant to experiment"
        )
    
    return AssignmentResponse(
        experiment_id=experiment_id,
        variant_id=variant.id,
        variant_name=variant.name,
        variant_config=variant.config
    )


@router.post("/experiments/{experiment_id}/track")
async def track_experiment_event(
    experiment_id: UUID,
    request: TrackEventRequest,
    db: AsyncSession = Depends(get_db)
):
    """Track an event for an experiment participant"""
    # Verify experiment exists
    experiment = await db.get(Experiment, experiment_id)
    
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    # Track event
    success = await experiment_manager.track_event(
        experiment_id=experiment_id,
        participant_type=request.participant_type,
        participant_id=request.participant_id,
        event_type=request.event_type,
        event_value=request.event_value,
        event_data=request.event_data,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not track event - participant may not be assigned"
        )
    
    return {"status": "tracked", "experiment_id": experiment_id}


@router.get("/experiments/active")
async def get_active_experiments(
    experiment_type: Optional[ExperimentType] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all active experiments for the agency"""
    experiments = await experiment_manager.get_active_experiments(
        agency_id=current_user["agency_id"],
        experiment_type=experiment_type,
        db=db
    )
    
    return [
        {
            "id": str(exp.id),
            "name": exp.name,
            "type": exp.experiment_type,
            "start_date": exp.start_date,
            "primary_metric": exp.primary_metric
        }
        for exp in experiments
    ]