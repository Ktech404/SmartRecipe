"""Recipe slugs: the readable part of a recipe's address.  (SCRUM-39)

A slug is the title in lowercase words plus the recipe id, e.g.
"lemon-garlic-chicken-12". The id at the end is what is looked up, so no extra
database column or migration is needed, every stored recipe already has a slug,
and two recipes with the same title never clash. The words are only for people:
a slug with an out-of-date title still finds the recipe.
"""

import re
import unicodedata

MAX_WORDS_LENGTH = 60

_ID_AT_END = re.compile(r"(?:^|-)(\d{1,18})$")


def slugify(title: str) -> str:
    """'Lemon & Garlic Chicken!' -> 'lemon-garlic-chicken' ('recipe' if nothing is left)."""
    ascii_text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(words) > MAX_WORDS_LENGTH:
        words = words[:MAX_WORDS_LENGTH].rsplit("-", 1)[0] or words[:MAX_WORDS_LENGTH]
    return words or "recipe"


def make_slug(title: str, recipe_id: int) -> str:
    return f"{slugify(title)}-{recipe_id}"


def parse_slug_id(slug: str) -> int | None:
    """The recipe id at the end of a slug, or None if there is not one."""
    match = _ID_AT_END.search(slug.strip().lower())
    return int(match.group(1)) if match else None
