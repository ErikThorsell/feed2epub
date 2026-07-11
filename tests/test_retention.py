from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from feed2epub.retention import prune


def _touch(dir_path: Path, name: str) -> Path:
    path = dir_path / name
    path.write_bytes(b"epub")
    return path


def test_prune_deletes_only_files_older_than_retention(tmp_path: Path) -> None:
    today = date(2026, 7, 11)
    # retention_days=14 -> cutoff 2026-06-27; strictly older is deleted, the boundary date is kept.
    old = _touch(tmp_path, "hacker-news-2026-06-20.epub")
    boundary = _touch(tmp_path, "hacker-news-2026-06-27.epub")
    fresh = _touch(tmp_path, "lwn-2026-07-10.epub")

    result = prune(tmp_path, 14, today=today)

    assert result.deleted == ["hacker-news-2026-06-20.epub"]
    assert set(result.kept) == {"hacker-news-2026-06-27.epub", "lwn-2026-07-10.epub"}
    assert result.errors == []
    assert not old.exists()
    assert boundary.exists()
    assert fresh.exists()


def test_prune_ignores_files_that_are_not_ours(tmp_path: Path) -> None:
    today = date(2026, 7, 11)
    # None of these match <slug>-YYYY-MM-DD.epub and must survive even though they are ancient / epub-ish.
    keepers = [
        _touch(tmp_path, "The Great Gatsby.epub"),  # real library book
        _touch(tmp_path, "2020-01-01.epub"),  # bare date, no slug
        _touch(tmp_path, "hacker-news-2020-13-01.epub"),  # shape matches but month is impossible
        _touch(tmp_path, "hacker-news-2020-01-01.epub.tmp"),  # crashed write fragment
        _touch(tmp_path, "notes-2020-01-01.txt"),  # wrong extension
    ]

    result = prune(tmp_path, 14, today=today)

    assert result.deleted == []
    assert all(path.exists() for path in keepers)


def test_prune_reports_delete_errors_without_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 7, 11)
    victim = _touch(tmp_path, "hacker-news-2026-01-01.epub")
    survivor = _touch(tmp_path, "lwn-2026-01-01.epub")

    real_unlink = Path.unlink

    def fake_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == victim.name:
            raise OSError("permission denied")
        real_unlink(self)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    result = prune(tmp_path, 14, today=today)

    assert survivor.name in result.deleted
    assert not survivor.exists()
    assert result.deleted == [survivor.name]
    assert len(result.errors) == 1
    assert result.errors[0][0] == victim.name
    assert victim.exists()  # the failed delete left it in place
