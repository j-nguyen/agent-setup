"""URL slugs for post titles."""
import re
import unicodedata

MAX_SLUG_LENGTH = 60
FALLBACK_SLUG = "post"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Return a URL-safe slug for `title` (see tests for examples)."""
    # Non-ASCII punctuation and symbols (em dashes, emoji) separate words, so turn them
    # into spaces before dropping what can't be transliterated; accents stay as marks.
    decomposed = unicodedata.normalize("NFKD", title)
    spaced = "".join(c if c.isascii() or unicodedata.category(c)[0] in "LNM" else " " for c in decomposed)
    ascii_title = spaced.encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM.sub("-", ascii_title.lower()).strip("-")
    slug = slug[:MAX_SLUG_LENGTH].rstrip("-")
    return slug or FALLBACK_SLUG
