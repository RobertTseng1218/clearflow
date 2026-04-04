from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    meta: dict[str, Any] = Field(default_factory=dict)
