from __future__ import annotations

import httpx

from app.connectors.base import SourceRecord, utcnow
from app.connectors.google_base import GoogleBaseConnector


class GmailConnector(GoogleBaseConnector):
    provider_key = "gmail"
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
    gmail_api_base = "https://gmail.googleapis.com/gmail/v1/users/me"

    def _fake_records(self) -> list[SourceRecord]:
        now = utcnow()
        return [
            SourceRecord(
                external_id="gmail-dev-001",
                source_type="email",
                title="Re: ClearFlow 合作確認",
                content_text="請今天內確認時程並回覆合作細節。",
                source_timestamp=now,
                participants=[{"email": "client@example.com", "name": "Client A"}],
                source_meta={"label_ids": ["INBOX"]},
            )
        ]

    def _fetch_real_source_records(self, access_token: str, sync_cursor: str | None = None) -> tuple[list[SourceRecord], str | None]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "maxResults": 10,
            "labelIds": "INBOX",
            "q": "newer_than:30d",
        }
        if sync_cursor:
            params["pageToken"] = sync_cursor

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(f"{self.gmail_api_base}/messages", headers=headers, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"讀取 Gmail 郵件列表失敗：{exc.response.text}") from exc

        payload = response.json()
        messages = payload.get("messages", [])
        next_cursor = payload.get("nextPageToken")
        records: list[SourceRecord] = []

        with httpx.Client(timeout=self.timeout_seconds) as client:
            for message in messages:
                message_id = message.get("id")
                if not message_id:
                    continue
                detail_resp = client.get(
                    f"{self.gmail_api_base}/messages/{message_id}",
                    headers=headers,
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
                )
                try:
                    detail_resp.raise_for_status()
                except httpx.HTTPStatusError:
                    continue
                detail = detail_resp.json()
                headers_map = {
                    item.get("name", "").lower(): item.get("value", "")
                    for item in detail.get("payload", {}).get("headers", [])
                }
                subject = headers_map.get("subject") or "(無主旨)"
                sender = headers_map.get("from")
                to = headers_map.get("to")
                participants = self._parse_participants(sender, to)
                records.append(
                    SourceRecord(
                        external_id=message_id,
                        source_type="email",
                        title=subject,
                        content_text=detail.get("snippet"),
                        source_timestamp=self._millis_to_datetime(detail.get("internalDate")),
                        participants=participants,
                        source_meta={
                            "thread_id": detail.get("threadId"),
                            "label_ids": detail.get("labelIds", []),
                            "from": sender,
                            "to": to,
                        },
                    )
                )

        return records, next_cursor
