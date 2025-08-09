"""
API endpoints for partition management and monitoring
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.security_v2 import get_current_user
from core.security_v2.authorization import check_permission
from core.database_utils.partitioning import partition_manager, get_partition_statistics
from core.tasks.partition_maintenance import (
    PartitionMaintenanceTask,
    get_partition_report,
    check_partition_health
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/partitions", tags=["partitions"])


class PartitionInfo(BaseModel):
    name: str
    size: str
    row_count: int
    last_vacuum: Optional[datetime]
    last_analyze: Optional[datetime]


class TablePartitions(BaseModel):
    table_name: str
    partition_count: int
    total_size_mb: float
    total_rows: int
    partitions: List[PartitionInfo]


class PartitionHealth(BaseModel):
    healthy: bool
    missing_partitions: List[Dict[str, str]]
    bloated_partitions: List[Dict[str, Any]]
    maintenance_needed: List[str]


@router.get("/", response_model=List[TablePartitions])
async def list_partitioned_tables(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all partitioned tables and their partitions"""
    await check_permission(current_user["role"], "admin.view")
    
    tables = []
    for table_name in partition_manager.partitioned_tables.keys():
        try:
            stats = await get_partition_statistics(db, table_name)
            partitions = await partition_manager.get_partition_info(db, table_name)
            
            tables.append(TablePartitions(
                table_name=table_name,
                partition_count=stats["partition_count"],
                total_size_mb=stats["total_size_mb"],
                total_rows=stats["total_rows"],
                partitions=[
                    PartitionInfo(
                        name=p["name"],
                        size=p["size"],
                        row_count=p["row_count"] or 0,
                        last_vacuum=p["last_vacuum"],
                        last_analyze=p["last_analyze"]
                    )
                    for p in partitions
                ]
            ))
        except Exception as e:
            logger.error(f"Error getting partitions for {table_name}: {e}")
    
    return tables


