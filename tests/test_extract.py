from __future__ import annotations

from pathlib import Path

from feed2epub.extract import extract_article, sanitize_html

ARTICLE = Path(__file__).parent / "fixtures" / "article.html"


def test_sanitize_strips_media_and_script() -> None:
    raw = (
        '<div class="wrap"><img src="x.png"><figure><img src="y.png"><figcaption>cap</figcaption></figure>'
        "<script>evil()</script><style>.a{}</style><p>Kept text.</p><svg><path/></svg></div>"
    )
    out = sanitize_html(raw)
    for needle in ("<img", "<figure", "<figcaption", "<script", "<style", "<svg", "evil()"):
        assert needle not in out
    assert "Kept text." in out
    assert "<p>Kept text.</p>" in out


def test_sanitize_strips_attributes_except_href() -> None:
    raw = '<p class="c" style="color:red" id="p1">See <a href="https://x.example" class="link" rel="nofollow">x</a></p>'
    out = sanitize_html(raw)
    assert 'class="c"' not in out
    assert "style=" not in out
    assert 'id="p1"' not in out
    assert 'href="https://x.example"' in out
    assert "rel=" not in out


def test_sanitize_unwraps_unknown_tags_keeping_text() -> None:
    raw = "<section><div><span>Hello</span> <b>bold</b> world</div></section>"
    out = sanitize_html(raw)
    for tag in ("<section", "<div", "<span", "<b>"):
        assert tag not in out
    assert "Hello" in out
    assert "bold" in out
    assert "world" in out


def test_sanitize_empty_input() -> None:
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""
    assert sanitize_html("   ") == ""


def test_extract_article_produces_clean_body() -> None:
    html_text = ARTICLE.read_text(encoding="utf-8")
    body = extract_article(html_text, "https://example.com/post")
    assert body is not None
    # No media/scripts/styles survive extraction + sanitisation.
    for needle in ("<img", "<script", "<style", "<figure", "diagram", "track("):
        assert needle not in body
    # The page's own title heading is dropped (the chapter title provides the sole <h1>).
    assert "<h1" not in body
    # Real prose and a genuine subheading from the article body are retained.
    assert "separation of concerns" in body
    assert "<h2>Why one document per feed</h2>" in body
    assert "<p>" in body
