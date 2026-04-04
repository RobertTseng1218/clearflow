from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import getaddresses
from urllib.parse import urlencode

import httpx

from app.connectors.base import OAuthTokenPayload, SourceRecord, utcnow
from app.core.config import get_settings


class GoogleBaseConnector:
    provider_key = "google"
    scopes: list[str] = []
    authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    timeout_seconds = 20.0

    def __init__(self) -> None:
        self.settings = get_settings()

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.settings.google_oauth_client_id,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{self.authorization_base_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthTokenPayload:
        if self.settings.dev_oauth_bypass and code.startswith("dev_"):
            name = code.removeprefix("dev_").replace("_", " ").strip().title() or "Dev User"
            email_local = code.removeprefix("dev_").replace("_", ".") or "dev.user"
            return OAuthTokenPayload(
                access_token=f"fake-access-{self.provider_key}-{email_local}",
                refresh_token=f"fake-refresh-{self.provider_key}-{email_local}",
                expires_at=utcnow() + timedelta(hours=1),
                scopes=self.scopes,
                profile={
                    "email": f"{email_local}@example.com",
                    "name": name,
                    "avatar_url": "https://example.com/avatar.png",
                    "provider_user_id": f"google-{email_local}",
                },
            )

        if not self._oauth_configured():
            raise NotImplementedError(
                "Google OAuth 設定尚未完成，請先設定 GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REDIRECT_URI。"
            )

        token_payload = self._exchange_code_real(code)
        profile = self._fetch_google_profile(str(token_payload["access_token"]))

        expires_at = None
        expires_in = token_payload.get("expires_in")
        if isinstance(expires_in, int | float):
            expires_at = utcnow() + timedelta(seconds=float(expires_in))

        return OAuthTokenPayload(
            access_token=str(token_payload["access_token"]).strip(),
            refresh_token=(str(token_payload["refresh_token"]).strip() if token_payload.get("refresh_token") else None),
            expires_at=expires_at,
            scopes=str(token_payload.get("scope", "")).split() or self.scopes,
            profile={
                "email": profile.get("email", ""),
                "name": profile.get("name", "Google User"),
                "avatar_url": profile.get("picture", ""),
                "provider_user_id": profile.get("sub", profile.get("email", "")),
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict[str, object]:
        if not self._oauth_configured():
            raise NotImplementedError(
                "Google OAuth 設定尚未完成，請先設定 GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REDIRECT_URI。"
            )

        payload = {
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.token_url, data=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(f"Google refresh token 交換失敗：{detail}") from exc

        data = response.json()
        if "access_token" not in data:
            raise RuntimeError("Google refresh token 交換未回傳 access_token。")
        return data

    def fetch_source_records(self, access_token: str, sync_cursor: str | None = None) -> tuple[list[SourceRecord], str | None]:
        if self.settings.dev_oauth_bypass and access_token.startswith("fake-access-"):
            return self._fake_records(), "dev-cursor-1"
        return self._fetch_real_source_records(access_token, sync_cursor)

    def _fetch_real_source_records(self, access_token: str, sync_cursor: str | None = None) -> tuple[list[SourceRecord], str | None]:
        raise NotImplementedError(
            f"Real fetch_source_records is not implemented for {self.provider_key} yet."
        )

    def _fake_records(self) -> list[SourceRecord]:
        raise NotImplementedError

    def _oauth_configured(self) -> bool:
        return all(
            [
                self.settings.google_oauth_client_id,
                self.settings.google_oauth_client_secret,
                self.settings.google_oauth_redirect_uri,
            ]
        ) and self.settings.google_oauth_client_id != "replace_me" and self.settings.google_oauth_client_secret != "replace_me"

    def _exchange_code_real(self, code: str) -> dict[str, object]:
        payload = {
            "code": code,
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.token_url, data=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(f"Google token exchange 失敗：{detail}") from exc
        data = response.json()
        if "access_token" not in data:
            raise RuntimeError("Google token exchange 未回傳 access_token。")
        return data

    def _fetch_google_profile(self, access_token: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {access_token.strip()}"}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(self.userinfo_url, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(f"取得 Google 使用者資料失敗：{detail}") from exc
        data = response.json()
        return {
            "email": data.get("email", ""),
            "name": data.get("name", "Google User"),
            "picture": data.get("picture", ""),
            "sub": data.get("sub", ""),
        }

    @staticmethod
    def _parse_participants(*values: str | None) -> list[dict[str, str]]:
        combined = ", ".join([value for value in values if value])
        participants: list[dict[str, str]] = []
        for name, email in getaddresses([combined]):
            if email:
                participants.append({"email": email, "name": name or email})
        return participants

    @staticmethod
    def _to_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _millis_to_datetime(value: str | int | None) -> datetime | None:
        if value is None:
            return None
        try:
            millis = int(value)
            return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            return None