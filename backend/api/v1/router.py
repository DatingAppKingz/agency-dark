from fastapi import APIRouter
from api.v1.endpoints import auth, users, agencies, analytics, sessions, sync_status

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(agencies.router, prefix="/agencies", tags=["agencies"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(sync_status.router, prefix="/sync", tags=["sync"])