"""Condense one transcript into action steps with Claude (one API call per video)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .download import FriendlyError, VideoInfo

PROMPT = (Path(__file__).parent / "prompts" / "condense.md").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "bottom_line": {"type": "string"},
        "onscreen_text": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["category", "slug", "title", "bottom_line", "onscreen_text", "body"],
    "additionalProperties": False,
}


@dataclass
class Condensed:
    category: str
    slug: str
    title: str
    bottom_line: str
    onscreen_text: str
    body: str
    input_tokens: int = 0
    output_tokens: int = 0


def make_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, max_retries=4)


def check_key(client: anthropic.Anthropic, model: str) -> None:
    """Cheap check that the key works and can use the model (looks the model up; no tokens spent)."""
    try:
        client.models.retrieve(model)
    except Exception as e:
        raise FriendlyError(explain_api_error(e)) from e


def explain_api_error(e: Exception) -> str:
    msg = str(e).lower()
    if isinstance(e, anthropic.AuthenticationError):
        return "Your Claude API key didn't work. Copy it again from console.anthropic.com -> API Keys."
    if "credit balance" in msg or "billing" in msg or isinstance(e, anthropic.EnforcedSpendLimitReachedError):
        return "Your Anthropic account is out of credits. Add some at console.anthropic.com -> Billing."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "Your API key isn't allowed to use this model. Check console.anthropic.com, or set CLAUDE_MODEL in .env."
    if isinstance(e, anthropic.NotFoundError):
        return "The Claude model named in .env (CLAUDE_MODEL) doesn't exist. Remove that line to use the default."
    if isinstance(e, anthropic.RateLimitError):
        return "Claude is rate-limiting this API key. Wait a minute and run it again."
    if isinstance(e, anthropic.APIConnectionError):
        return "Couldn't reach Claude. Check your internet connection."
    if isinstance(e, anthropic.APIStatusError) and e.status_code >= 500:
        return "Claude's servers had a hiccup. Run it again in a few minutes; finished videos are kept."
    return f"Claude request failed: {str(e)[:200]}"


def _user_content(info: VideoInfo, transcript: str, frames: list[Path], categories: list[str]) -> list[dict]:
    content: list[dict] = []
    for f in frames:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.standard_b64encode(f.read_bytes()).decode()},
        })
    stats = ", ".join(x for x in [
        f"{info.view_count:,} views" if info.view_count else "",
        f"{info.like_count:,} likes" if info.like_count else "",
    ] if x) or "unknown"
    text = (
        f"Existing categories: {', '.join(categories) if categories else '(none yet)'}\n\n"
        f"<video>\nLink: {info.url}\nCreator: {info.uploader}\nPosted: {info.upload_date}\nStats: {stats}\n"
        f"</video>\n\n<caption>\n{info.caption or '(no caption)'}\n</caption>\n\n"
        f"<transcript>\n{transcript or '(no speech detected)'}\n</transcript>"
    )
    if frames:
        text += f"\n\nThe {len(frames)} images above are evenly spaced frames from the video; read the on-screen text."
    content.append({"type": "text", "text": text})
    return content


def condense(client: anthropic.Anthropic, model: str, effort: str, info: VideoInfo, transcript: str,
             frames: list[Path], categories: list[str]) -> Condensed:
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            # if a safety filter declines (rare for this content), let the API retry on a fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": _user_content(info, transcript, frames, categories)}],
        )
    except FriendlyError:
        raise
    except Exception as e:
        raise FriendlyError(explain_api_error(e)) from e

    if response.stop_reason == "refusal":
        raise FriendlyError("Claude declined to summarize this video.")
    if response.stop_reason == "max_tokens":
        raise FriendlyError("Claude's answer was cut off. Try this video again.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise FriendlyError("Claude's answer came back garbled. Try this video again.") from e
    return Condensed(**{k: str(data.get(k, "")).strip() for k in SCHEMA["required"]},
                     input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
