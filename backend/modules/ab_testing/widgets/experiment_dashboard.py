"""
A/B Testing Dashboard Widget
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from core.logging import get_logger
from modules.analytics.dashboard.base_widget import BaseWidget, WidgetType
from modules.ab_testing.domain.models import (
    Experiment, ExperimentVariant, ExperimentParticipant,
    ExperimentStatus
)
from modules.ab_testing.core.experiment_manager import experiment_manager

logger = get_logger(__name__)


class ExperimentDashboardWidget(BaseWidget):
    """Widget for displaying A/B testing metrics"""
    
    widget_type = WidgetType.CHART
    
    async def render(
        self,
        agency_id: str,
        config: Dict[str, Any],
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Render experiment dashboard data"""
        view_type = config.get("view_type", "overview")
        
        if view_type == "overview":
            return await self._render_overview(agency_id, time_range, db)
        elif view_type == "experiment_details":
            experiment_id = config.get("experiment_id")
            if experiment_id:
                return await self._render_experiment_details(
                    UUID(experiment_id), time_range, db
                )
        elif view_type == "active_experiments":
            return await self._render_active_experiments(agency_id, db)
        
        return {"error": "Invalid view type"}
    
    async def _render_overview(
        self,
        agency_id: str,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Render experiments overview"""
        # Get date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=time_range.get("days", 30))
        
        # Count experiments by status
        status_query = select(
            Experiment.status,
            func.count(Experiment.id).label("count")
        ).where(
            and_(
                Experiment.agency_id == agency_id,
                Experiment.created_at >= start_date
            )
        ).group_by(Experiment.status)
        
        result = await db.execute(status_query)
        status_counts = {row.status: row.count for row in result}
        
        # Get total participants
        participants_query = select(
            func.count(ExperimentParticipant.id)
        ).join(
            Experiment
        ).where(
            and_(
                Experiment.agency_id == agency_id,
                ExperimentParticipant.assignment_timestamp >= start_date
            )
        )
        
        participants_result = await db.execute(participants_query)
        total_participants = participants_result.scalar() or 0
        
        # Get conversion metrics
        conversion_query = select(
            func.count(ExperimentParticipant.id).label("total"),
            func.sum(
                func.cast(ExperimentParticipant.has_converted, func.Integer)
            ).label("converted")
        ).join(
            Experiment
        ).where(
            and_(
                Experiment.agency_id == agency_id,
                ExperimentParticipant.assignment_timestamp >= start_date
            )
        )
        
        conversion_result = await db.execute(conversion_query)
        conversion_data = conversion_result.first()
        
        overall_conversion_rate = 0
        if conversion_data and conversion_data.total > 0:
            overall_conversion_rate = (conversion_data.converted or 0) / conversion_data.total
        
        return {
            "type": "stats",
            "data": {
                "experiments": {
                    "draft": status_counts.get(ExperimentStatus.DRAFT.value, 0),
                    "running": status_counts.get(ExperimentStatus.RUNNING.value, 0),
                    "paused": status_counts.get(ExperimentStatus.PAUSED.value, 0),
                    "completed": status_counts.get(ExperimentStatus.COMPLETED.value, 0),
                    "total": sum(status_counts.values())
                },
                "participants": {
                    "total": total_participants,
                    "average_per_experiment": (
                        total_participants / sum(status_counts.values())
                        if sum(status_counts.values()) > 0 else 0
                    )
                },
                "performance": {
                    "overall_conversion_rate": overall_conversion_rate,
                    "total_conversions": conversion_data.converted if conversion_data else 0
                }
            }
        }
    
    async def _render_experiment_details(
        self,
        experiment_id: UUID,
        time_range: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Render detailed experiment metrics"""
        # Get experiment
        experiment = await db.get(Experiment, experiment_id)
        if not experiment:
            return {"error": "Experiment not found"}
        
        # Get analysis
        try:
            analysis = await experiment_manager.analyze_experiment(
                experiment_id, db
            )
        except Exception as e:
            logger.error(f"Error analyzing experiment: {e}")
            return {"error": "Failed to analyze experiment"}
        
        # Format for visualization
        variants_data = []
        for variant in analysis.get("variants", []):
            variants_data.append({
                "name": variant.get("name", "Unknown"),
                "participants": variant.get("participants", 0),
                "conversions": variant.get("conversions", 0),
                "conversion_rate": variant.get("conversion_rate", 0),
                "is_control": variant.get("is_control", False),
                "is_significant": variant.get("is_statistically_significant", False),
                "confidence_interval": variant.get("confidence_interval", {})
            })
        
        # Time series data
        time_series = analysis.get("time_series", [])
        
        return {
            "type": "experiment_analysis",
            "data": {
                "experiment": {
                    "id": str(experiment.id),
                    "name": experiment.name,
                    "status": experiment.status,
                    "type": experiment.experiment_type,
                    "start_date": experiment.start_date.isoformat() if experiment.start_date else None,
                    "duration_days": analysis.get("duration_days", 0)
                },
                "variants": variants_data,
                "statistical_significance": analysis.get("statistical_significance", {}),
                "recommendations": analysis.get("recommendations", []),
                "time_series": [
                    {
                        "timestamp": ts["timestamp"],
                        "participants": ts["participants"],
                        "events": ts["events"]
                    }
                    for ts in time_series[-24:]  # Last 24 hours
                ]
            }
        }
    
    async def _render_active_experiments(
        self,
        agency_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Render active experiments list"""
        # Get running experiments
        experiments = await experiment_manager.get_active_experiments(
            agency_id=agency_id,
            db=db
        )
        
        experiments_data = []
        for exp in experiments:
            # Get participant count
            participant_query = select(
                func.count(ExperimentParticipant.id)
            ).where(
                ExperimentParticipant.experiment_id == exp.id
            )
            
            result = await db.execute(participant_query)
            participant_count = result.scalar() or 0
            
            # Get variant count
            variant_query = select(
                func.count(ExperimentVariant.id)
            ).where(
                ExperimentVariant.experiment_id == exp.id
            )
            
            variant_result = await db.execute(variant_query)
            variant_count = variant_result.scalar() or 0
            
            # Calculate progress
            progress = 0
            if exp.minimum_sample_size > 0:
                progress = min(
                    100,
                    (participant_count / exp.minimum_sample_size) * 100
                )
            
            experiments_data.append({
                "id": str(exp.id),
                "name": exp.name,
                "type": exp.experiment_type,
                "start_date": exp.start_date.isoformat() if exp.start_date else None,
                "participants": participant_count,
                "variants": variant_count,
                "progress": progress,
                "primary_metric": exp.primary_metric
            })
        
        return {
            "type": "table",
            "data": {
                "experiments": experiments_data,
                "total": len(experiments_data)
            }
        }
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default widget configuration"""
        return {
            "view_type": "overview",
            "refresh_interval": 300,  # 5 minutes
            "show_recommendations": True
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate widget configuration"""
        view_type = config.get("view_type")
        
        if view_type not in ["overview", "experiment_details", "active_experiments"]:
            return False
        
        if view_type == "experiment_details" and not config.get("experiment_id"):
            return False
        
        return True