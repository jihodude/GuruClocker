"""Turn whatever the user pasted into a clean list of video links."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

_URL = re.compile(r"https?://[^\s,<>\"']+", re.IGNORECASE)
_INSTAGRAM = re.compile(r"instagram\.com/(?:[^/]+/)?(reel|reels|p|tv)/([A-Za-z0-9_-]+)", re.IGNORECASE)


def instagram_id(url: str) -> str | None:
    m = _INSTAGRAM.search(url)
    return m.group(2) if m else None


def clean(url: str) -> str:
    """Drop tracking junk. Instagram links become https://www.instagram.com/reel/<ID>/."""
    url = url.rstrip(".,;)")
    ig = instagram_id(url)
    if ig:
        return f"https://www.instagram.com/reel/{ig}/"
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def parse_links(text: str) -> tuple[list[str], list[str]]:
    """Returns (links, junk). Links may be separated by commas, spaces or new lines; anything that
    isn't a link (notes, stray words) comes back as junk so the user can be told it was ignored."""
    links: list[str] = []
    for raw in _URL.findall(text):
        url = clean(raw)
        if url not in links:
            links.append(url)
    leftover = _URL.sub(" ", text)
    junk = [w for w in re.split(r"[,\s]+", leftover) if w.strip()]
    return links, junk
