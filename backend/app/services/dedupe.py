"""URL normalization and content-hash helpers for deduplicating recipes.  (SCRUM-29)

The same recipe can reach us several ways: the same page with tracking
parameters added, or the same recipe copied onto a different site. Before
storing anything, ingestion asks two questions:

1. normalize_url():  is this the same page we already have?
2. content_hash():   is this the same recipe, even at a different URL?

Both are pure functions: no database, no network. Storage (SCRUM-36) saves
the results in recipe.source_url and recipe.content_hash.
"""

import hashlib
import re
from collections.abc import Callable, Iterable
from typing import TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

T = TypeVar("T")

# Query parameters that only track where a visitor came from. They never change
# which recipe the page shows, so they are removed before comparing URLs.
_TRACKING_PARAMS = {
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "igshid", "ref",
    "ref_src", "source", "campaign", "cmp", "pin_unauth",
    # Blog comment links (Blogger, WordPress): same post, different anchor.
    "showcomment", "replytocom",
}
_TRACKING_PREFIXES = ("utm_",)


def _is_tracking(name: str) -> bool:
    name = name.lower()
    return name in _TRACKING_PARAMS or name.startswith(_TRACKING_PREFIXES)


def normalize_url(url: str | None) -> str | None:
    """Return a canonical form of url, or None if it is not a usable web URL.

    - scheme and host are lowercased, http becomes https, "www." is dropped
    - default ports (80, 443) and the #fragment are dropped
    - tracking parameters (utm_*, fbclid, ...) are dropped, the rest are sorted
    - a trailing slash is dropped (except for the bare site root)
    """
    if not url or not url.strip():
        return None
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None

    host = parts.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    # Keep a non-default port, drop the default ones.
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking(k)
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))


def _clean_text(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def content_hash(title: str | None, ingredient_lines: Iterable[str]) -> str | None:
    """Return a SHA-256 hex digest that identifies a recipe by what it is.

    Built from the cleaned title plus the cleaned ingredient lines in sorted
    order, so the same recipe on two different sites usually hashes the same
    even if the ingredients are listed in a different order.

    Returns None when there is no title or no ingredient lines: without them
    different recipes could share a hash by accident, and a None hash is
    allowed to repeat in the database.
    """
    cleaned_title = _clean_text(title or "")
    lines = sorted({c for c in (_clean_text(l) for l in ingredient_lines) if c})
    if not cleaned_title or not lines:
        return None
    payload = cleaned_title + "\n" + "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dedupe_by_url(items: Iterable[T], get_url: Callable[[T], str | None]) -> list[T]:
    """Drop items whose normalized URL was already seen, keeping the first.

    Items with an unusable URL are dropped too, since we could not link back to
    them. Order is preserved.
    """
    seen: set[str] = set()
    kept: list[T] = []
    for item in items:
        key = normalize_url(get_url(item))
        if key is None or key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept
