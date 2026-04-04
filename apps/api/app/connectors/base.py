from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(slots=True)
class OAuthTokenPayload:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str]
    profile: dict[str, str]


@dataclass(slots=True)
class SourceRecord:
    external_id: str
    source_type: str
    title: str | None
    content_text: str | None
    source_timestamp: datetime | None
    participants: list[dict[str, str]]
    source_meta: dict[str, object]


class Connector(Protocol):
    provider_key: str

    def build_authorization_url(self, state: str) -> str: ...

    def exchange_code(self, code: str) -> OAuthTokenPayload: ...

    def fetch_source_records(self, access_token: str, sync_cursor: str | None = None) -> tuple[list[SourceRecord], str | None]: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
