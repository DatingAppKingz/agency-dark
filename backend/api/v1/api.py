from fastapi import APIRouter

from .endpoints import auth
from backend.modules.inflow_wrapper.api import router as inflow_router
from backend.modules.onlyfans_wrapper.api import router as onlyfans_router
from backend.modules.api_orchestration.api.endpoints import router as orchestration_router
from backend.core.webhooks.handlers import router as webhook_router
from backend.modules.analytics.api import router as analytics_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(inflow_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(onlyfans_router, prefix="/integrations", tags=["integrations"])
api_router.include_router(orchestration_router, tags=["orchestration"])
api_router.include_router(webhook_router, tags=["webhooks"])
api_router.include_router(analytics_router, tags=["analytics"])