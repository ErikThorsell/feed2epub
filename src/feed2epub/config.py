"""Load ``feeds.yaml`` into validated, immutable dataclasses.

Every per-feed key except ``url`` and ``name`` is optional and falls back to a top-level default, which in turn
falls back to a hard-coded module default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RETENTION_DAYS = 14
DEFAULT_MAX_AGE_HOURS = 36
DEFAULT_REQUEST_TIMEOUT = 20
DEFAULT_MAX_ITEMS = 25
DEFAULT_FULL_TEXT = True
DEFAULT_USER_AGENT = "feed2epub/1.0 (+https://wirsenius.se)"


class ConfigError(ValueError):
    """Raised when ``feeds.yaml`` is missing required data or has the wrong shape."""


@dataclass(frozen=True)
class FeedConfig:
    """A single feed, with all per-feed defaults already resolved."""

    url: str
    name: str
    max_items: int
    full_text: bool
    group: str | None
    """If set, this feed's articles are merged into a shared EPUB named after the group instead of its own."""


@dataclass(frozen=True)
class AppConfig:
    """Top-level configuration plus the resolved list of feeds."""

    output_dir: Path
    retention_days: int
    max_age_hours: int
    request_timeout: int
    user_agent: str
    feeds: tuple[FeedConfig, ...]


def _require_mapping(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{what} must be a mapping, got {type(value).__name__}")
    return value


def _require_str(mapping: dict[str, Any], key: str, what: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{what}: '{key}' is required and must be a non-empty string")
    return value.strip()


def _optional_str(mapping: dict[str, Any], key: str, what: str) -> str | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{what}: '{key}' must be a non-empty string when set")
    return value.strip()


def _positive_int(mapping: dict[str, Any], key: str, default: int, what: str) -> int:
    if key not in mapping or mapping[key] is None:
        return default
    value = mapping[key]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{what}: '{key}' must be a positive integer, got {value!r}")
    return value


def _bool(mapping: dict[str, Any], key: str, default: bool, what: str) -> bool:
    if key not in mapping or mapping[key] is None:
        return default
    value = mapping[key]
    if not isinstance(value, bool):
        raise ConfigError(f"{what}: '{key}' must be a boolean, got {value!r}")
    return value


def _parse_feed(raw: Any, index: int, defaults: dict[str, Any]) -> FeedConfig:
    what = f"feeds[{index}]"
    mapping = _require_mapping(raw, what)
    return FeedConfig(
        url=_require_str(mapping, "url", what),
        name=_require_str(mapping, "name", what),
        max_items=_positive_int(mapping, "max_items", defaults["max_items"], what),
        full_text=_bool(mapping, "full_text", defaults["full_text"], what),
        group=_optional_str(mapping, "group", what),
    )


def load_config(path: Path) -> AppConfig:
    """Parse and validate ``feeds.yaml`` at ``path``.

    Raises :class:`ConfigError` on any structural problem so the entrypoint can exit cleanly.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config at {path}: {exc}") from exc

    data = _require_mapping(yaml.safe_load(text) or {}, "config root")

    top_max_items = _positive_int(data, "max_items", DEFAULT_MAX_ITEMS, "config")
    top_full_text = _bool(data, "full_text", DEFAULT_FULL_TEXT, "config")
    defaults = {"max_items": top_max_items, "full_text": top_full_text}

    raw_feeds = data.get("feeds")
    if not isinstance(raw_feeds, list) or not raw_feeds:
        raise ConfigError("config: 'feeds' is required and must be a non-empty list")

    feeds = tuple(_parse_feed(raw, i, defaults) for i, raw in enumerate(raw_feeds))

    return AppConfig(
        output_dir=Path(_require_str(data, "output_dir", "config")),
        retention_days=_positive_int(data, "retention_days", DEFAULT_RETENTION_DAYS, "config"),
        max_age_hours=_positive_int(data, "max_age_hours", DEFAULT_MAX_AGE_HOURS, "config"),
        request_timeout=_positive_int(data, "request_timeout", DEFAULT_REQUEST_TIMEOUT, "config"),
        user_agent=data.get("user_agent") or DEFAULT_USER_AGENT,
        feeds=feeds,
    )
