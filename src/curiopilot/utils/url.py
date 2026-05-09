"""URL normalization for deduplication.

Many feeds tag the same article with different tracking parameters (Medium's
``?source=rss------machine_learning-5`` is the canonical example). String-equality
dedup misses these, so we normalize URLs to a canonical form before comparing.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit, urlunsplit

_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_name", "utm_brand", "utm_social", "utm_social-type",
        "source",
        "ref", "ref_src", "ref_url",
        "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "yclid",
        "_hsenc", "_hsmi",
        "feature",
    }
)


def normalize_url(url: str) -> str:
    """Return a canonical form of *url* suitable for dedup comparisons.

    - Lowercases scheme and host (path stays case-sensitive).
    - Drops the fragment.
    - Removes well-known tracking query parameters; preserves the rest in order.
    - Strips a single trailing slash from non-root paths.
    - Idempotent.
    """
    if not url:
        return url
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    if parts.query:
        kept = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
        ]
        from urllib.parse import urlencode

        query = urlencode(kept, doseq=True)
    else:
        query = ""

    return urlunsplit((scheme, netloc, path, query, ""))
