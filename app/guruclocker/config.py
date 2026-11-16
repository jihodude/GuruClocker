"""Settings, read from the .env file next to the program (or real environment variables)."""

from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent        # the app/ folder
TOP = ROOT.parent                                    # the folder with windows.bat / mac.command
ENV_FILE = ROOT / ".env"
IN_DOCKER = os.environ.get("GURUCLOCKER_IN_DOCKER") == "1"

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
MLX_MODEL = "mlx-community/Qwen3-ASR-1.7B-8bit"


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    api_key: str
    claude_model: str
    claude_effort: str
    asr_backend: str          # auto | mlx | whisper
    whisper_model: str        # "" = pick by hardware
    whisper_device: str       # auto | cuda | cpu
    keep_videos: bool
    cookies_browser: str
    output_dir: Path


def load_settings() -> Settings:
    load_dotenv(ENV_FILE, override=False)
    out = os.environ.get("OUTPUT_DIR", "").strip()
    return Settings(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        claude_model=os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_CLAUDE_MODEL,
        claude_effort=os.environ.get("CLAUDE_EFFORT", "").strip() or "high",
        asr_backend=os.environ.get("ASR_BACKEND", "").strip().lower() or "auto",
        whisper_model=os.environ.get("WHISPER_MODEL", "").strip(),
        whisper_device=os.environ.get("WHISPER_DEVICE", "").strip().lower() or "auto",
        keep_videos=_bool(os.environ.get("KEEP_VIDEOS")),
        cookies_browser=os.environ.get("COOKIES_BROWSER", "").strip(),
        output_dir=Path(out).expanduser().resolve() if out else TOP / "output",
    )


def save_api_key(key: str) -> None:
    """Write the key into .env (creating it from .env.example if needed) and into this process."""
    # Edited in place (not write-temp-then-rename): inside Docker, .env is a single mounted file and
    # can't be replaced by a rename.
    example = ROOT / ".env.example"
    text = ENV_FILE.read_text() if ENV_FILE.exists() else (example.read_text() if example.exists() else "")
    line = f"ANTHROPIC_API_KEY={key}"
    if re.search(r"^ANTHROPIC_API_KEY=.*$", text, re.MULTILINE):
        text = re.sub(r"^ANTHROPIC_API_KEY=.*$", lambda _: line, text, count=1, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
    with open(ENV_FILE, "w") as f:
        f.write(text)
    os.environ["ANTHROPIC_API_KEY"] = key
