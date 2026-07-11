"""Assemble one EPUB per feed with ``ebooklib``: one chapter per article, a nav document, no cover.

The article bodies handed in here are already sanitised HTML fragments (see :mod:`feed2epub.extract`).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ebooklib import epub


@dataclass(frozen=True)
class Article:
    """One article, ready to become a chapter. ``body_html`` is a sanitised HTML fragment."""

    title: str
    author: str | None
    published: datetime | None
    url: str | None
    body_html: str


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lowercase ``name`` and collapse runs of non-alphanumerics to a single '-'."""
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "feed"


def _byline(article: Article) -> str:
    parts: list[str] = []
    if article.author:
        parts.append("By " + html.escape(article.author))
    if article.published:
        parts.append(article.published.strftime("%Y-%m-%d"))
    if article.url:
        parts.append(f'<a href="{html.escape(article.url, quote=True)}">Source</a>')
    return " -- ".join(parts)


def _chapter_body(article: Article) -> str:
    parts = [f"<h1>{html.escape(article.title)}</h1>"]
    byline = _byline(article)
    if byline:
        parts.append(f"<p>{byline}</p>")
    parts.append(article.body_html)
    return "".join(parts)


def build_book(feed_name: str, date_str: str, language: str, articles: list[Article]) -> epub.EpubBook:
    """Build an :class:`EpubBook` titled ``<feed_name> -- <date_str>`` with one chapter per article."""
    book = epub.EpubBook()
    book.set_identifier(f"feed2epub:{slugify(feed_name)}:{date_str}")
    book.set_title(f"{feed_name} -- {date_str}")
    book.set_language(language or "en")
    book.add_author(feed_name)

    chapters: list[epub.EpubHtml] = []
    for index, article in enumerate(articles):
        chapter = epub.EpubHtml(
            title=article.title,
            file_name=f"chap_{index:03d}.xhtml",
            lang=language or "en",
        )
        # ebooklib wraps this fragment in its own XHTML template; passing a full document (or an XML prolog)
        # double-wraps and yields an empty body.
        chapter.content = _chapter_body(article)
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]
    return book


def write_book(book: epub.EpubBook, path: Path) -> None:
    """Write ``book`` to ``path`` atomically (temp file + rename), so a poller never sees a partial EPUB."""
    tmp = path.with_name(path.name + ".tmp")
    epub.write_epub(str(tmp), book)
    tmp.replace(path)
