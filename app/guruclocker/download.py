"""Download a video and its details (creator, caption, ...) with yt-dlp."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


class FriendlyError(Exception):
    """An error whose message is already written for a non-technical person."""


@dataclass
class VideoInfo:
    url: str
    video_id: str
    title: str
    uploader: str
    upload_date: str
    view_count: int | None
    like_count: int | None
    caption: str


class _Silent:
    """yt-dlp prints raw errors even in quiet mode; we report our own plain-English version instead."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def _opts(cookies_browser: str) -> dict:
    opts = {"quiet": True, "noprogress": True, "no_warnings": True, "ffmpeg_location": FFMPEG, "logger": _Silent()}
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


def explain(err: Exception) -> str:
    """Translate yt-dlp's error text into plain English."""
    msg = str(err).lower()
    if "private" in msg or "not available" in msg or "removed" in msg or "404" in msg:
        return "This video is private, deleted, or not available."
    if "login" in msg or "rate" in msg or "429" in msg or "cookies" in msg:
        return ("The site blocked the download (it wants you logged in, or we asked too often). "
                "Try again later, or see 'Instagram keeps blocking me' in the README.")
    if "unsupported url" in msg:
        return "That link isn't a video page this program understands."
    if "timed out" in msg or "connection" in msg or "network" in msg:
        return "Couldn't reach the site. Check your internet connection."
    return f"Download failed: {str(err).splitlines()[0][:200]}"


def probe(url: str, cookies_browser: str = "") -> VideoInfo:
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({**_opts(cookies_browser), "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # yt-dlp raises many types; all get explained the same way
        raise FriendlyError(explain(e)) from e
    if info.get("_type") == "playlist":
        raise FriendlyError("That link is a playlist or profile, not a single video.")
    return VideoInfo(
        url=info.get("webpage_url") or url,
        video_id=str(info.get("id") or "video"),
        title=(info.get("title") or "").strip(),
        uploader=(info.get("uploader") or info.get("channel") or info.get("uploader_id") or "unknown").strip(),
        upload_date=_date(info.get("upload_date")),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        caption=(info.get("description") or "").strip(),
    )


def fetch(url: str, dest_dir: Path, cookies_browser: str = "") -> Path:
    """Download the video into dest_dir and return its path."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        **_opts(cookies_browser),
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "video.%(ext)s"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise FriendlyError(explain(e)) from e
    videos = sorted(p for p in dest_dir.glob("video.*") if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov", ".m4v"})
    if not videos:
        raise FriendlyError("The download finished but no video file came out.")
    return videos[0]


def _date(raw: str | None) -> str:
    if raw and re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw or "unknown"
