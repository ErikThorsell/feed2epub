from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from ebooklib import epub

from feed2epub.epub import Article, build_book, slugify, write_book
from feed2epub.opds import build_catalog, scan_library

_ATOM = "{http://www.w3.org/2005/Atom}"


def _make_epub(dir_path: Path, feed_name: str, date_str: str) -> Path:
    articles = [Article(title="A", author=None, published=None, url=None, body_html="<p>Body.</p>")]
    book = build_book(feed_name, date_str, "en", articles)
    path = dir_path / f"{slugify(feed_name)}-{date_str}.epub"
    write_book(book, path)
    return path


def _make_foreign_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("urn:isbn:9780743273565")  # a real book's id, not ours
    book.set_title("The Great Gatsby")
    book.set_language("en")
    book.add_author("F. Scott Fitzgerald")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


def test_scan_library_lists_only_our_books_newest_first(tmp_path: Path) -> None:
    _make_epub(tmp_path, "Hacker News", "2026-07-09")
    _make_epub(tmp_path, "LWN", "2026-07-11")
    _make_foreign_epub(tmp_path / "gatsby-2026-07-10.epub")  # foreign identifier -> must be ignored
    (tmp_path / "notes.txt").write_text("not an epub", encoding="utf-8")

    pubs = scan_library(tmp_path)

    # Sorted by embedded date, newest first; the foreign book is absent despite its recent-looking filename.
    assert [p.title for p in pubs] == ["LWN -- 2026-07-11", "Hacker News -- 2026-07-09"]
    assert all(p.identifier.startswith("feed2epub:") for p in pubs)
    assert pubs[0].filename == "lwn-2026-07-11.epub"


def test_build_catalog_is_valid_opds_acquisition_feed(tmp_path: Path) -> None:
    _make_epub(tmp_path, "Hacker News", "2026-07-11")
    pubs = scan_library(tmp_path)

    xml = build_catalog(pubs, updated=datetime(2026, 7, 11, 12, 0, tzinfo=UTC))
    root = ET.fromstring(xml)

    assert root.tag == f"{_ATOM}feed"
    self_links = [link for link in root.findall(f"{_ATOM}link") if link.get("rel") == "self"]
    assert len(self_links) == 1
    self_type = self_links[0].get("type")
    assert self_type is not None and self_type.startswith("application/atom+xml")

    entries = root.findall(f"{_ATOM}entry")
    assert len(entries) == 1
    acquisition = entries[0].find(f"{_ATOM}link")
    assert acquisition is not None
    assert acquisition.get("rel") == "http://opds-spec.org/acquisition"
    assert acquisition.get("type") == "application/epub+zip"
    # Relative href so it resolves against whatever host/port the catalog is served from.
    assert acquisition.get("href") == "hacker-news-2026-07-11.epub"
