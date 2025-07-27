from fastapi import APIRouter

from .endpoints import auth
from modules.inflow_wrapper.api import router as inflow_router
from modules.onlyfans_wrapper.api import router as onlyfans_router
from modules.api_orchestration.api.endpoints import router as orchestration_router
from core.webhooks.handlers import router as webhook_router
from modules.analytics.api import router as analytics_router
from modules.financial.api import router as financial_router
from modules.financial.api.webhook_endpoints import router as payment_webhook_router
from modules.whitelabel.api.routes import router as whitelabel_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(inflow_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(onlyfans_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(orchestration_router, tags=["orchestration"])
api_router.include_router(webhook_router, tags=["webhooks"])
api_router.include_router(payment_webhook_router, prefix="/payments", tags=["payment-webhooks"])
api_router.include_router(analytics_router, tags=["analytics"])
api_router.include_router(financial_router, tags=["financial"])
api_router.include_router(whitelabel_router, tags=["whitelabel"])