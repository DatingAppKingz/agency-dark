from fastapi import APIRouter

from .endpoints import auth, api_keys, rate_limits, fraud_detection, bulk_operations, reports, ml_analytics, monitoring
from .secure_api_keys import router as secure_api_keys_router
from .monitoring.performance import router as performance_router
from .mobile import auth as mobile_auth, messages as mobile_messages, analytics as mobile_analytics, notifications as mobile_notifications
from .analytics_dashboard import router as analytics_dashboard_router
from modules.inflow_wrapper.api import router as inflow_router
from modules.onlyfans_wrapper.api import router as onlyfans_router
from modules.api_orchestration.api.endpoints import router as orchestration_router
from modules.api_orchestration.api.endpoints_v2 import router as orchestration_v2_router
from core.webhooks.handlers import router as webhook_handler_router
from api.v1.webhooks import router as webhook_management_router
from modules.analytics.api import router as analytics_router
from modules.financial.api import router as financial_router
from modules.financial.api.webhook_endpoints import router as payment_webhook_router
from modules.whitelabel.api.routes import router as whitelabel_router
from .docs import router as docs_router
from .experiments import router as experiments_router
from .performance import router as performance_optimization_router
from .partitions import router as partitions_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(api_keys.router, tags=["api-keys"])
api_router.include_router(secure_api_keys_router, tags=["api-keys-secure"])
api_router.include_router(rate_limits.router, tags=["rate-limits"])
api_router.include_router(fraud_detection.router, tags=["fraud-detection"])
api_router.include_router(bulk_operations.router, tags=["bulk-operations"])
api_router.include_router(inflow_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(onlyfans_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(orchestration_router, tags=["orchestration"])
api_router.include_router(orchestration_v2_router, tags=["orchestration-v2"])
api_router.include_router(webhook_handler_router, tags=["webhook-handlers"])
api_router.include_router(webhook_management_router, tags=["webhooks"])
api_router.include_router(payment_webhook_router, prefix="/payments", tags=["payment-webhooks"])
api_router.include_router(analytics_router, tags=["analytics"])
api_router.include_router(financial_router, tags=["financial"])
api_router.include_router(whitelabel_router, tags=["whitelabel"])
api_router.include_router(performance_router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(monitoring.router, tags=["monitoring"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(ml_analytics.router, tags=["ml-analytics"])
api_router.include_router(docs_router, tags=["documentation"])

# Mobile API endpoints
api_router.include_router(mobile_auth.router, tags=["mobile"])
api_router.include_router(mobile_messages.router, tags=["mobile"])
api_router.include_router(mobile_analytics.router, tags=["mobile"])
api_router.include_router(mobile_notifications.router, tags=["mobile"])

# Analytics dashboard
api_router.include_router(analytics_dashboard_router, tags=["analytics-dashboard"])

# A/B Testing
api_router.include_router(experiments_router, tags=["experiments"])

# Performance Optimization
api_router.include_router(performance_optimization_router, tags=["performance"])

# Database Partitioning
api_router.include_router(partitions_router, tags=["partitions"])

# Materialized Views
from .materialized_views import router as materialized_views_router
api_router.include_router(materialized_views_router, tags=["materialized-views"])