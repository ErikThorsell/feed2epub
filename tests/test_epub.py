from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ebooklib import epub

from feed2epub.epub import Article, build_book, slugify, write_book
from feed2epub.extract import sanitize_html


def test_slugify() -> None:
    assert slugify("Hacker News") == "hacker-news"
    assert slugify("LWN.net!!") == "lwn-net"
    assert slugify("  ---  ") == "feed"


def test_build_and_reopen_epub_no_images(tmp_path: Path) -> None:
    # Body deliberately contains an <img>; it must not survive into the EPUB.
    body = sanitize_html("<p>First paragraph.</p><img src='x.png'><p>Second.</p>")
    assert "<img" not in body

    articles = [
        Article(
            title="Article One",
            author="Jane Doe",
            published=datetime(2026, 7, 10, tzinfo=UTC),
            url="https://example.com/one",
            body_html=body,
        ),
        Article(title="Article Two", author=None, published=None, url=None, body_html="<p>Body two.</p>"),
    ]

    book = build_book("Example Feed", "2026-07-10", "en", articles)
    out = tmp_path / "example-feed-2026-07-10.epub"
    write_book(book, out)
    assert out.exists()
    assert not out.with_name(out.name + ".tmp").exists()  # temp file was renamed away

    reopened = epub.read_epub(str(out))
    assert reopened.title == "Example Feed"

    chapters = [i for i in reopened.get_items() if i.get_name().startswith("chap_")]
    assert len(chapters) == 2

    for chapter in chapters:
        assert b"<img" not in chapter.get_content()

    first = reopened.get_item_with_href("chap_000.xhtml").get_content().decode("utf-8")
    assert "<h1>Article One</h1>" in first
    assert "By Jane Doe" in first
    assert 'href="https://example.com/one"' in first
