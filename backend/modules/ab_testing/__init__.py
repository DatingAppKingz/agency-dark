"""
A/B Testing Framework for AgencyDark

This module provides comprehensive A/B testing capabilities for:
- Message content and timing
- Pricing strategies
- UI/UX variations
- Content recommendations
- Engagement strategies
"""

from .core.experiment_manager import ExperimentManager
from .core.traffic_splitter import TrafficSplitter
from .core.metrics_collector import MetricsCollector
from .analysis.statistical_engine import StatisticalEngine

__all__ = [
    "ExperimentManager",
    "TrafficSplitter",
    "MetricsCollector",
    "StatisticalEngine"
]
