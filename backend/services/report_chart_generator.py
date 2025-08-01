"""Chart generation service for reports."""

import io
import base64
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import seaborn as sns
import pandas as pd
import numpy as np

from core.logger import get_logger

logger = get_logger(__name__)


class ReportChartGenerator:
    """Service for generating charts for reports."""
    
    def __init__(self):
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        
        # Default colors
        self.colors = {
            'primary': '#3B82F6',
            'secondary': '#10B981',
            'accent': '#F59E0B',
            'danger': '#EF4444',
            'success': '#10B981',
            'warning': '#F59E0B',
            'info': '#3B82F6'
        }
    
    async def generate_revenue_chart(
        self,
        data: List[Dict[str, Any]],
        chart_type: str = 'line',
        title: str = 'Revenue Overview',
        size: tuple = (10, 6)
    ) -> str:
        """
        Generate revenue chart.
        
        Args:
            data: List of revenue data points
            chart_type: Type of chart (line, bar, area)
            title: Chart title
            size: Figure size (width, height)
            
        Returns:
            Base64 encoded image string
        """
        try:
            fig, ax = plt.subplots(figsize=size)
            
            # Prepare data
            df = pd.DataFrame(data)
            if 'period' in df.columns:
                df['period'] = pd.to_datetime(df['period'])
                df = df.sort_values('period')
            
            # Generate based on chart type
            if chart_type == 'line':
                ax.plot(df['period'], df['gross_revenue'], 
                       label='Gross Revenue', color=self.colors['primary'], linewidth=2)
                ax.plot(df['period'], df['net_revenue'], 
                       label='Net Revenue', color=self.colors['secondary'], linewidth=2)
                ax.fill_between(df['period'], df['gross_revenue'], df['net_revenue'],
                               alpha=0.3, color=self.colors['warning'], label='Platform Fees')
            
            elif chart_type == 'bar':
                x = np.arange(len(df))
                width = 0.35
                ax.bar(x - width/2, df['gross_revenue'], width, 
                      label='Gross Revenue', color=self.colors['primary'])
                ax.bar(x + width/2, df['net_revenue'], width,
                      label='Net Revenue', color=self.colors['secondary'])
                ax.set_xticks(x)
                ax.set_xticklabels([d.strftime('%Y-%m-%d') for d in df['period']], rotation=45)
            
            elif chart_type == 'area':
                ax.fill_between(df['period'], 0, df['gross_revenue'],
                               alpha=0.7, color=self.colors['primary'], label='Gross Revenue')
                ax.fill_between(df['period'], 0, df['net_revenue'],
                               alpha=0.7, color=self.colors['secondary'], label='Net Revenue')
            
            # Format chart
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Revenue ($)', fontsize=12)
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            
            # Format dates on x-axis
            if chart_type != 'bar':
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                plt.xticks(rotation=45)
            
            # Format y-axis with currency
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
            
            plt.tight_layout()
            
            # Convert to base64
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating revenue chart: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_performance_chart(
        self,
        data: Dict[str, Any],
        metric: str = 'response_rate',
        title: str = 'Performance Metrics',
        size: tuple = (10, 6)
    ) -> str:
        """Generate performance metrics chart."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            # Extract metric data
            metric_data = data.get(metric, {})
            
            if metric == 'response_rate':
                # Pie chart for response rates
                labels = list(metric_data.keys())
                values = list(metric_data.values())
                colors = [self.colors[c] for c in ['primary', 'secondary', 'accent', 'warning']][:len(labels)]
                
                ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%',
                      startangle=90, textprops={'fontsize': 12})
                ax.set_title(title, fontsize=16, fontweight='bold')
                
            elif metric == 'daily_messages':
                # Line chart for daily messages
                df = pd.DataFrame(metric_data)
                df['date'] = pd.to_datetime(df['date'])
                
                ax.plot(df['date'], df['sent'], label='Sent', 
                       color=self.colors['primary'], linewidth=2, marker='o')
                ax.plot(df['date'], df['received'], label='Received', 
                       color=self.colors['secondary'], linewidth=2, marker='s')
                
                ax.set_title(title, fontsize=16, fontweight='bold')
                ax.set_xlabel('Date', fontsize=12)
                ax.set_ylabel('Messages', fontsize=12)
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                # Format dates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                plt.xticks(rotation=45)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating performance chart: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_comparison_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_fields: List[str],
        title: str = 'Comparison Chart',
        chart_type: str = 'bar',
        size: tuple = (12, 6)
    ) -> str:
        """Generate comparison chart for multiple metrics."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            df = pd.DataFrame(data)
            
            if chart_type == 'bar':
                # Grouped bar chart
                x = np.arange(len(df))
                width = 0.8 / len(y_fields)
                
                for i, field in enumerate(y_fields):
                    offset = (i - len(y_fields)/2 + 0.5) * width
                    ax.bar(x + offset, df[field], width, 
                          label=field.replace('_', ' ').title(),
                          color=list(self.colors.values())[i])
                
                ax.set_xlabel(x_field.replace('_', ' ').title(), fontsize=12)
                ax.set_xticks(x)
                ax.set_xticklabels(df[x_field], rotation=45 if len(df[x_field].astype(str)[0]) > 10 else 0)
                
            elif chart_type == 'line':
                # Multiple line chart
                for i, field in enumerate(y_fields):
                    ax.plot(df[x_field], df[field], 
                           label=field.replace('_', ' ').title(),
                           color=list(self.colors.values())[i],
                           linewidth=2, marker='o')
                
                ax.set_xlabel(x_field.replace('_', ' ').title(), fontsize=12)
                plt.xticks(rotation=45)
            
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_ylabel('Value', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating comparison chart: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_heatmap(
        self,
        data: Dict[str, Dict[str, float]],
        title: str = 'Activity Heatmap',
        size: tuple = (12, 8)
    ) -> str:
        """Generate heatmap visualization."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Create heatmap
            sns.heatmap(df, annot=True, fmt='.0f', cmap='YlOrRd',
                       cbar_kws={'label': 'Activity'}, ax=ax)
            
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_xlabel('Hour of Day', fontsize=12)
            ax.set_ylabel('Day of Week', fontsize=12)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating heatmap: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_distribution_chart(
        self,
        data: List[float],
        title: str = 'Distribution',
        chart_type: str = 'histogram',
        bins: int = 30,
        size: tuple = (10, 6)
    ) -> str:
        """Generate distribution chart."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            if chart_type == 'histogram':
                ax.hist(data, bins=bins, color=self.colors['primary'], 
                       alpha=0.7, edgecolor='black')
                ax.set_ylabel('Frequency', fontsize=12)
                
            elif chart_type == 'boxplot':
                box = ax.boxplot(data, patch_artist=True)
                box['boxes'][0].set_facecolor(self.colors['primary'])
                box['medians'][0].set_color(self.colors['danger'])
                
            elif chart_type == 'violin':
                parts = ax.violinplot([data], showmeans=True, showmedians=True)
                for pc in parts['bodies']:
                    pc.set_facecolor(self.colors['primary'])
                    pc.set_alpha(0.7)
            
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_xlabel('Value', fontsize=12)
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating distribution chart: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_trend_chart(
        self,
        data: List[Dict[str, Any]],
        date_field: str = 'date',
        value_field: str = 'value',
        trend_line: bool = True,
        title: str = 'Trend Analysis',
        size: tuple = (12, 6)
    ) -> str:
        """Generate trend chart with optional trend line."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            # Prepare data
            df = pd.DataFrame(data)
            df[date_field] = pd.to_datetime(df[date_field])
            df = df.sort_values(date_field)
            
            # Plot main data
            ax.plot(df[date_field], df[value_field], 
                   color=self.colors['primary'], linewidth=2, 
                   marker='o', markersize=6, label='Actual')
            
            # Add trend line if requested
            if trend_line and len(df) > 1:
                # Convert dates to numeric for regression
                x_numeric = mdates.date2num(df[date_field])
                z = np.polyfit(x_numeric, df[value_field], 1)
                p = np.poly1d(z)
                
                ax.plot(df[date_field], p(x_numeric), 
                       color=self.colors['danger'], linewidth=2, 
                       linestyle='--', label='Trend')
            
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel(value_field.replace('_', ' ').title(), fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Format dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating trend chart: {e}")
            raise
        finally:
            plt.close('all')
    
    async def generate_funnel_chart(
        self,
        data: Dict[str, int],
        title: str = 'Conversion Funnel',
        size: tuple = (10, 8)
    ) -> str:
        """Generate funnel chart for conversion analysis."""
        try:
            fig, ax = plt.subplots(figsize=size)
            
            # Prepare data
            stages = list(data.keys())
            values = list(data.values())
            
            # Calculate percentages
            max_value = max(values) if values else 1
            percentages = [v/max_value * 100 for v in values]
            
            # Create funnel
            y_pos = np.arange(len(stages))
            
            for i, (stage, value, pct) in enumerate(zip(stages, values, percentages)):
                width = pct / 100
                ax.barh(i, width, height=0.8, 
                       left=(1-width)/2,  # Center the bar
                       color=self.colors['primary'], 
                       alpha=0.8 - i*0.1)  # Gradient effect
                
                # Add labels
                ax.text(0.5, i, f'{stage}\n{value:,} ({pct:.1f}%)', 
                       ha='center', va='center', fontsize=12, fontweight='bold')
            
            ax.set_xlim(0, 1)
            ax.set_ylim(-0.5, len(stages)-0.5)
            ax.set_yticks([])
            ax.set_xticks([])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating funnel chart: {e}")
            raise
        finally:
            plt.close('all')
    
    def _fig_to_base64(self, fig: Figure) -> str:
        """Convert matplotlib figure to base64 string."""
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        buffer.close()
        return f"data:image/png;base64,{image_base64}"


# Singleton instance
_chart_generator = None


def get_report_chart_generator() -> ReportChartGenerator:
    """Get singleton instance of report chart generator."""
    global _chart_generator
    if _chart_generator is None:
        _chart_generator = ReportChartGenerator()
    return _chart_generator