"""
Chart data generator for various visualization types
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

from core.logging import get_logger
from .models import ChartType

logger = get_logger(__name__)


class ChartGenerator:
    """Generate chart data for frontend visualization"""
    
    def __init__(self):
        self._chart_generators = {
            ChartType.LINE: self._generate_line_chart,
            ChartType.BAR: self._generate_bar_chart,
            ChartType.PIE: self._generate_pie_chart,
            ChartType.AREA: self._generate_area_chart,
            ChartType.SCATTER: self._generate_scatter_chart,
            ChartType.BUBBLE: self._generate_bubble_chart,
            ChartType.RADAR: self._generate_radar_chart,
            ChartType.DOUGHNUT: self._generate_doughnut_chart,
            ChartType.COMBO: self._generate_combo_chart
        }
        
    async def generate_chart(
        self,
        data: Dict[str, Any],
        chart_type: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate chart data based on type"""
        generator = self._chart_generators.get(ChartType(chart_type))
        
        if not generator:
            raise ValueError(f"Unsupported chart type: {chart_type}")
            
        options = options or {}
        
        try:
            chart_data = await generator(data, options)
            
            # Add common chart options
            chart_data["options"] = {
                "responsive": True,
                "maintainAspectRatio": False,
                "animation": {
                    "duration": options.get("animation_duration", 750)
                },
                **options
            }
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error generating {chart_type} chart: {e}")
            raise
            
    async def _generate_line_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate line chart data"""
        # Extract time series data
        time_series = data.get("time_series", [])
        
        if not time_series:
            return self._empty_chart("line")
            
        # Prepare labels and datasets
        labels = []
        datasets = defaultdict(list)
        
        for point in time_series:
            labels.append(self._format_date_label(point["date"], options))
            
            for key, value in point.items():
                if key != "date":
                    datasets[key].append(value)
                    
        # Format datasets for Chart.js
        chart_datasets = []
        colors = self._get_color_palette(len(datasets))
        
        for i, (key, values) in enumerate(datasets.items()):
            dataset = {
                "label": self._format_label(key),
                "data": values,
                "borderColor": colors[i],
                "backgroundColor": self._add_alpha(colors[i], 0.1),
                "tension": options.get("line_tension", 0.1),
                "fill": options.get("fill", True)
            }
            
            # Add trendline if requested
            if options.get("show_trendline"):
                dataset["trendlineLinear"] = {
                    "style": "rgba(255, 105, 180, .8)",
                    "lineStyle": "dotted",
                    "width": 2
                }
                
            chart_datasets.append(dataset)
            
        return {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": chart_datasets
            },
            "options": {
                "scales": {
                    "y": {
                        "beginAtZero": options.get("begin_at_zero", True),
                        "ticks": {
                            "callback": "value"  # Will be processed on frontend
                        }
                    }
                },
                "plugins": {
                    "legend": {
                        "display": options.get("show_legend", True)
                    },
                    "tooltip": {
                        "mode": "index",
                        "intersect": False
                    }
                }
            }
        }
        
    async def _generate_bar_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate bar chart data"""
        categories = data.get("categories", [])
        values = data.get("values", [])
        
        if not categories or not values:
            return self._empty_chart("bar")
            
        # Handle multiple series
        if isinstance(values[0], dict):
            # Multiple series
            datasets = []
            colors = self._get_color_palette(len(values[0]))
            
            for i, (key, _) in enumerate(values[0].items()):
                dataset_values = [v.get(key, 0) for v in values]
                datasets.append({
                    "label": self._format_label(key),
                    "data": dataset_values,
                    "backgroundColor": colors[i],
                    "borderColor": colors[i],
                    "borderWidth": 1
                })
        else:
            # Single series
            colors = self._get_color_palette(len(categories))
            datasets = [{
                "label": options.get("label", "Value"),
                "data": values,
                "backgroundColor": colors,
                "borderColor": colors,
                "borderWidth": 1
            }]
            
        return {
            "type": "bar",
            "data": {
                "labels": categories,
                "datasets": datasets
            },
            "options": {
                "scales": {
                    "y": {
                        "beginAtZero": True
                    }
                },
                "plugins": {
                    "legend": {
                        "display": len(datasets) > 1
                    }
                }
            }
        }
        
    async def _generate_pie_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate pie chart data"""
        labels = data.get("labels", [])
        values = data.get("values", [])
        
        if not labels or not values:
            return self._empty_chart("pie")
            
        colors = self._get_color_palette(len(labels))
        
        return {
            "type": "pie",
            "data": {
                "labels": labels,
                "datasets": [{
                    "data": values,
                    "backgroundColor": colors,
                    "borderColor": "#fff",
                    "borderWidth": 2
                }]
            },
            "options": {
                "plugins": {
                    "legend": {
                        "position": options.get("legend_position", "right")
                    },
                    "tooltip": {
                        "callbacks": {
                            "label": "percentage"  # Will be processed on frontend
                        }
                    }
                }
            }
        }
        
    async def _generate_area_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate area chart data"""
        # Similar to line chart but with fill
        line_chart = await self._generate_line_chart(data, {**options, "fill": True})
        line_chart["type"] = "line"  # Area is just a line chart with fill
        
        # Adjust transparency for area
        for dataset in line_chart["data"]["datasets"]:
            if "backgroundColor" in dataset:
                dataset["backgroundColor"] = self._add_alpha(
                    dataset["borderColor"], 
                    options.get("fill_opacity", 0.3)
                )
                
        return line_chart
        
    async def _generate_scatter_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate scatter chart data"""
        points = data.get("points", [])
        
        if not points:
            return self._empty_chart("scatter")
            
        # Group points by series if available
        series_data = defaultdict(list)
        
        for point in points:
            series = point.get("series", "default")
            series_data[series].append({
                "x": point.get("x", 0),
                "y": point.get("y", 0)
            })
            
        # Create datasets
        datasets = []
        colors = self._get_color_palette(len(series_data))
        
        for i, (series, points) in enumerate(series_data.items()):
            datasets.append({
                "label": series,
                "data": points,
                "backgroundColor": colors[i],
                "borderColor": colors[i]
            })
            
        return {
            "type": "scatter",
            "data": {
                "datasets": datasets
            },
            "options": {
                "scales": {
                    "x": {
                        "type": "linear",
                        "position": "bottom"
                    },
                    "y": {
                        "type": "linear"
                    }
                }
            }
        }
        
    async def _generate_bubble_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate bubble chart data"""
        bubbles = data.get("bubbles", [])
        
        if not bubbles:
            return self._empty_chart("bubble")
            
        # Group by series
        series_data = defaultdict(list)
        
        for bubble in bubbles:
            series = bubble.get("series", "default")
            series_data[series].append({
                "x": bubble.get("x", 0),
                "y": bubble.get("y", 0),
                "r": bubble.get("size", 5)
            })
            
        # Create datasets
        datasets = []
        colors = self._get_color_palette(len(series_data))
        
        for i, (series, bubbles) in enumerate(series_data.items()):
            datasets.append({
                "label": series,
                "data": bubbles,
                "backgroundColor": self._add_alpha(colors[i], 0.6),
                "borderColor": colors[i]
            })
            
        return {
            "type": "bubble",
            "data": {
                "datasets": datasets
            },
            "options": {
                "scales": {
                    "x": {
                        "type": "linear",
                        "position": "bottom"
                    },
                    "y": {
                        "type": "linear"
                    }
                }
            }
        }
        
    async def _generate_radar_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate radar chart data"""
        labels = data.get("labels", [])
        datasets_data = data.get("datasets", [])
        
        if not labels or not datasets_data:
            return self._empty_chart("radar")
            
        datasets = []
        colors = self._get_color_palette(len(datasets_data))
        
        for i, dataset in enumerate(datasets_data):
            datasets.append({
                "label": dataset.get("label", f"Series {i+1}"),
                "data": dataset.get("values", []),
                "backgroundColor": self._add_alpha(colors[i], 0.2),
                "borderColor": colors[i],
                "pointBackgroundColor": colors[i],
                "pointBorderColor": "#fff",
                "pointHoverBackgroundColor": "#fff",
                "pointHoverBorderColor": colors[i]
            })
            
        return {
            "type": "radar",
            "data": {
                "labels": labels,
                "datasets": datasets
            },
            "options": {
                "elements": {
                    "line": {
                        "borderWidth": 3
                    }
                }
            }
        }
        
    async def _generate_doughnut_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate doughnut chart data"""
        # Same as pie chart but with cutout
        pie_chart = await self._generate_pie_chart(data, options)
        pie_chart["type"] = "doughnut"
        pie_chart["options"]["cutout"] = options.get("cutout", "50%")
        
        return pie_chart
        
    async def _generate_combo_chart(
        self,
        data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate combination chart (bar + line)"""
        labels = data.get("labels", [])
        bar_data = data.get("bar_data", [])
        line_data = data.get("line_data", [])
        
        if not labels:
            return self._empty_chart("bar")
            
        colors = self._get_color_palette(2)
        
        datasets = []
        
        # Bar dataset
        if bar_data:
            datasets.append({
                "label": options.get("bar_label", "Bar Data"),
                "data": bar_data,
                "type": "bar",
                "backgroundColor": colors[0],
                "borderColor": colors[0],
                "order": 2
            })
            
        # Line dataset
        if line_data:
            datasets.append({
                "label": options.get("line_label", "Line Data"),
                "data": line_data,
                "type": "line",
                "borderColor": colors[1],
                "backgroundColor": self._add_alpha(colors[1], 0.1),
                "order": 1
            })
            
        return {
            "type": "bar",
            "data": {
                "labels": labels,
                "datasets": datasets
            },
            "options": {
                "scales": {
                    "y": {
                        "beginAtZero": True
                    }
                }
            }
        }
        
    def _empty_chart(self, chart_type: str) -> Dict[str, Any]:
        """Return empty chart structure"""
        return {
            "type": chart_type,
            "data": {
                "labels": [],
                "datasets": []
            },
            "options": {}
        }
        
    def _format_date_label(self, date: Any, options: Dict[str, Any]) -> str:
        """Format date for chart label"""
        if isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif not isinstance(date, datetime):
            return str(date)
            
        format_type = options.get("date_format", "short")
        
        if format_type == "short":
            return date.strftime("%m/%d")
        elif format_type == "medium":
            return date.strftime("%b %d")
        elif format_type == "long":
            return date.strftime("%B %d, %Y")
        else:
            return date.strftime(format_type)
            
    def _format_label(self, key: str) -> str:
        """Format data key as readable label"""
        # Convert snake_case to Title Case
        return key.replace("_", " ").title()
        
    def _get_color_palette(self, count: int) -> List[str]:
        """Get color palette for charts"""
        # Professional color palette
        base_colors = [
            "#4F46E5",  # Indigo
            "#10B981",  # Emerald
            "#F59E0B",  # Amber
            "#EF4444",  # Red
            "#8B5CF6",  # Violet
            "#3B82F6",  # Blue
            "#EC4899",  # Pink
            "#14B8A6",  # Teal
            "#F97316",  # Orange
            "#6366F1",  # Indigo light
        ]
        
        if count <= len(base_colors):
            return base_colors[:count]
            
        # Generate additional colors if needed
        colors = base_colors.copy()
        while len(colors) < count:
            # Create variations of existing colors
            for base_color in base_colors:
                if len(colors) >= count:
                    break
                colors.append(self._lighten_color(base_color, 0.2))
                
        return colors[:count]
        
    def _add_alpha(self, color: str, alpha: float) -> str:
        """Add alpha channel to hex color"""
        if color.startswith("#"):
            # Convert hex to rgba
            hex_color = color.lstrip("#")
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"
        return color
        
    def _lighten_color(self, color: str, factor: float) -> str:
        """Lighten a color by a factor"""
        if color.startswith("#"):
            hex_color = color.lstrip("#")
            rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
            
            # Lighten each component
            rgb = [min(255, int(c + (255 - c) * factor)) for c in rgb]
            
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        return color
