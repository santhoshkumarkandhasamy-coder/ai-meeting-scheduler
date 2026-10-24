from datetime import datetime
from types import SimpleNamespace

from anthropic.types.beta import BetaTextBlock, BetaToolUseBlock

from app.agent import runner
from tests.test_tools import IST, ctx

PROFILE = {"name": "Santhosh", "email": "s@example.com", "timezone": "Asia/Kolkata", "language": "auto", "work_hours": "09:00-18:00"}


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def fake_client(monkeypatch, responses):
    messages = FakeMessages(responses)
    monkeypatch.setattr(runner, "_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages)))
    return messages


def resp(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def test_tool_loop_and_history(monkeypatch):
    messages = fake_client(
        monkeypatch,
        [
            resp(
                "tool_use",
                BetaToolUseBlock(
                    type="tool_use", id="t1", name="list_events",
                    input={"start": "2026-10-28T00:00:00+05:30", "end": "2026-10-29T00:00:00+05:30"},
                ),
            ),
            resp("end_turn", BetaTextBlock(type="text", text="Tomorrow you have one meeting at 10 AM.")),
        ],
    )
    now = datetime(2026, 10, 27, 9, 0, tzinfo=IST)
    reply, history = runner.run_turn([], "What meetings tomorrow?", ctx(), PROFILE, now=now)

    assert reply == "Tomorrow you have one meeting at 10 AM."
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert history[0]["content"].startswith("[Now: Tuesday 27 October 2026, 09:00")
    assert history[2]["content"][0]["tool_use_id"] == "t1"
    assert history[2]["content"][0]["is_error"] is False
    # Static system prompt: the timestamp must not leak into it (keeps the cache prefix stable).
    assert "2026" not in messages.calls[0]["system"][0]["text"]
    assert messages.calls[0]["fallbacks"] == "default"


def test_refusal_returns_fallback(monkeypatch):
    fake_client(monkeypatch, [resp("refusal")])
    reply, _ = runner.run_turn([], "hi", ctx(), PROFILE)
    assert reply == runner.FALLBACK_REPLY


def test_tool_round_limit_keeps_history_valid(monkeypatch):
    tool = BetaToolUseBlock(type="tool_use", id="t", name="nope", input={})
    fake_client(monkeypatch, [resp("tool_use", tool)] * runner.MAX_TOOL_ROUNDS)
    reply, history = runner.run_turn([], "loop", ctx(), PROFILE)
    assert reply == runner.FALLBACK_REPLY
    assert history[-1]["role"] == "assistant" and history[-2]["role"] == "user"
