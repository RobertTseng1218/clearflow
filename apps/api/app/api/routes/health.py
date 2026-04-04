from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.responses import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return success_response({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})
