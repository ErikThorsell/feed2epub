"""Generate an OPDS 1.2 acquisition catalog (Atom XML) for the feed EPUBs in a library folder.

This is the core of the "Option C" serving model: feed2epub owns a small catalog, served by a dumb file server,
isolated to its own EPUBs. Ownership is gated on the Dublin Core identifier stamped into every book we build
(``feed2epub:<slug>:<date>``) -- a stray book dropped in the folder is read, found foreign, and left out of the feed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ebooklib import epub

_ATOM = "http://www.w3.org/2005/Atom"
_DCTERMS = "http://purl.org/dc/terms/"
_OPDS = "http://opds-spec.org/2010/catalog"
_ACQUISITION_REL = "http://opds-spec.org/acquisition"
_CATALOG_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"
_EPUB_TYPE = "application/epub+zip"
_IDENTIFIER_PREFIX = "feed2epub:"

ET.register_namespace("", _ATOM)
ET.register_namespace("dcterms", _DCTERMS)
ET.register_namespace("opds", _OPDS)


@dataclass(frozen=True)
class Publication:
    """One catalog entry, sourced from an EPUB's own metadata. ``filename`` is the relative acquisition href."""

    identifier: str
    title: str
    author: str
    language: str
    filename: str
    updated: datetime
    sort_date: date


def _first(items: Any) -> str | None:
    """First value from an ebooklib ``get_metadata`` result (a list of ``(value, attrs)`` tuples), or ``None``."""
    if items:
        return str(items[0][0])
    return None


def _identifier_date(identifier: str) -> date | None:
    """Parse the trailing ``:YYYY-MM-DD`` off a ``feed2epub:<slug>:<date>`` identifier, if it is a real date."""
    try:
        return datetime.strptime(identifier.rsplit(":", 1)[-1], "%Y-%m-%d").date()
    except ValueError:
        return None


def _read_publication(path: Path) -> Publication | None:
    """Read one EPUB's metadata into a :class:`Publication`, or ``None`` if it is unreadable or not ours."""
    try:
        book = epub.read_epub(str(path))
    except Exception:
        return None  # unreadable / not a valid EPUB -- skip, never let one bad file break the whole catalog
    identifier = _first(book.get_metadata("DC", "identifier"))
    if identifier is None or not identifier.startswith(_IDENTIFIER_PREFIX):
        return None  # a foreign book that happens to share the folder; do not list it
    updated = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return Publication(
        identifier=identifier,
        title=_first(book.get_metadata("DC", "title")) or path.stem,
        author=_first(book.get_metadata("DC", "creator")) or "feed2epub",
        language=_first(book.get_metadata("DC", "language")) or "en",
        filename=path.name,
        updated=updated,
        sort_date=_identifier_date(identifier) or updated.date(),
    )


def scan_library(library_dir: Path) -> list[Publication]:
    """Read every ``*.epub`` in ``library_dir``, keep the ones we minted, and return them newest-first."""
    pubs: list[Publication] = []
    for path in sorted(library_dir.glob("*.epub")):
        if not path.is_file():
            continue
        pub = _read_publication(path)
        if pub is not None:
            pubs.append(pub)
    pubs.sort(key=lambda p: (p.sort_date, p.filename), reverse=True)
    return pubs


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(parent: ET.Element, tag: str, text: str) -> None:
    ET.SubElement(parent, tag).text = text


def _link(parent: ET.Element, *, rel: str, href: str, mime: str) -> None:
    ET.SubElement(parent, f"{{{_ATOM}}}link", {"rel": rel, "href": href, "type": mime})


def build_catalog(
    publications: list[Publication],
    *,
    updated: datetime,
    feed_id: str = "urn:feed2epub:catalog",
    feed_title: str = "feed2epub",
    self_href: str = "/catalog.xml",
) -> str:
    """Render ``publications`` as an OPDS acquisition feed.

    Hrefs are root-relative (``/<file>.epub``), not document-relative. CrossPoint (Xteink X4) resolves a
    document-relative acquisition href like ``foo.epub`` by *appending* it to the catalog path -- it fetches
    ``/catalog.xml/foo.epub`` and 404s instead of replacing the last segment per RFC 3986. A root-relative href
    ignores the catalog's own path, so it works on that client and stays correct on conformant ones. This assumes
    the catalog is served at the site root (the deployment fronts it at its own host), which it is.
    """
    feed = ET.Element(f"{{{_ATOM}}}feed")
    _text(feed, f"{{{_ATOM}}}id", feed_id)
    _text(feed, f"{{{_ATOM}}}title", feed_title)
    _text(feed, f"{{{_ATOM}}}updated", _iso(updated))
    _link(feed, rel="self", href=self_href, mime=_CATALOG_TYPE)
    _link(feed, rel="start", href=self_href, mime=_CATALOG_TYPE)

    for pub in publications:
        entry = ET.SubElement(feed, f"{{{_ATOM}}}entry")
        _text(entry, f"{{{_ATOM}}}id", pub.identifier)
        _text(entry, f"{{{_ATOM}}}title", pub.title)
        _text(entry, f"{{{_ATOM}}}updated", _iso(pub.updated))
        author = ET.SubElement(entry, f"{{{_ATOM}}}author")
        _text(author, f"{{{_ATOM}}}name", pub.author)
        _text(entry, f"{{{_DCTERMS}}}language", pub.language)
        _link(entry, rel=_ACQUISITION_REL, href=f"/{quote(pub.filename)}", mime=_EPUB_TYPE)

    ET.indent(feed)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(feed, encoding="unicode")
