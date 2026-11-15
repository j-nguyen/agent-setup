"""URL slugs for post titles."""
import re
import unicodedata

MAX_SLUG_LENGTH = 60
FALLBACK_SLUG = "post"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Return a URL-safe slug for `title` (see tests for examples)."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM.sub("-", ascii_title.lower()).strip("-")
    slug = slug[:MAX_SLUG_LENGTH].rstrip("-")
    return slug or FALLBACK_SLUG
