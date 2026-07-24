"""Shared helpers for sportocal fetch/build scripts.

Generic event schema (sport-agnostic, see README):
    id, sport, competition, round, title, start, timeConfirmed,
    location, participants, lastUpdated  (+ optional sport-specific extras)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "sportocal/1.0 (https://github.com/; contact via repo issues)"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = ROOT_DIR / "docs"
CONFIG_PATH = ROOT_DIR / "config.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def http_get_json(url: str, retries: int = 3, timeout: int = 20) -> Any:
    """GET a URL and parse it as JSON, with basic retry on transient failures."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"WARNUNG: {message}", file=sys.stderr, flush=True)


def load_snapshot(source_id: str) -> dict:
    path = DATA_DIR / f"{source_id}.json"
    if not path.exists():
        return {"events": [], "lastChecked": None}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(source_id: str, events: list[dict], now_iso: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{source_id}.json"
    payload = {"events": events, "lastChecked": now_iso}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


def diff_and_log(source_id: str, old_events: list[dict], new_events: list[dict]) -> bool:
    """Compare old vs new event lists by id, log human-readable changes.

    Returns True if anything changed (added/removed/modified).
    """
    old_by_id = {e["id"]: e for e in old_events}
    new_by_id = {e["id"]: e for e in new_events}

    changed = False

    for event_id, new_event in new_by_id.items():
        old_event = old_by_id.get(event_id)
        if old_event is None:
            changed = True
            log(f"[{source_id}] NEU: {new_event.get('title')} ({new_event.get('start')})")
            continue
        for field in ("start", "timeConfirmed", "title", "round", "location"):
            old_value = old_event.get(field)
            new_value = new_event.get(field)
            if old_value != new_value:
                changed = True
                log(
                    f"[{source_id}] {new_event.get('round') or new_event.get('title')}: "
                    f"{field} von {old_value!r} auf {new_value!r} geändert"
                )

    for event_id, old_event in old_by_id.items():
        if event_id not in new_by_id:
            changed = True
            log(f"[{source_id}] ENTFERNT: {old_event.get('title')} ({old_event.get('start')})")

    return changed


def normalize_text(text: str) -> str:
    """Lowercase, strip umlauts/punctuation for loose fuzzy matching."""
    import re

    text = text.lower()
    for umlaut, plain in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_keyword(haystack: str, keyword: str) -> bool:
    """Substring match, except purely numeric keywords which need a digit
    boundary so e.g. keyword '2' doesn't accidentally match inside '2025'."""
    import re

    if keyword.isdigit():
        return re.search(rf"(?<!\d){re.escape(keyword)}(?!\d)", haystack) is not None
    return keyword in haystack


def clean_wikitext(text: str) -> str:
    """Best-effort conversion of a small wikitext fragment to plain text."""
    import re

    if text is None:
        return ""
    # Drop file/image embeds entirely (icons etc. have no useful text value).
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    # Strip simple (non-nested) templates a few passes to handle mild nesting.
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # [[target|display]] -> display, [[target]] -> target
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
