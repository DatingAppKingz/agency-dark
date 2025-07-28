"""
Grafana dashboard definitions and provisioning
"""
import json
from typing import Dict, List, Any
from datetime import datetime


class GrafanaDashboard:
    """Base class for Grafana dashboards"""
    
    def __init__(self, title: str, uid: str, description: str = ""):
        self.title = title
        self.uid = uid
        self.description = description
        self.panels = []
        self.templating = {"list": []}
        self.time = {"from": "now-6h", "to": "now"}
        self.refresh = "10s"
    
    def add_panel(self, panel: Dict[str, Any]):
        """Add a panel to the dashboard"""
        panel["id"] = len(self.panels) + 1
        self.panels.append(panel)
    
    def add_variable(self, variable: Dict[str, Any]):
        """Add a template variable"""
        self.templating["list"].append(variable)
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to Grafana JSON format"""
        return {
            "dashboard": {
                "uid": self.uid,
                "title": self.title,
                "description": self.description,
                "panels": self.panels,
                "templating": self.templating,
                "time": self.time,
                "refresh": self.refresh,
                "schemaVersion": 30,
                "version": 1,
                "tags": ["agency", "monitoring"]
            },
            "overwrite": True
        }


def create_overview_dashboard() -> GrafanaDashboard:
    """Create main overview dashboard"""
    dashboard = GrafanaDashboard(
        title="Agency Platform Overview",
        uid="agency-overview",
        description="Main dashboard for Agency platform monitoring"
    )
    
    # Add variables
    dashboard.add_variable({
        "name": "datasource",
        "type": "datasource",
        "query": "prometheus",
        "current": {"text": "Prometheus", "value": "prometheus"},
        "hide": 0,
        "label": "Data Source"
    })
    
    # Request Rate Panel
    dashboard.add_panel({
        "title": "Request Rate",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [{
            "expr": 'sum(rate(http_requests_total[5m])) by (method)',
            "legendFormat": "{{method}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "reqps", "label": "Requests/sec"},
            {"format": "short"}
        ]
    })
    
    # Error Rate Panel
    dashboard.add_panel({
        "title": "Error Rate",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [{
            "expr": 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100',
            "legendFormat": "Error %",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "percent", "label": "Error Rate"},
            {"format": "short"}
        ],
        "alert": {
            "conditions": [{
                "evaluator": {"params": [5], "type": "gt"},
                "operator": {"type": "and"},
                "query": {"params": ["A", "5m", "now"]},
                "reducer": {"params": [], "type": "avg"},
                "type": "query"
            }],
            "executionErrorState": "alerting",
            "for": "5m",
            "frequency": "1m",
            "handler": 1,
            "name": "High Error Rate",
            "noDataState": "no_data",
            "notifications": []
        }
    })
    
    # Response Time Panel
    dashboard.add_panel({
        "title": "Response Time (95th percentile)",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [{
            "expr": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))',
            "legendFormat": "{{endpoint}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "s", "label": "Response Time"},
            {"format": "short"}
        ]
    })
    
    # Active Users Panel
    dashboard.add_panel({
        "title": "Active Users",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 8},
        "targets": [{
            "expr": 'active_users_total',
            "refId": "A"
        }],
        "options": {
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False
            },
            "textMode": "auto"
        }
    })
    
    # CPU Usage Panel
    dashboard.add_panel({
        "title": "CPU Usage",
        "type": "gauge",
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 8},
        "targets": [{
            "expr": 'system_cpu_usage_percent',
            "refId": "A"
        }],
        "options": {
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "fieldConfig": {
            "defaults": {
                "max": 100,
                "min": 0,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "yellow", "value": 70},
                        {"color": "red", "value": 90}
                    ]
                },
                "unit": "percent"
            }
        }
    })
    
    # Memory Usage Panel
    dashboard.add_panel({
        "title": "Memory Usage",
        "type": "gauge",
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 12},
        "targets": [{
            "expr": 'system_memory_usage_percent',
            "refId": "A"
        }],
        "options": {
            "showThresholdLabels": False,
            "showThresholdMarkers": True
        },
        "fieldConfig": {
            "defaults": {
                "max": 100,
                "min": 0,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "yellow", "value": 80},
                        {"color": "red", "value": 95}
                    ]
                },
                "unit": "percent"
            }
        }
    })
    
    # Database Connections Panel
    dashboard.add_panel({
        "title": "Database Connections",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 12},
        "targets": [{
            "expr": 'sum(database_connections_active)',
            "refId": "A"
        }],
        "options": {
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "center"
        }
    })
    
    return dashboard


def create_business_metrics_dashboard() -> GrafanaDashboard:
    """Create business metrics dashboard"""
    dashboard = GrafanaDashboard(
        title="Business Metrics",
        uid="agency-business",
        description="Business KPIs and metrics"
    )
    
    # Transaction Volume Panel
    dashboard.add_panel({
        "title": "Transaction Volume",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [{
            "expr": 'sum(rate(business_transactions_total[5m])) by (type)',
            "legendFormat": "{{type}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "short", "label": "Transactions/min"},
            {"format": "short"}
        ]
    })
    
    # Revenue Panel
    dashboard.add_panel({
        "title": "Revenue (Last 24h)",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
        "targets": [{
            "expr": 'sum(increase(business_transaction_amount_sum{currency="USD"}[24h]))',
            "refId": "A"
        }],
        "options": {
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "center"
        },
        "fieldConfig": {
            "defaults": {
                "unit": "currencyUSD",
                "decimals": 2
            }
        }
    })
    
    # Success Rate Panel
    dashboard.add_panel({
        "title": "Transaction Success Rate",
        "type": "gauge",
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
        "targets": [{
            "expr": 'sum(rate(business_transactions_total{status="success"}[5m])) / sum(rate(business_transactions_total[5m])) * 100',
            "refId": "A"
        }],
        "fieldConfig": {
            "defaults": {
                "max": 100,
                "min": 0,
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "red", "value": None},
                        {"color": "yellow", "value": 95},
                        {"color": "green", "value": 99}
                    ]
                },
                "unit": "percent"
            }
        }
    })
    
    # Top Content Creators Panel
    dashboard.add_panel({
        "title": "Top Content Creators",
        "type": "table",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [{
            "expr": 'topk(10, sum by (user_id) (increase(business_transactions_total{type="content_sale"}[24h])))',
            "format": "table",
            "instant": True,
            "refId": "A"
        }],
        "options": {
            "showHeader": True
        },
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "auto",
                    "displayMode": "auto"
                }
            }
        }
    })
    
    # Content Performance Panel
    dashboard.add_panel({
        "title": "Content Performance",
        "type": "heatmap",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        "targets": [{
            "expr": 'sum(increase(content_views_bucket[1h])) by (le)',
            "format": "heatmap",
            "refId": "A"
        }],
        "options": {
            "calculate": False,
            "cellGap": 1,
            "cellRadius": 1,
            "color": {
                "mode": "spectrum",
                "scheme": "Oranges"
            },
            "exemplars": {
                "color": "rgba(255,0,255,0.7)"
            },
            "filterValues": {
                "le": 1e-09
            },
            "legend": {
                "show": True
            },
            "rowsFrame": {
                "layout": "auto"
            },
            "tooltip": {
                "show": True,
                "yHistogram": False
            },
            "yAxis": {
                "axisPlacement": "left",
                "reverse": False
            }
        }
    })
    
    return dashboard


def create_infrastructure_dashboard() -> GrafanaDashboard:
    """Create infrastructure monitoring dashboard"""
    dashboard = GrafanaDashboard(
        title="Infrastructure",
        uid="agency-infra",
        description="Infrastructure and system metrics"
    )
    
    # System Overview Row
    dashboard.add_panel({
        "title": "System Overview",
        "type": "row",
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
        "collapsed": False
    })
    
    # CPU Usage by Core
    dashboard.add_panel({
        "title": "CPU Usage by Core",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 1},
        "targets": [{
            "expr": 'rate(process_cpu_seconds_total[5m]) * 100',
            "legendFormat": "Core {{cpu}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "percent", "label": "CPU Usage"},
            {"format": "short"}
        ]
    })
    
    # Memory Usage Breakdown
    dashboard.add_panel({
        "title": "Memory Usage Breakdown",
        "type": "piechart",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 1},
        "targets": [
            {
                "expr": 'node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes',
                "legendFormat": "Used",
                "refId": "A"
            },
            {
                "expr": 'node_memory_MemAvailable_bytes',
                "legendFormat": "Available",
                "refId": "B"
            }
        ],
        "options": {
            "pieType": "pie",
            "tooltip": {
                "displayMode": "single"
            },
            "legend": {
                "displayMode": "list",
                "placement": "right"
            }
        }
    })
    
    # Disk I/O
    dashboard.add_panel({
        "title": "Disk I/O",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 9},
        "targets": [
            {
                "expr": 'rate(node_disk_read_bytes_total[5m])',
                "legendFormat": "Read {{device}}",
                "refId": "A"
            },
            {
                "expr": 'rate(node_disk_written_bytes_total[5m])',
                "legendFormat": "Write {{device}}",
                "refId": "B"
            }
        ],
        "yaxes": [
            {"format": "Bps", "label": "Bytes/sec"},
            {"format": "short"}
        ]
    })
    
    # Network Traffic
    dashboard.add_panel({
        "title": "Network Traffic",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 9},
        "targets": [
            {
                "expr": 'rate(system_network_bytes_sent_total[5m])',
                "legendFormat": "Sent",
                "refId": "A"
            },
            {
                "expr": 'rate(system_network_bytes_received_total[5m])',
                "legendFormat": "Received",
                "refId": "B"
            }
        ],
        "yaxes": [
            {"format": "Bps", "label": "Bytes/sec"},
            {"format": "short"}
        ]
    })
    
    # Database Row
    dashboard.add_panel({
        "title": "Database Metrics",
        "type": "row",
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": 17},
        "collapsed": False
    })
    
    # Query Performance
    dashboard.add_panel({
        "title": "Database Query Performance",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 18},
        "targets": [{
            "expr": 'histogram_quantile(0.95, sum(rate(database_query_duration_seconds_bucket[5m])) by (le, operation))',
            "legendFormat": "{{operation}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "s", "label": "Query Time"},
            {"format": "short"}
        ]
    })
    
    # Connection Pool
    dashboard.add_panel({
        "title": "Database Connection Pool",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 18},
        "targets": [
            {
                "expr": 'database_connections_active',
                "legendFormat": "Active",
                "refId": "A"
            },
            {
                "expr": 'database_connections_idle',
                "legendFormat": "Idle",
                "refId": "B"
            }
        ],
        "yaxes": [
            {"format": "short", "label": "Connections"},
            {"format": "short"}
        ]
    })
    
    return dashboard


def create_error_tracking_dashboard() -> GrafanaDashboard:
    """Create error tracking dashboard"""
    dashboard = GrafanaDashboard(
        title="Error Tracking",
        uid="agency-errors",
        description="Application errors and exceptions"
    )
    
    # Error Rate by Category
    dashboard.add_panel({
        "title": "Errors by Category",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [{
            "expr": 'sum(rate(application_errors_total[5m])) by (category)',
            "legendFormat": "{{category}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "short", "label": "Errors/min"},
            {"format": "short"}
        ]
    })
    
    # Error Severity Distribution
    dashboard.add_panel({
        "title": "Error Severity Distribution",
        "type": "piechart",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [{
            "expr": 'sum(increase(application_errors_total[1h])) by (severity)',
            "legendFormat": "{{severity}}",
            "refId": "A"
        }],
        "options": {
            "pieType": "donut",
            "tooltip": {
                "displayMode": "single"
            },
            "legend": {
                "displayMode": "table",
                "placement": "right",
                "values": ["value", "percent"]
            }
        }
    })
    
    # Top Errors Table
    dashboard.add_panel({
        "title": "Top Errors (Last Hour)",
        "type": "table",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 8},
        "targets": [{
            "expr": 'topk(10, sum by (error_type) (increase(application_errors_total[1h])))',
            "format": "table",
            "instant": True,
            "refId": "A"
        }],
        "options": {
            "showHeader": True,
            "sortBy": [
                {
                    "desc": True,
                    "displayName": "Value"
                }
            ]
        }
    })
    
    # Critical Errors Timeline
    dashboard.add_panel({
        "title": "Critical Errors Timeline",
        "type": "graph",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
        "targets": [{
            "expr": 'sum(rate(application_errors_total{severity="critical"}[5m])) by (error_type)',
            "legendFormat": "{{error_type}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "short", "label": "Errors/min"},
            {"format": "short"}
        ],
        "alert": {
            "conditions": [{
                "evaluator": {"params": [0], "type": "gt"},
                "operator": {"type": "and"},
                "query": {"params": ["A", "5m", "now"]},
                "reducer": {"params": [], "type": "max"},
                "type": "query"
            }],
            "executionErrorState": "alerting",
            "for": "1m",
            "frequency": "30s",
            "handler": 1,
            "name": "Critical Error Detected",
            "noDataState": "no_data",
            "notifications": []
        }
    })
    
    return dashboard


def create_celery_dashboard() -> GrafanaDashboard:
    """Create Celery task monitoring dashboard"""
    dashboard = GrafanaDashboard(
        title="Celery Tasks",
        uid="agency-celery",
        description="Celery task queue monitoring"
    )
    
    # Task Throughput
    dashboard.add_panel({
        "title": "Task Throughput",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
            {
                "expr": 'sum(rate(celery_tasks_total{status="success"}[5m]))',
                "legendFormat": "Success",
                "refId": "A"
            },
            {
                "expr": 'sum(rate(celery_tasks_total{status="failure"}[5m]))',
                "legendFormat": "Failure",
                "refId": "B"
            }
        ],
        "yaxes": [
            {"format": "short", "label": "Tasks/min"},
            {"format": "short"}
        ]
    })
    
    # Task Duration
    dashboard.add_panel({
        "title": "Task Duration (95th percentile)",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [{
            "expr": 'histogram_quantile(0.95, sum(rate(celery_task_duration_seconds_bucket[5m])) by (le, task_name))',
            "legendFormat": "{{task_name}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "s", "label": "Duration"},
            {"format": "short"}
        ]
    })
    
    # Queue Size
    dashboard.add_panel({
        "title": "Queue Size",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [{
            "expr": 'queue_size',
            "legendFormat": "{{queue_name}}",
            "refId": "A"
        }],
        "yaxes": [
            {"format": "short", "label": "Messages"},
            {"format": "short"}
        ]
    })
    
    # Task Success Rate
    dashboard.add_panel({
        "title": "Task Success Rate",
        "type": "stat",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
        "targets": [{
            "expr": 'sum(rate(celery_tasks_total{status="success"}[5m])) / sum(rate(celery_tasks_total[5m])) * 100',
            "refId": "A"
        }],
        "options": {
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False
            },
            "textMode": "auto"
        },
        "fieldConfig": {
            "defaults": {
                "unit": "percent",
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "red", "value": None},
                        {"color": "yellow", "value": 95},
                        {"color": "green", "value": 99}
                    ]
                }
            }
        }
    })
    
    return dashboard


# Dashboard provisioning
def provision_dashboards() -> List[Dict[str, Any]]:
    """Generate all dashboard configurations for provisioning"""
    dashboards = [
        create_overview_dashboard(),
        create_business_metrics_dashboard(),
        create_infrastructure_dashboard(),
        create_error_tracking_dashboard(),
        create_celery_dashboard()
    ]
    
    return [dashboard.to_json() for dashboard in dashboards]


def save_dashboards_to_files(output_dir: str = "./dashboards"):
    """Save dashboard JSON files for manual import"""
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    dashboards = provision_dashboards()
    for dashboard_config in dashboards:
        dashboard = dashboard_config["dashboard"]
        filename = f"{dashboard['uid']}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(dashboard_config, f, indent=2)
        
        print(f"Saved dashboard '{dashboard['title']}' to {filepath}")


# Grafana API client for automated provisioning
class GrafanaAPIClient:
    """Client for Grafana HTTP API"""
    
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_dashboard(self, dashboard_json: Dict[str, Any]):
        """Create or update a dashboard"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/api/dashboards/db",
                json=dashboard_json,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def provision_all_dashboards(self):
        """Provision all dashboards"""
        dashboards = provision_dashboards()
        results = []
        
        for dashboard_config in dashboards:
            try:
                result = await self.create_dashboard(dashboard_config)
                results.append({
                    "title": dashboard_config["dashboard"]["title"],
                    "uid": dashboard_config["dashboard"]["uid"],
                    "status": "success",
                    "url": result.get("url")
                })
            except Exception as e:
                results.append({
                    "title": dashboard_config["dashboard"]["title"],
                    "uid": dashboard_config["dashboard"]["uid"],
                    "status": "error",
                    "error": str(e)
                })
        
        return results


if __name__ == "__main__":
    # Save dashboards to files for manual import
    save_dashboards_to_files()
