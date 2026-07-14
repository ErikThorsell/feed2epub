"""Full-text extraction (``trafilatura``) and HTML sanitisation.

This is where the correctness risk lives. Whatever HTML enters :func:`sanitize_html` -- from trafilatura or from a
raw feed summary -- is reduced to a small semantic whitelist with no images, no CSS, and no attributes other than
``href`` on links. The device screen is small and monochrome, so images and styling are actively harmful.
"""

from __future__ import annotations

import html
import re
import time

import httpx
import lxml.html
import structlog
import trafilatura

log = structlog.get_logger()

# Elements removed wholesale, including their contents (media, scripting, styling, interactive chrome).
_DROP_TREE = frozenset(
    {
        "img",
        "figure",
        "picture",
        "svg",
        "video",
        "audio",
        "source",
        "canvas",
        "script",
        "style",
        "link",
        "iframe",
        "object",
        "embed",
        "noscript",
        "form",
        "button",
        "input",
        "select",
        "textarea",
    }
)

# Elements kept as-is. Anything else is unwrapped (its text is preserved, its tag is dropped).
_ALLOWED = frozenset({"h1", "h2", "h3", "p", "blockquote", "pre", "code", "ul", "ol", "li", "a", "br"})


def _local(tag: object) -> str:
    """Return the lowercase local name of an lxml tag, or '' for comments/PIs."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def sanitize_html(raw: str | None) -> str:
    """Reduce arbitrary HTML to the semantic whitelist. Returns '' if nothing survives."""
    if not raw or not raw.strip():
        return ""

    root = lxml.html.fragment_fromstring(raw, create_parent="body")

    # Pass 1: remove media/script/style subtrees. Materialise the node list first (mutating a live iterator skips
    # siblings), then process in document order and skip anything whose ancestor was already removed.
    dropped: set[int] = set()
    for el in list(root.iter()):
        if any(id(anc) in dropped for anc in el.iterancestors()):
            continue
        if _local(el.tag) in _DROP_TREE:
            dropped.add(id(el))
            el.drop_tree()

    # Remove comments outright.
    for comment in root.xpath(".//comment()"):
        parent = comment.getparent()
        if parent is not None:
            parent.remove(comment)

    # Pass 2: strip attributes (keep only href on <a>) and unwrap non-whitelisted tags.
    for el in list(root.iter()):
        tag = _local(el.tag)
        if not tag:
            continue
        for attr in list(el.attrib):
            if not (tag == "a" and attr == "href"):
                del el.attrib[attr]
        if tag not in _ALLOWED and el is not root:
            el.drop_tag()

    # Serialise the inner content as XML so void tags self-close (XHTML-safe for EPUB).
    parts = [html.escape(root.text)] if root.text else []
    parts += [lxml.html.tostring(child, method="xml", encoding="unicode") for child in root]
    return "".join(parts).strip()


def _demote_article_headings(fragment: str) -> str:
    """Drop a leading heading (the page's own title, which we already render as the chapter title) and demote any
    remaining ``<h1>`` to ``<h2>`` so the chapter's title stays the single ``<h1>``.
    """
    if not fragment:
        return fragment
    root = lxml.html.fragment_fromstring(fragment, create_parent="body")

    for first in root:  # only the first element child
        if _local(first.tag) in {"h1", "h2", "h3"}:
            first.drop_tree()
        break

    for el in root.iter():
        if _local(el.tag) == "h1":
            el.tag = "h2"

    parts = [html.escape(root.text)] if root.text else []
    parts += [lxml.html.tostring(child, method="xml", encoding="unicode") for child in root]
    return "".join(parts).strip()


def make_client(user_agent: str, timeout: int) -> httpx.Client:
    """An httpx client with a real User-Agent, a sane timeout, and redirect following."""
    return httpx.Client(
        headers={"User-Agent": user_agent},
        timeout=timeout,
        follow_redirects=True,
    )


def fetch_html(client: httpx.Client, url: str, *, retries: int = 2, backoff: float = 0.5) -> str | None:
    """GET ``url`` with a short retry/backoff. Returns the body text, or ``None`` if every attempt failed."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    log.warning("fetch.failed", url=url, error=str(last_error))
    return None


# trafilatura tags inline code as block-level ``<pre>``. A ``<pre>`` whose content spans no newline is inline code
# it mis-tagged: left as-is it renders as its own monospace block and -- because a block element cannot nest inside
# ``<p>`` -- forces the surrounding paragraph closed when the HTML is parsed, shredding the prose into fragments.
# This is not site-specific: across a 20-article sample from a dozen domains it hit ~70% of articles and ~91% of all
# ``<pre>`` elements. Genuine multi-line code blocks contain a newline and are left untouched.
_INLINE_PRE_RE = re.compile(r"<pre>([^\n]*?)</pre>")


def _inline_pre_to_code(fragment: str) -> str:
    """Rewrite single-line ``<pre>`` (mis-tagged inline code) to ``<code>``.

    Applied to trafilatura's raw output *before* parsing -- the only point at which the paragraph a block-level
    ``<pre>`` would otherwise break can still be kept intact.
    """
    return _INLINE_PRE_RE.sub(r"<code>\1</code>", fragment)


def extract_article(html_text: str, url: str | None) -> str | None:
    """Extract the main article body from a page and sanitise it. Returns ``None`` if extraction fails."""
    content = trafilatura.extract(
        html_text,
        url=url,
        output_format="html",
        include_images=False,
        include_comments=False,
        include_tables=False,
        include_links=True,
        favor_precision=False,
    )
    if not content:
        return None
    cleaned = _demote_article_headings(sanitize_html(_inline_pre_to_code(content)))
    return cleaned or None