@router.get("/{table_name}", response_model=TablePartitions)
async def get_table_partitions(
    table_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed partition information for a specific table"""
    await check_permission(current_user["role"], "admin.view")
    
    if table_name not in partition_manager.partitioned_tables:
        raise HTTPException(
            status_code=404,
            detail=f"Table {table_name} is not partitioned"
        )
    
    try:
        stats = await get_partition_statistics(db, table_name)
        partitions = await partition_manager.get_partition_info(db, table_name)
        
        return TablePartitions(
            table_name=table_name,
            partition_count=stats["partition_count"],
            total_size_mb=stats["total_size_mb"],
            total_rows=stats["total_rows"],
            partitions=[
                PartitionInfo(
                    name=p["name"],
                    size=p["size"],
                    row_count=p["row_count"] or 0,
                    last_vacuum=p["last_vacuum"],
                    last_analyze=p["last_analyze"]
                )
                for p in partitions
            ]
        )
    except Exception as e:
        logger.error(f"Error getting partitions for {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get partition information: {str(e)}"
        )


@router.get("/health/check", response_model=PartitionHealth)
async def check_partitions_health(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check health of all partitions"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        # Check for missing partitions
        health_result = await check_partition_health()
        
        # Check for bloated partitions
        maintenance_task = PartitionMaintenanceTask()
        bloated = await maintenance_task._check_bloated_partitions(db)
        
        # Check which tables need maintenance
        stats = await maintenance_task._collect_partition_stats(db)
        maintenance_needed = []
        
        for table_name, table_stats in stats.items():
            if table_stats["needs_vacuum"] or table_stats["needs_analyze"]:
                maintenance_needed.append(table_name)
        
        return PartitionHealth(
            healthy=health_result["healthy"] and len(bloated) == 0,
            missing_partitions=health_result.get("missing", []),
            bloated_partitions=bloated,
            maintenance_needed=maintenance_needed
        )
    except Exception as e:
        logger.error(f"Error checking partition health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check partition health: {str(e)}"
        )


@router.post("/maintenance/run")
async def run_maintenance(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger partition maintenance"""
    await check_permission(current_user["role"], "admin.execute")
    
    try:
        task = PartitionMaintenanceTask()
        await task.run_maintenance(db)
        
        return {
            "status": "success",
            "message": "Partition maintenance completed",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error running partition maintenance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run partition maintenance: {str(e)}"
        )


@router.post("/create/{table_name}")
async def create_partition(
    table_name: str,
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually create a partition for a specific month"""
    await check_permission(current_user["role"], "admin.execute")
    
    if table_name not in partition_manager.partitioned_tables:
        raise HTTPException(
            status_code=404,
            detail=f"Table {table_name} is not partitioned"
        )
    
    try:
        partition_date = datetime(year, month, 1)
        config = partition_manager.partitioned_tables[table_name]
        
        await partition_manager._create_monthly_partition(
            db, table_name, partition_date, config
        )
        await db.commit()
        
        return {
            "status": "success",
            "partition_name": f"{table_name}_{year}_{month:02d}",
            "message": f"Partition created for {year}-{month:02d}"
        }
    except Exception as e:
        logger.error(f"Error creating partition: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create partition: {str(e)}"
        )


@router.delete("/drop/{partition_name}")
async def drop_partition(
    partition_name: str,
    archive: bool = Query(True, description="Archive data before dropping"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually drop a specific partition"""
    await check_permission(current_user["role"], "admin.execute")
    
    # Validate partition name format
    if not partition_name.match(r'^[a-z_]+_\d{4}_\d{2}$'):
        raise HTTPException(
            status_code=400,
            detail="Invalid partition name format. Expected: tablename_YYYY_MM"
        )
    
    try:
        # Check if partition exists
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_tables 
                WHERE tablename = :partition_name
            )
        """)
        result = await db.execute(check_query, {"partition_name": partition_name})
        
        if not result.scalar():
            raise HTTPException(
                status_code=404,
                detail=f"Partition {partition_name} not found"
            )
        
        # Archive if requested
        if archive:
            await partition_manager._archive_partition(db, partition_name)
        
        # Drop the partition
        drop_query = text(f"DROP TABLE {partition_name}")
        await db.execute(drop_query)
        await db.commit()
        
        return {
            "status": "success",
            "message": f"Partition {partition_name} dropped",
            "archived": archive
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dropping partition: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to drop partition: {str(e)}"
        )


@router.post("/{table_name}/analyze")
async def analyze_table_partitions(
    table_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run ANALYZE on all partitions of a table"""
    await check_permission(current_user["role"], "admin.execute")
    
    if table_name not in partition_manager.partitioned_tables:
        raise HTTPException(
            status_code=404,
            detail=f"Table {table_name} is not partitioned"
        )
    
    try:
        # Get all partitions
        partitions = await partition_manager.get_partition_info(db, table_name)
        
        # Analyze each partition
        analyzed = []
        for partition in partitions:
            analyze_query = text(f"ANALYZE {partition['name']}")
            await db.execute(analyze_query)
            analyzed.append(partition["name"])
        
        # Analyze parent table
        analyze_parent = text(f"ANALYZE {table_name}")
        await db.execute(analyze_parent)
        
        await db.commit()
        
        return {
            "status": "success",
            "table": table_name,
            "partitions_analyzed": len(analyzed),
            "partitions": analyzed
        }
    except Exception as e:
        logger.error(f"Error analyzing partitions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze partitions: {str(e)}"
        )


@router.get("/report/summary")
async def get_partitioning_report(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive partitioning report"""
    await check_permission(current_user["role"], "admin.view")
    
    try:
        report = await get_partition_report()
        
        # Add recommendations
        recommendations = []
        for table_name, table_data in report["tables"].items():
            if table_data["growth_rate_pct"] > 50:
                recommendations.append({
                    "table": table_name,
                    "issue": "high_growth",
                    "recommendation": f"Table {table_name} has {table_data['growth_rate_pct']}% growth rate. Consider adjusting retention policy."
                })
            
            stats = table_data["statistics"]
            if stats["partition_count"] > 24:  # More than 2 years of monthly partitions
                recommendations.append({
                    "table": table_name,
                    "issue": "many_partitions",
                    "recommendation": f"Table {table_name} has {stats['partition_count']} partitions. Consider archiving old data."
                })
        
        report["recommendations"] = recommendations
        
        return report
    except Exception as e:
        logger.error(f"Error generating partition report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate partition report: {str(e)}"
        )


import re