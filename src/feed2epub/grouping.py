"""Plan which collected feeds become which EPUBs.

Pure, network-free logic so it is trivially testable. A feed with no ``group`` becomes its own book (unchanged
default behaviour); feeds sharing a ``group`` value are merged, in config order, into one book named after the group.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import FeedConfig
from .epub import Article, slugify
from .feeds import FeedMeta


@dataclass
class BookPlan:
    """One EPUB to build: a slug (drives the filename), a title/author, a language, and the articles to include.

    ``feeds`` lists the contributing feed names, for logging and failure bookkeeping.
    """

    slug: str
    title: str
    language: str
    articles: list[Article] = field(default_factory=list)
    feeds: list[str] = field(default_factory=list)


def plan_books(collected: list[tuple[FeedConfig, FeedMeta, list[Article]]]) -> list[BookPlan]:
    """Group successfully-collected feeds into ordered :class:`BookPlan`s.

    Grouped feeds key on ``slugify(group)`` and take the group as title; ungrouped feeds key on ``slugify(name)``
    and keep the feed's own metadata title, exactly as before. Plans preserve first-seen order; within a plan,
    articles are concatenated in feed (config) order.
    """
    plans: dict[str, BookPlan] = {}
    for feed_cfg, meta, articles in collected:
        if feed_cfg.group:
            key, title = slugify(feed_cfg.group), feed_cfg.group
        else:
            key, title = slugify(feed_cfg.name), meta.title
        plan = plans.get(key)
        if plan is None:
            plan = plans[key] = BookPlan(slug=key, title=title, language=meta.language)
        plan.articles.extend(articles)
        plan.feeds.append(feed_cfg.name)
    return list(plans.values())


def find_slug_collisions(feeds: tuple[FeedConfig, ...]) -> list[str]:
    """Return output slugs claimed by more than one distinct identity -- a likely footgun.

    Two feeds legitimately share a slug only when they share the same non-empty ``group``. Anything else that
    collapses to the same slug (a group vs. a same-named solo feed, or two groups that slugify alike) merges
    silently, so callers can warn on the returned slugs.
    """
    identities: dict[str, set[tuple[str, str]]] = {}
    for feed_cfg in feeds:
        if feed_cfg.group:
            slug, identity = slugify(feed_cfg.group), ("group", feed_cfg.group)
        else:
            slug, identity = slugify(feed_cfg.name), ("solo", feed_cfg.name)
        identities.setdefault(slug, set()).add(identity)
    return sorted(slug for slug, ids in identities.items() if len(ids) > 1)
