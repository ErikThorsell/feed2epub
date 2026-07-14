from __future__ import annotations

from pathlib import Path

import pytest

from feed2epub.config import DEFAULT_MAX_ITEMS, ConfigError, load_config


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "feeds.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_config_with_defaults(tmp_path: Path) -> None:
    cfg = load_config(
        _write(
            tmp_path,
            """
            output_dir: /library
            max_age_hours: 12
            full_text: false
            feeds:
              - url: https://a.example/rss
                name: Feed A
                max_items: 5
              - url: https://b.example/rss
                name: Feed B
            """,
        )
    )
    assert cfg.output_dir == Path("/library")
    assert cfg.max_age_hours == 12
    assert len(cfg.feeds) == 2
    # Feed A overrides max_items; Feed B inherits the top-level default for full_text and the hard default for items.
    assert cfg.feeds[0].max_items == 5
    assert cfg.feeds[0].full_text is False
    assert cfg.feeds[1].max_items == DEFAULT_MAX_ITEMS
    assert cfg.feeds[1].full_text is False


def test_max_age_hours_per_feed_override_and_inheritance(tmp_path: Path) -> None:
    cfg = load_config(
        _write(
            tmp_path,
            """
            output_dir: /library
            max_age_hours: 48
            feeds:
              - url: https://curated.example/rss
                name: Curated
                max_age_hours: 4320
              - url: https://news.example/rss
                name: News
            """,
        )
    )
    assert cfg.max_age_hours == 48
    assert cfg.feeds[0].max_age_hours == 4320  # per-feed override
    assert cfg.feeds[1].max_age_hours == 48  # inherits the top-level default


def test_url_env_var_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_FEED", "https://secret.example/rss/tok3n")
    cfg = load_config(
        _write(
            tmp_path,
            """
            output_dir: /library
            feeds:
              - url: ${SECRET_FEED}
                name: Curated
            """,
        )
    )
    assert cfg.feeds[0].url == "https://secret.example/rss/tok3n"


def test_unset_env_var_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_FEED", raising=False)
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                """
                output_dir: /library
                feeds:
                  - url: ${MISSING_FEED}
                    name: Curated
                """,
            )
        )


def test_group_is_optional_and_parsed(tmp_path: Path) -> None:
    cfg = load_config(
        _write(
            tmp_path,
            """
            output_dir: /library
            feeds:
              - url: https://a.example/rss
                name: Grouped
                group: Wikipedia
              - url: https://b.example/rss
                name: Ungrouped
            """,
        )
    )
    assert cfg.feeds[0].group == "Wikipedia"
    assert cfg.feeds[1].group is None


def test_empty_group_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                "output_dir: /library\nfeeds:\n  - url: https://a/rss\n    name: A\n    group: '   '\n",
            )
        )


def test_missing_output_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "feeds:\n  - url: https://a.example/rss\n    name: A\n"))


def test_empty_feeds_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "output_dir: /library\nfeeds: []\n"))


def test_feed_missing_url_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "output_dir: /library\nfeeds:\n  - name: No URL\n"))


def test_non_positive_int_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(
            _write(
                tmp_path,
                "output_dir: /library\nmax_age_hours: 0\nfeeds:\n  - url: https://a/rss\n    name: A\n",
            )
        )
