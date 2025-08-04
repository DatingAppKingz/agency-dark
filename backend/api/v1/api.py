from fastapi import APIRouter

from .endpoints import auth, auth_minimal, api_keys, api_keys_management, rate_limits, fraud_detection, bulk_operations, reports, ml_analytics, monitoring, users, sync_status, ml_insights_advanced, chat, webhook_receiver, webhook_queue, sync_scheduler, api_usage, api_audit, sync_dashboard, sync_conflicts, sync_error_monitoring, realtime_analytics, media, search, notifications, translations, data_export, data_import, cache, external_api, enhanced_reports, schedule, models, models_bulk, payouts, invoices, email_preferences
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
api_router.include_router(auth_minimal.router, prefix="/auth", tags=["authentication-minimal"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(models_bulk.router, prefix="/models", tags=["models-bulk"])
api_router.include_router(payouts.router, prefix="/payouts", tags=["payouts"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(email_preferences.router, prefix="/email", tags=["email"])
api_router.include_router(media.router, tags=["media"])
api_router.include_router(sync_status.router, tags=["sync"])
api_router.include_router(sync_scheduler.router, tags=["sync-scheduler"])
api_router.include_router(sync_dashboard.router, tags=["sync-dashboard"])
api_router.include_router(sync_conflicts.router, tags=["sync-conflicts"])
api_router.include_router(sync_error_monitoring.router, tags=["sync-errors"])
api_router.include_router(realtime_analytics.router, tags=["realtime-analytics"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(api_keys_management.router, tags=["api-keys-management"])
api_router.include_router(secure_api_keys_router, tags=["api-keys-secure"])
api_router.include_router(api_usage.router, tags=["api-usage"])
api_router.include_router(api_audit.router, tags=["api-audit"])
api_router.include_router(rate_limits.router, tags=["rate-limits"])
api_router.include_router(fraud_detection.router, tags=["fraud-detection"])
api_router.include_router(bulk_operations.router, tags=["bulk-operations"])
api_router.include_router(inflow_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(onlyfans_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(orchestration_router, tags=["orchestration"])
api_router.include_router(orchestration_v2_router, tags=["orchestration-v2"])
api_router.include_router(webhook_handler_router, tags=["webhook-handlers"])
api_router.include_router(webhook_management_router, tags=["webhooks"])
api_router.include_router(webhook_receiver.router, tags=["webhook-receiver"])
api_router.include_router(webhook_queue.router, tags=["webhook-queue"])
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

# External API Management
api_router.include_router(external_api.router, tags=["external-api"])

# Enhanced Reports with Charts
api_router.include_router(enhanced_reports.router, tags=["enhanced-reports"])

# Schedule Management
api_router.include_router(schedule.router, tags=["schedule"])

# Materialized Views
from .materialized_views import router as materialized_views_router
api_router.include_router(materialized_views_router, tags=["materialized-views"])

# Advanced ML Insights
api_router.include_router(ml_insights_advanced.router, prefix="/ml-insights", tags=["ml-insights-advanced"])

# SSO Integration
from modules.sso.api import router as sso_router, scim_router
api_router.include_router(sso_router, tags=["sso"])
api_router.include_router(scim_router, tags=["scim"])

# Search
api_router.include_router(search.router, tags=["search"])

# Notifications
api_router.include_router(notifications.router, tags=["notifications"])

# Translations
api_router.include_router(translations.router, tags=["translations"])

# Data Export/Import
api_router.include_router(data_export.router, tags=["exports"])
api_router.include_router(data_import.router, tags=["imports"])

# Cache Management
api_router.include_router(cache.router, tags=["cache"])