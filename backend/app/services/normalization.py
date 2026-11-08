"""Ingredient normalization and synonym lookup (requirements 1.3.2, 1.3.7).

normalize_ingredient() turns messy text into a comparison key:

    "2 cloves garlic, minced"            -> "garlic"
    "1 lb boneless skinless chicken breasts" -> "chicken breast"
    "Black beans"                        -> "black bean"

The key is only for comparing. Canonical names stay as stored in the database.
Both sides of every comparison go through the same function (see build_lookup),
so an imperfect singularization is harmless as long as it is consistent.

Synonyms generalize: "sirloin steak" -> "beef". A user who owns "beef" matches
a recipe that lists "flank steak".

This module is pure Python with no database or network access.
"""

import csv
import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path

# 1, 1.5, 1/2, 1 1/2, and ranges such as 2-3 or 2 to 3
_NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
_QUANTITY_RE = re.compile(rf"^\s*{_NUM}(?:\s*(?:-|to)\s*{_NUM})?\s*")

# Units are only stripped when a quantity comes first ("2 cups rice"), so a
# bare "clove" (the spice) is left alone.
_UNITS = frozenset(
    """
    cup cups tablespoon tablespoons tbsp tbs teaspoon teaspoons tsp
    gram grams g kilogram kilograms kg ounce ounces oz pound pounds lb lbs
    milliliter milliliters ml liter liters litre litres l
    clove cloves can cans pack packs package packages pinch dash bunch
    slice slices stick sticks
    """.split()
)

# Preparation and size words that do not change which ingredient it is.
# Deliberately NOT included: "ground" (ground beef), "extra" (extra virgin),
# "crushed" (crushed tomatoes), "dried" (dried vs fresh herbs).
_DESCRIPTORS = frozenset(
    """
    minced chopped diced sliced grated shredded peeled melted softened cubed
    halved quartered trimmed rinsed drained divided fresh freshly large medium
    small boneless skinless finely roughly thinly optional packed heaping level
    frozen thawed
    """.split()
)

_IRREGULAR_PLURALS = {
    "leaves": "leaf",
    "loaves": "loaf",
    "halves": "half",
    "cookies": "cookie",
    "brownies": "brownie",
    "smoothies": "smoothie",
    "pies": "pie",
}

# Words that end in "s" but are already singular.
_NO_SINGULAR = frozenset(
    "hummus asparagus couscous molasses citrus octopus swiss bass".split()
)


def _singularize(word: str) -> str:
    if word in _NO_SINGULAR:
        return word
    if word in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[word]
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:  # cherries -> cherry
        return word[:-3] + "y"
    if word.endswith(("sses", "ches", "shes", "xes", "zes", "oes")):
        return word[:-2]  # peaches -> peach, tomatoes -> tomato
    if word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _strip_leading_measure(text: str) -> str:
    match = _QUANTITY_RE.match(text)
    if not match:
        return text
    words = text[match.end() :].split()
    if words and words[0].rstrip(".") in _UNITS:
        words = words[1:]
    if words and words[0] == "of":
        words = words[1:]
    return " ".join(words)


def normalize_ingredient(text: str) -> str:
    """Return the comparison key for an ingredient string ("" if nothing left)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\u2044", "/").lower()
    text = re.sub(r"\([^)]*\)", " ", text)  # drop "(extra virgin)"
    text = text.split(",")[0]  # drop ", minced" and ", to taste"
    text = text.replace("'", "").replace("\u2019", "")
    text = _strip_leading_measure(text.strip())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()
    words = [w for w in words if w not in _DESCRIPTORS] or words
    if not words:
        return ""
    words[-1] = _singularize(words[-1])
    return " ".join(words)


def build_lookup(
    canonical_names: Iterable[str],
    synonyms: Mapping[str, str],
) -> dict[str, str]:
    """Map normalized keys to canonical ingredient names.

    canonical_names: names exactly as stored in the ingredient table.
    synonyms: alias -> canonical name.

    Raises ValueError on blank keys, two canonicals with the same key, an alias
    pointing at an unknown canonical, or an alias claimed by two canonicals.
    """
    names = list(canonical_names)
    known = set(names)
    lookup: dict[str, str] = {}

    for name in names:
        key = normalize_ingredient(name)
        if not key:
            raise ValueError(f"ingredient name normalizes to nothing: {name!r}")
        if lookup.get(key, name) != name:
            raise ValueError(
                f"{name!r} and {lookup[key]!r} both normalize to {key!r}"
            )
        lookup[key] = name

    for alias, canonical in synonyms.items():
        if canonical not in known:
            raise ValueError(f"synonym {alias!r} points to unknown ingredient {canonical!r}")
        key = normalize_ingredient(alias)
        if not key:
            raise ValueError(f"synonym normalizes to nothing: {alias!r}")
        if lookup.get(key, canonical) != canonical:
            raise ValueError(
                f"synonym {alias!r} maps to {canonical!r} but {key!r} already "
                f"belongs to {lookup[key]!r}"
            )
        lookup[key] = canonical

    return lookup


def resolve_ingredient(text: str, lookup: Mapping[str, str]) -> str | None:
    """Return the canonical ingredient name for text, or None if unrecognized."""
    return lookup.get(normalize_ingredient(text))


def load_seed_lookup(seed_dir: Path) -> dict[str, str]:
    """Build a lookup from the seed CSVs.

    Convenience for tests and spikes until the lookup is built from the
    database. seed_dir contains ingredients.csv and ingredient_synonyms.csv.
    """
    with open(seed_dir / "ingredients.csv", newline="", encoding="utf-8") as f:
        names = [row["name"] for row in csv.DictReader(f)]
    with open(seed_dir / "ingredient_synonyms.csv", newline="", encoding="utf-8") as f:
        synonyms = {row["alias"]: row["canonical"] for row in csv.DictReader(f)}
    return build_lookup(names, synonyms)
