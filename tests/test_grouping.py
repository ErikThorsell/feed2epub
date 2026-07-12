from __future__ import annotations

from feed2epub.config import FeedConfig
from feed2epub.epub import Article
from feed2epub.feeds import FeedMeta
from feed2epub.grouping import find_slug_collisions, plan_books


def _feed(name: str, group: str | None = None) -> FeedConfig:
    return FeedConfig(url=f"https://ex/{name}", name=name, max_items=25, full_text=False, group=group)


def _meta(title: str, language: str = "en") -> FeedMeta:
    return FeedMeta(title=title, language=language)


def _article(title: str) -> Article:
    return Article(title=title, author=None, published=None, url=None, body_html=f"<p>{title}</p>")


def test_ungrouped_feeds_each_get_their_own_book() -> None:
    collected = [
        (_feed("Feed A"), _meta("Feed A Title"), [_article("a1")]),
        (_feed("Feed B"), _meta("Feed B Title"), [_article("b1"), _article("b2")]),
    ]
    plans = plan_books(collected)

    assert [p.slug for p in plans] == ["feed-a", "feed-b"]
    # Ungrouped books keep the feed's own metadata title, exactly as before.
    assert [p.title for p in plans] == ["Feed A Title", "Feed B Title"]
    assert [len(p.articles) for p in plans] == [1, 2]


def test_grouped_feeds_merge_into_one_book_in_config_order() -> None:
    collected = [
        (_feed("Wikipedia Featured", group="Wikipedia"), _meta("Featured"), [_article("tfa")]),
        (_feed("Wikipedia On This Day", group="Wikipedia"), _meta("OTD"), [_article("otd1"), _article("otd2")]),
    ]
    plans = plan_books(collected)

    assert len(plans) == 1
    plan = plans[0]
    assert plan.slug == "wikipedia"
    assert plan.title == "Wikipedia"  # the group name, not either feed's title
    assert [a.title for a in plan.articles] == ["tfa", "otd1", "otd2"]  # sectioned, config order
    assert plan.feeds == ["Wikipedia Featured", "Wikipedia On This Day"]


def test_grouped_and_ungrouped_coexist_preserving_first_seen_order() -> None:
    collected = [
        (_feed("News", group="Daily"), _meta("News"), [_article("n")]),
        (_feed("Solo"), _meta("Solo"), [_article("s")]),
        (_feed("Sports", group="Daily"), _meta("Sports"), [_article("sp")]),
    ]
    plans = plan_books(collected)

    assert [p.slug for p in plans] == ["daily", "solo"]
    assert [len(p.articles) for p in plans] == [2, 1]  # Daily gathered both grouped feeds


def test_empty_collection_yields_no_plans() -> None:
    assert plan_books([]) == []


def test_find_slug_collisions_flags_group_vs_solo_and_clashing_groups() -> None:
    feeds = (
        _feed("Wikipedia", group="Wikipedia"),
        _feed("Wikipedia"),  # solo name collides with the group slug
        _feed("Tech News", group="Tech-News"),
        _feed("Extra", group="Tech News"),  # different group, same slug
    )
    assert find_slug_collisions(feeds) == ["tech-news", "wikipedia"]


def test_find_slug_collisions_allows_shared_group_and_distinct_feeds() -> None:
    feeds = (
        _feed("Wikipedia Featured", group="Wikipedia"),
        _feed("Wikipedia On This Day", group="Wikipedia"),
        _feed("Hacker News"),
        _feed("Lobsters"),
    )
    assert find_slug_collisions(feeds) == []
