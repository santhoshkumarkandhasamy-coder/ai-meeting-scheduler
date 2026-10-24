"""Thin wrapper over the Google Calendar API v3 for one user."""

import uuid
from datetime import datetime

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def exchange_server_auth_code(code: str) -> dict:
    """Exchange the mobile app's serverAuthCode for tokens and the verified identity."""
    settings = get_settings()
    resp = httpx.post(
        TOKEN_URI,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "authorization_code",
            # Codes issued to native Google Sign-In use an empty redirect URI.
            "redirect_uri": "",
        },
        timeout=15,
    )
    resp.raise_for_status()
    tokens = resp.json()
    claims = id_token.verify_oauth2_token(tokens["id_token"], Request(), settings.google_client_id)
    return {"tokens": tokens, "claims": claims}


def simplify_event(event: dict) -> dict:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event["id"],
        "title": event.get("summary", "(no title)"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start,
        "location": event.get("location"),
        "meet_link": event.get("hangoutLink"),
        "organizer": event.get("organizer", {}).get("email"),
        "is_owner": event.get("organizer", {}).get("self", False),
        "attendees": [
            {"email": a.get("email"), "response": a.get("responseStatus")}
            for a in event.get("attendees", [])
            if not a.get("self")
        ],
        "my_response": next(
            (a.get("responseStatus") for a in event.get("attendees", []) if a.get("self")),
            "accepted",
        ),
    }


class CalendarClient:
    def __init__(self, refresh_token: str, timezone: str):
        settings = get_settings()
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        self.timezone = timezone
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_events(self, start: datetime, end: datetime, max_results: int = 50) -> list[dict]:
        result = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
                timeZone=self.timezone,
            )
            .execute()
        )
        return [simplify_event(e) for e in result.get("items", []) if e.get("status") != "cancelled"]

    def busy_intervals(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        result = (
            self._service.freebusy()
            .query(
                body={
                    "timeMin": start.isoformat(),
                    "timeMax": end.isoformat(),
                    "timeZone": self.timezone,
                    "items": [{"id": "primary"}],
                }
            )
            .execute()
        )
        busy = result["calendars"]["primary"].get("busy", [])
        return [(datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])) for b in busy]

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        description: str | None = None,
        add_meet_link: bool = True,
    ) -> dict:
        body: dict = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": self.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self.timezone},
            "attendees": [{"email": a} for a in attendees or []],
        }
        if description:
            body["description"] = description
        if add_meet_link:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        event = (
            self._service.events()
            .insert(calendarId="primary", body=body, conferenceDataVersion=1, sendUpdates="all")
            .execute()
        )
        return simplify_event(event)

    def update_event(self, event_id: str, changes: dict) -> dict:
        body: dict = {}
        if "title" in changes:
            body["summary"] = changes["title"]
        if "start" in changes:
            body["start"] = {"dateTime": changes["start"].isoformat(), "timeZone": self.timezone}
        if "end" in changes:
            body["end"] = {"dateTime": changes["end"].isoformat(), "timeZone": self.timezone}
        if "attendees" in changes:
            body["attendees"] = [{"email": a} for a in changes["attendees"]]
        event = (
            self._service.events()
            .patch(calendarId="primary", eventId=event_id, body=body, sendUpdates="all")
            .execute()
        )
        return simplify_event(event)

    def cancel_event(self, event_id: str) -> None:
        self._service.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
