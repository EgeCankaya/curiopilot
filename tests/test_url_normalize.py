"""Tests for URL normalization helper."""

from __future__ import annotations

from curiopilot.utils.url import normalize_url


def test_strips_medium_source_param() -> None:
    base = "https://medium.com/@neonmaxima/rag-pipelines-04bc72599925"
    a = base + "?source=rss------machine_learning-5"
    b = base + "?source=rss------artificial_intelligence-5"
    assert normalize_url(a) == base
    assert normalize_url(a) == normalize_url(b)


def test_strips_utm_params() -> None:
    url = "https://example.com/article?utm_source=newsletter&utm_medium=email&utm_campaign=jan"
    assert normalize_url(url) == "https://example.com/article"


def test_preserves_real_query_params() -> None:
    assert normalize_url("https://example.com/post?id=123") == "https://example.com/post?id=123"
    assert normalize_url("https://wp.test/?p=42") == "https://wp.test/?p=42"


def test_preserves_real_params_alongside_tracking() -> None:
    url = "https://example.com/p?id=42&utm_source=x&fbclid=abc"
    assert normalize_url(url) == "https://example.com/p?id=42"


def test_drops_fragment() -> None:
    assert normalize_url("https://example.com/a#section") == "https://example.com/a"


def test_lowercases_scheme_and_host() -> None:
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_strips_trailing_slash_but_keeps_root() -> None:
    assert normalize_url("https://example.com/foo/") == "https://example.com/foo"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_idempotent() -> None:
    url = "https://example.com/x?utm_source=a&id=1#frag"
    once = normalize_url(url)
    assert once == normalize_url(once)


def test_strips_misc_trackers() -> None:
    url = "https://example.com/x?gclid=a&ref=b&mc_eid=c&igshid=d"
    assert normalize_url(url) == "https://example.com/x"


def test_empty_input() -> None:
    assert normalize_url("") == ""
