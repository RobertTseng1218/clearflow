from __future__ import annotations

from datetime import timedelta

import httpx

from app.connectors.base import SourceRecord, utcnow
from app.connectors.google_base import GoogleBaseConnector


class GoogleCalendarConnector(GoogleBaseConnector):
    provider_key = "gcal"
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]
    calendar_api_base = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    def _fake_records(self) -> list[SourceRecord]:
        now = utcnow()
        return [
            SourceRecord(
                external_id="gcal-dev-001",
                source_type="calendar_event",
                title="ClearFlow Sprint 規劃會議",
                content_text="檢查 Sprint 0 與 Sprint 1 任務拆解。",
                source_timestamp=now,
                participants=[{"email": "team@example.com", "name": "Core Team"}],
                source_meta={"location": "Google Meet"},
            )
        ]

    def _fetch_real_source_records(self, access_token: str, sync_cursor: str | None = None) -> tuple[list[SourceRecord], str | None]:
        headers = {"Authorization": f"Bearer {access_token}"}
        now = utcnow()
        params = {
            "maxResults": 20,
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": (now - timedelta(days=7)).isoformat(),
            "timeMax": (now + timedelta(days=30)).isoformat(),
        }
        if sync_cursor:
            params["pageToken"] = sync_cursor

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(self.calendar_api_base, headers=headers, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"讀取 Google Calendar 事件失敗：{exc.response.text}") from exc

        payload = response.json()
        items = payload.get("items", [])
        next_cursor = payload.get("nextPageToken")
        records: list[SourceRecord] = []

        for event in items:
            event_id = event.get("id")
            if not event_id:
                continue
            start = event.get("start", {})
            source_time = (
                self._to_datetime(start.get("dateTime"))
                or self._to_datetime(start.get("date"))
                or now
            )
            attendees = event.get("attendees", [])
            participants = [
                {"email": attendee.get("email", ""), "name": attendee.get("displayName") or attendee.get("email", "")}
                for attendee in attendees
                if attendee.get("email")
            ]
            records.append(
                SourceRecord(
                    external_id=event_id,
                    source_type="calendar_event",
                    title=event.get("summary") or "(未命名行程)",
                    content_text=event.get("description"),
                    source_timestamp=source_time,
                    participants=participants,
                    source_meta={
                        "location": event.get("location"),
                        "status": event.get("status"),
                        "html_link": event.get("htmlLink"),
                    },
                )
            )

        return records, next_cursor
