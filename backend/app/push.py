import logging

import httpx

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push(token: str | None, title: str, body: str, data: dict | None = None) -> None:
    if not token:
        return
    try:
        resp = httpx.post(
            EXPO_PUSH_URL,
            json={
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                "priority": "high",
                "channelId": "reminders",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        log.exception("Expo push failed")
