"""Entrypoint: load config, build one EPUB per feed, write them to the output dir.

Resilience contract: a single failing entry must not fail its feed, and a single failing feed must not fail the
run. The process exits non-zero only if *every* feed failed. After a non-total-failure run, old EPUBs are pruned
from ``output_dir`` (see :mod:`feed2epub.retention`). Serving is intentionally out of scope here.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import httpx
import structlog

from .config import AppConfig, ConfigError, FeedConfig, load_config
from .epub import Article, build_book, slugify, write_book
from .extract import extract_article, fetch_html, make_client, sanitize_html
from .feeds import Entry, parse_entries
from .retention import prune

log = structlog.get_logger()


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def _article_from_entry(entry: Entry, feed_cfg: FeedConfig, client: httpx.Client) -> Article | None:
    """Turn one entry into an :class:`Article`, or ``None`` if no usable body can be produced."""
    body: str | None = None
    if feed_cfg.full_text and entry.url:
        html_text = fetch_html(client, entry.url)
        if html_text:
            body = extract_article(html_text, entry.url)
        if not body:
            log.warning("entry.extract_failed", feed=feed_cfg.name, url=entry.url, title=entry.title)

    if not body and entry.summary:
        body = sanitize_html(entry.summary) or None

    if not body:
        return None
    return Article(
        title=entry.title,
        author=entry.author,
        published=entry.published,
        url=entry.url,
        body_html=body,
    )


def _process_feed(feed_cfg: FeedConfig, cfg: AppConfig, client: httpx.Client, date_str: str, now: datetime) -> bool:
    """Build and write one feed's EPUB. Returns ``True`` if the feed *failed* (fetch/parse/write error)."""
    counts = {"entries_seen": 0, "entries_written": 0, "entries_failed": 0}

    raw = fetch_html(client, feed_cfg.url)
    if raw is None:
        log.warning("feed.fetch_failed", feed=feed_cfg.name, url=feed_cfg.url, **counts)
        return True

    try:
        meta, entries = parse_entries(raw, feed_cfg, now=now, max_age_hours=cfg.max_age_hours)
    except Exception as exc:  # a malformed feed must not crash the run
        log.warning("feed.parse_failed", feed=feed_cfg.name, error=str(exc), **counts)
        return True

    counts["entries_seen"] = len(entries)
    articles: list[Article] = []
    for entry in entries:
        try:
            article = _article_from_entry(entry, feed_cfg, client)
        except Exception as exc:  # one entry must never fail the feed
            log.warning("entry.error", feed=feed_cfg.name, url=entry.url, error=str(exc))
            article = None
        if article is None:
            counts["entries_failed"] += 1
            continue
        articles.append(article)
        counts["entries_written"] += 1

    if not articles:
        log.info("feed.no_articles", feed=feed_cfg.name, **counts)
        return False

    book = build_book(meta.title, date_str, meta.language, articles)
    out_path = cfg.output_dir / f"{slugify(feed_cfg.name)}-{date_str}.epub"
    try:
        write_book(book, out_path)
    except OSError as exc:
        log.error("feed.write_failed", feed=feed_cfg.name, path=str(out_path), error=str(exc), **counts)
        return True

    log.info("feed.done", feed=feed_cfg.name, path=str(out_path), **counts)
    return False


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="feed2epub")
    parser.add_argument("--config", type=Path, default=Path("/config/feeds.yaml"))
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        log.error("config.invalid", error=str(exc))
        return 2

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    date_str = now.strftime("%Y-%m-%d")

    failed = 0
    with make_client(cfg.user_agent, cfg.request_timeout) as client:
        for feed_cfg in cfg.feeds:
            if _process_feed(feed_cfg, cfg, client, date_str, now):
                failed += 1

    total = len(cfg.feeds)
    run_failed = total > 0 and failed == total

    # Prune only after a run that produced something usable: a total failure may signal a broken environment (DNS,
    # bad mount), and we would rather keep stale EPUBs than delete on a bad day. Serving remains out of scope here.
    if not run_failed:
        result = prune(cfg.output_dir, cfg.retention_days, today=now.date())
        log.info(
            "retention.done",
            deleted=len(result.deleted),
            kept=len(result.kept),
            errors=len(result.errors),
        )
        for name, error in result.errors:
            log.warning("retention.delete_failed", file=name, error=error)

    log.info("run.summary", feeds_total=total, feeds_failed=failed)
    return 1 if run_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
