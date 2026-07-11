"""Parse a feed with ``feedparser``, filter entries by age, dedupe, and cap to ``max_items``.

This module does no network I/O: it takes raw feed bytes/text so it stays trivially testable against fixtures.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser

from .config import FeedConfig


@dataclass(frozen=True)
class Entry:
    """A single feed entry, normalised. ``uid`` is the dedupe key (id -> url -> title)."""

    uid: str
    title: str
    url: str | None
    author: str | None
    published: datetime | None
    summary: str | None


@dataclass(frozen=True)
class FeedMeta:
    """Feed-level metadata used to build the EPUB."""

    title: str
    language: str


def _to_datetime(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    # feedparser returns *_parsed as a UTC struct_time; interpret it as UTC.
    return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)


def _entry_uid(entry: dict[str, Any]) -> str:
    for key in ("id", "link", "title"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _entry_summary(entry: dict[str, Any]) -> str | None:
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value")
        if isinstance(value, str) and value.strip():
            return value
    summary = entry.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    return None


def _min_aware() -> datetime:
    return datetime.min.replace(tzinfo=UTC)


def parse_entries(
    raw: str | bytes,
    feed_cfg: FeedConfig,
    *,
    now: datetime,
    max_age_hours: int,
) -> tuple[FeedMeta, list[Entry]]:
    """Return feed metadata and the filtered, deduped, newest-first, capped list of entries.

    Entries with no parseable date are kept (some feeds omit dates); dated entries older than ``max_age_hours``
    are dropped. Duplicates within the feed are collapsed by ``uid``.
    """
    parsed = feedparser.parse(raw)
    feed = parsed.get("feed", {})
    meta = FeedMeta(
        title=(feed.get("title") or feed_cfg.name).strip(),
        language=(feed.get("language") or "en").strip() or "en",
    )

    max_age_seconds = max_age_hours * 3600
    seen: set[str] = set()
    entries: list[Entry] = []
    for raw_entry in parsed.get("entries", []):
        uid = _entry_uid(raw_entry)
        if not uid or uid in seen:
            continue
        published = _to_datetime(raw_entry.get("published_parsed") or raw_entry.get("updated_parsed"))
        if published is not None and (now - published).total_seconds() > max_age_seconds:
            continue
        seen.add(uid)
        title = raw_entry.get("title")
        author = raw_entry.get("author")
        entries.append(
            Entry(
                uid=uid,
                title=(title.strip() if isinstance(title, str) and title.strip() else "Untitled"),
                url=raw_entry.get("link"),
                author=author.strip() if isinstance(author, str) and author.strip() else None,
                published=published,
                summary=_entry_summary(raw_entry),
            )
        )

    entries.sort(key=lambda e: e.published or _min_aware(), reverse=True)
    return meta, entries[: feed_cfg.max_items]
