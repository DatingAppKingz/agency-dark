"""
Dashboard data models
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, JSON, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship

from core.database import Base


class WidgetType(str, Enum):
    """Available widget types"""
    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    HEATMAP = "heatmap"
    FUNNEL = "funnel"
    MAP = "map"
    TIMELINE = "timeline"
    MIXED = "mixed"
    INSIGHTS = "insights"
    CUSTOM = "custom"


class ChartType(str, Enum):
    """Available chart types"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    AREA = "area"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    RADAR = "radar"
    POLAR = "polar"
    COMBO = "combo"


class DashboardWidget(Base):
    """Dashboard widget configuration"""
    __tablename__ = "dashboard_widgets"
    
    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    widget_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String)
    
    # Widget configuration
    config = Column(JSON, nullable=False)
    position = Column(JSON, nullable=False)  # {x, y}
    size = Column(JSON, nullable=False)  # {width, height}
    
    # Visibility and permissions
    is_active = Column(Boolean, default=True)
    visibility = Column(String, default="private")  # private, team, public
    created_by = Column(String, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    layouts = relationship("DashboardLayoutWidget", back_populates="widget")


class DashboardLayout(Base):
    """Dashboard layout configuration"""
    __tablename__ = "dashboard_layouts"
    
    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    
    # Layout configuration
    widgets = Column(JSON, nullable=False)  # Array of widget positions
    grid_size = Column(JSON, default={"cols": 12, "rows": 8})
    
    # Settings
    is_default = Column(Boolean, default=False)
    is_shared = Column(Boolean, default=False)
    theme = Column(String, default="light")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    layout_widgets = relationship("DashboardLayoutWidget", back_populates="layout")


class DashboardLayoutWidget(Base):
    """Association table for layouts and widgets"""
    __tablename__ = "dashboard_layout_widgets"
    
    layout_id = Column(String, ForeignKey("dashboard_layouts.id"), primary_key=True)
    widget_id = Column(String, ForeignKey("dashboard_widgets.id"), primary_key=True)
    position = Column(JSON, nullable=False)
    size = Column(JSON, nullable=False)
    order = Column(Integer, default=0)
    
    # Relationships
    layout = relationship("DashboardLayout", back_populates="layout_widgets")
    widget = relationship("DashboardWidget", back_populates="layouts")


class DashboardFilter(Base):
    """Saved dashboard filters"""
    __tablename__ = "dashboard_filters"
    
    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    
    # Filter configuration
    filters = Column(JSON, nullable=False)
    is_global = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DashboardSnapshot(Base):
    """Dashboard snapshots for historical views"""
    __tablename__ = "dashboard_snapshots"
    
    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    layout_id = Column(String, ForeignKey("dashboard_layouts.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    
    # Snapshot data
    snapshot_data = Column(JSON, nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    
    # Metadata
    created_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
