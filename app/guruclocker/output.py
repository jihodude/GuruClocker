"""The output folder: output/<category>/<slug>__<id>/{link.md, transcript.txt, condensed.md}."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from .condense import Condensed
from .download import VideoInfo

SPECIAL = {"_archive", "refined"}   # created by the Claude Code pruning session
TEMPLATE = Path(__file__).parent / "templates" / "CLAUDE.md"


def kebab(text: str, max_words: int = 8, fallback: str = "item") -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:max_words])[:60].strip("-") or fallback


def folder_id(video_id: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", video_id.lower()) or "video"


def categories(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and p.name not in SPECIAL and not p.name.startswith((".", "_")))


def processed_ids(root: Path) -> set[str]:
    """IDs of every video already in the output folder, including ones the user archived or kept."""
    if not root.exists():
        return set()
    return {p.name.rsplit("__", 1)[1] for p in root.rglob("*__*") if p.is_dir()}


def write_reel(root: Path, info: VideoInfo, transcript: str, looped: bool, c: Condensed) -> Path:
    from .transcribe import LOOP_NOTE

    category = kebab(c.category, 4, "other")
    folder = root / category / f"{kebab(c.slug, 6)}__{folder_id(info.video_id)}"
    folder.mkdir(parents=True, exist_ok=True)

    stats = " · ".join(x for x in [
        f"{info.view_count:,} views" if info.view_count else "",
        f"{info.like_count:,} likes" if info.like_count else "",
    ] if x)
    (folder / "link.md").write_text(
        f"# {c.title}\n\n"
        f"- **Link:** {info.url}\n"
        f"- **Creator:** {info.uploader}\n"
        f"- **Posted:** {info.upload_date}\n"
        + (f"- **Stats:** {stats}\n" if stats else "")
        + f"\n## Caption\n\n{info.caption or '_none_'}\n",
        encoding="utf-8",
    )

    parts = []
    if looped:
        parts.append(LOOP_NOTE)
    parts.append(transcript or "(no speech detected)")
    if c.onscreen_text:
        parts.append("--- On-screen text (read from video frames) ---\n" + c.onscreen_text)
    (folder / "transcript.txt").write_text("\n\n".join(parts) + "\n", encoding="utf-8")

    (folder / "condensed.md").write_text(
        f"# {c.title}\n\n**Bottom line:** {c.bottom_line}\n\n{c.body.strip()}\n", encoding="utf-8"
    )
    return folder


def _first(path: Path, pattern: str) -> str:
    if not path.exists():
        return ""
    m = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else ""


def write_index(root: Path) -> None:
    lines = ["# Index", "", f"_Rebuilt {date.today().isoformat()}. One line per video; open each folder's "
             "`condensed.md` for the action steps._", ""]
    total = 0
    for cat in categories(root):
        reels = sorted(p for p in (root / cat).iterdir() if p.is_dir() and "__" in p.name)
        if not reels:
            continue
        lines += [f"## {cat}", ""]
        for r in reels:
            title = _first(r / "condensed.md", r"^# (.+)$") or r.name
            bottom = _first(r / "condensed.md", r"^\*\*Bottom line:\*\*\s*(.+)$")
            link = _first(r / "link.md", r"^- \*\*Link:\*\* (\S+)")
            lines.append(f"- **[{title}]({cat}/{r.name}/condensed.md)**: {bottom}" + (f" ([video]({link}))" if link else ""))
            total += 1
        lines.append("")
    if total == 0:
        lines.append("_No videos yet._")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_failures(root: Path, failures: list[tuple[str, str]]) -> None:
    path = root / "failures.md"
    if not failures:
        return
    header = "" if path.exists() else "# Links that failed\n\nRun guruclocker again with these links to retry.\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(header + f"\n## {date.today().isoformat()}\n\n" + "".join(f"- {u}: {why}\n" for u, why in failures))


def ensure_claude_md(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if not (root / "CLAUDE.md").exists():
        shutil.copy(TEMPLATE, root / "CLAUDE.md")
