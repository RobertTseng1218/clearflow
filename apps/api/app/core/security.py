from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)


def _sign(data: bytes, secret_key: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def create_access_token(user_id: UUID, secret_key: str, expires_in_seconds: int = 60 * 60 * 24 * 7) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + expires_in_seconds}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_part = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature_part = _sign(payload_part.encode("utf-8"), secret_key)
    return f"{payload_part}.{signature_part}"


def decode_access_token(token: str, secret_key: str) -> dict[str, object]:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    expected_signature = _sign(payload_part.encode("utf-8"), secret_key)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise ValueError("Invalid token signature")

    padded = payload_part + "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    exp = int(payload["exp"])
    if exp < int(time.time()):
        raise ValueError("Token expired")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing bearer token."},
        )

    settings = get_settings()
    try:
        payload = decode_access_token(credentials.credentials, settings.secret_key)
        user_id = UUID(str(payload["sub"]))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired token."},
        ) from exc

    user = db.get(User, str(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "User not found."},
        )
    return user
