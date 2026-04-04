from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.activity_logs import router as activity_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.summaries import router as summaries_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.me import router as me_router
from app.api.routes.settings import router as settings_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix=settings.api_v1_prefix)
api_router.include_router(activity_logs_router, prefix=settings.api_v1_prefix)
api_router.include_router(me_router, prefix=settings.api_v1_prefix)
api_router.include_router(integrations_router, prefix=settings.api_v1_prefix)
api_router.include_router(dashboard_router, prefix=settings.api_v1_prefix)
api_router.include_router(summaries_router, prefix=settings.api_v1_prefix)
api_router.include_router(tasks_router, prefix=settings.api_v1_prefix)

api_router.include_router(settings_router, prefix=settings.api_v1_prefix)
