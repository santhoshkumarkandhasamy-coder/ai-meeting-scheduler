"""Claude tool-use loop for one chat turn."""

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import anthropic

from app.agent.prompts import SYSTEM_PROMPT, user_profile_block
from app.agent.tools import TOOLS, ToolContext, run_tool_block
from app.config import get_settings

MAX_TOOL_ROUNDS = 8
FALLBACK_REPLY = "Sorry, I couldn't finish that. Please try again."


@lru_cache
def _client() -> anthropic.Anthropic:
    key = get_settings().anthropic_api_key
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def _context_line(now: datetime) -> str:
    return f"[Now: {now.strftime('%A %d %B %Y, %H:%M')} ({now.isoformat(timespec='minutes')}, {now.tzinfo})]"


def run_turn(
    history: list[dict],
    user_text: str,
    ctx: ToolContext,
    profile: dict,
    now: datetime | None = None,
) -> tuple[str, list[dict]]:
    """Run one user turn. Returns (reply_text, new_history). History is append-only."""
    settings = get_settings()
    tz: ZoneInfo = ctx.tz
    now = (now or datetime.now(tz)).astimezone(tz)

    messages = list(history)
    messages.append({"role": "user", "content": f"{_context_line(now)}\n{user_text}"})

    # System prompt and tool list are fixed per user, so the prefix stays cacheable;
    # the changing timestamp lives in the user message instead.
    system = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": user_profile_block(**profile)},
    ]

    response = None
    for _ in range(MAX_TOOL_ROUNDS):
        response = _client().beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=16000,
            system=system,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": settings.anthropic_effort},
            cache_control={"type": "ephemeral"},
            # Server-side refusal fallback: re-runs a declined request on a suitable model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Pass every block back unchanged (thinking, fallback, tool_use) on later requests.
        messages.append(
            {"role": "assistant", "content": [b.model_dump(mode="json", exclude_none=True) for b in response.content]}
        )

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    content, is_error = run_tool_block(block.name, block.input or {}, ctx)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
                    )
            messages.append({"role": "user", "content": results})
            continue
        if response.stop_reason == "pause_turn":
            continue
        break

    if response is None or response.stop_reason == "refusal":
        return FALLBACK_REPLY, messages

    text = " ".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "tool_use":
        # Ran out of tool rounds; close the dangling tool_result turn so the history stays valid.
        messages.append({"role": "assistant", "content": [{"type": "text", "text": FALLBACK_REPLY}]})
        return FALLBACK_REPLY, messages
    return text or FALLBACK_REPLY, messages
