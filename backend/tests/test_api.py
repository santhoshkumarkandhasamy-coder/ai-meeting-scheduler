from fastapi.testclient import TestClient

from app import main
from app.db import init_db

init_db()
client = TestClient(main.app)


def sign_in(monkeypatch, refresh_token="rt-1"):
    tokens = {"id_token": "x"} | ({"refresh_token": refresh_token} if refresh_token else {})
    monkeypatch.setattr(
        main, "exchange_server_auth_code",
        lambda code: {"tokens": tokens, "claims": {"sub": "google-123", "email": "s@example.com", "name": "Santhosh"}},
    )
    return client.post("/auth/google", json={"server_auth_code": "code", "timezone": "Asia/Kolkata"})


def test_sign_in_and_settings(monkeypatch):
    r = sign_in(monkeypatch)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/me", headers=headers).json()["email"] == "s@example.com"

    r = client.put("/me/settings", headers=headers, json={"reminder_minutes": [5, 15, 15], "language": "ta-IN"})
    assert r.json()["reminder_minutes"] == [15, 5] and r.json()["language"] == "ta-IN"

    r = client.put("/me/settings", headers=headers, json={"disable_morning_briefing": True})
    assert r.json()["morning_briefing_time"] is None

    assert client.put("/me/settings", headers=headers, json={"timezone": "Mars/Base"}).status_code == 422

    # Second sign-in without a refresh token keeps the stored one.
    assert sign_in(monkeypatch, refresh_token=None).status_code == 200


def test_requires_auth():
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer junk"}).status_code == 401
