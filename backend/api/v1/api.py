from fastapi import APIRouter

from .endpoints import auth
from backend.modules.inflow_wrapper.api import router as inflow_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(inflow_router, prefix="/integrations", tags=["integrations"])