from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from feed2epub.config import FeedConfig
from feed2epub.feeds import parse_entries

FIXTURE = Path(__file__).parent / "fixtures" / "sample_rss.xml"
NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _cfg(max_items: int = 25) -> FeedConfig:
    return FeedConfig(url="https://example.com/rss", name="Example", max_items=max_items, full_text=True)


def test_age_filter_and_dedupe() -> None:
    raw = FIXTURE.read_text(encoding="utf-8")
    meta, entries = parse_entries(raw, _cfg(), now=NOW, max_age_hours=36)

    # B is too old; the duplicate of A is deduped by guid. A and D remain.
    uids = [e.uid for e in entries]
    assert uids == ["guid-a", "guid-d"]
    assert meta.title == "Example Feed"
    assert meta.language == "en-us"


def test_newest_first_ordering() -> None:
    raw = FIXTURE.read_text(encoding="utf-8")
    _, entries = parse_entries(raw, _cfg(), now=NOW, max_age_hours=36)
    assert entries[0].uid == "guid-a"  # 10 Jul is newer than 9 Jul
    assert entries[0].published is not None
    assert entries[1].published is not None
    assert entries[0].published > entries[1].published


def test_max_items_cap() -> None:
    raw = FIXTURE.read_text(encoding="utf-8")
    _, entries = parse_entries(raw, _cfg(max_items=1), now=NOW, max_age_hours=36)
    assert len(entries) == 1
    assert entries[0].uid == "guid-a"


def test_wide_window_keeps_old_entry() -> None:
    raw = FIXTURE.read_text(encoding="utf-8")
    _, entries = parse_entries(raw, _cfg(), now=NOW, max_age_hours=24 * 30)
    assert "guid-b" in {e.uid for e in entries}
