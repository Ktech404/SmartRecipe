"""Map a parsed recipe's ingredient lines to canonical ingredients.  (SCRUM-32)

The Gemini parser (SCRUM-31) gives us lines exactly as written on the page:

    "2 cloves garlic, minced"   "1 1/2 cups rice"   "Salt and pepper to taste"

Matching and storage need canonical ingredient names ("garlic", "rice") plus a
quantity and unit where there is one. This module does that, and decides whether
the recipe is clean enough to keep.

The team decision (Sprint 3): if a line is not in our ingredient vocabulary, we
SKIP THE RECIPE instead of adding an unverified ingredient. A recipe with a
missing ingredient would show up as a better match than it really is. The limit is
the `max_unrecognized` argument (default 0), so it can be loosened later without
rewriting anything. Unrecognized lines are always returned, so we can see which
ones to add to the seed CSVs.

The output is plain data (MappedIngredient). The ingestion script (SCRUM-33)
turns it into what the storage service (SCRUM-36) saves. Nothing here touches
the database except the optional load_lookup_from_db().
"""

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction

from typing import TYPE_CHECKING

from app.providers.base import RawRecipe
from app.services.normalization import (
    _QUANTITY_RE,
    _UNITS,
    build_lookup,
    normalize_ingredient,
    resolve_ingredient,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Spelled-out and abbreviated units, collapsed to one short form each.
_UNIT_NAMES = {
    "cups": "cup", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbs": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp", "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg", "ounce": "oz", "ounces": "oz",
    "pound": "lb", "pounds": "lb", "lbs": "lb", "milliliter": "ml",
    "milliliters": "ml", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
}
_MIN_INGREDIENTS = 2

# Wording that is common on recipe pages but that the normalizer does not handle.
# Each rule rewrites the line into the plain form the normalizer understands.
_CLEANUP_RULES = [
    # "Salt to taste", "olive oil for frying": notes without a comma
    (re.compile(r"\b(?:to taste|as needed|for serving|for garnish|for frying|for dusting)\b", re.I), " "),
    # "boneless, skinless chicken thighs": the comma would cut the line short
    (re.compile(r"\b(boneless|skinless|peeled|seeded|cored|trimmed|pitted),\s+(?=\w)", re.I), r"\1 "),
    # "1 cup uncooked rice"
    (re.compile(r"\buncooked\s+", re.I), ""),
    # "1 inch piece fresh ginger", "2-inch knob of ginger"
    (re.compile(r"\b\d+(?:/\d+)?[\s-]*inch(?:es)?\s+(?:piece|pieces|knob|chunk)?\s*(?:of\s+)?", re.I), "1 "),
    # "juice of 1 lime", "zest of a lemon"
    (re.compile(r"^\s*(?:juice|zest)\s+of\s+(?:\d+\s+)?(?:an?\s+)?", re.I), ""),
]


def _preclean(line: str) -> str:
    for pattern, replacement in _CLEANUP_RULES:
        line = pattern.sub(replacement, line)
    return line


@dataclass(frozen=True)
class MappedIngredient:
    name: str  # canonical name, exactly as in the ingredient table
    quantity: float | None = None
    unit: str | None = None
    is_optional: bool = False
    line: str = ""  # the original line, for logging


@dataclass(frozen=True)
class MappingResult:
    ok: bool
    ingredients: tuple[MappedIngredient, ...]
    unrecognized: tuple[str, ...]  # lines we could not map, always reported
    reason: str | None = None  # why the recipe was rejected, when ok is False


def _to_number(text: str) -> float | None:
    """'2' -> 2.0, '1/2' -> 0.5, '1 1/2' -> 1.5."""
    try:
        return float(sum(Fraction(part) for part in text.split()))
    except (ValueError, ZeroDivisionError):
        return None


def parse_quantity_and_unit(line: str) -> tuple[float | None, str | None]:
    """Read a leading quantity and unit from an ingredient line.

    "2 cloves garlic" -> (2.0, "clove");  "500g chicken" -> (500.0, "g");
    "2-3 eggs" -> (2.0, None) (a range keeps the lower number);  "salt" -> (None, None).
    """
    text = unicodedata.normalize("NFKD", line).replace("⁄", "/").strip()
    match = _QUANTITY_RE.match(text)
    if not match:
        return None, None
    first_number = re.split(r"\s*(?:-|to)\s*", match.group(0).strip())[0]
    quantity = _to_number(first_number)
    words = text[match.end():].split()
    unit = None
    if words and words[0].rstrip(".").lower() in _UNITS:
        raw_unit = words[0].rstrip(".").lower()
        unit = _UNIT_NAMES.get(raw_unit) or (
            raw_unit[:-1] if raw_unit.endswith("s") and len(raw_unit) > 3 else raw_unit
        )
    return quantity, unit


def _is_section_header(line: str) -> bool:
    """'For the sauce:' is a heading inside an ingredient list, not an ingredient."""
    stripped = line.strip()
    return stripped.endswith(":") and not any(ch.isdigit() for ch in stripped)


def map_ingredient_line(line: str, lookup: dict[str, str]) -> list[MappedIngredient] | None:
    """Map one line to one or two ingredients, or None if it is not recognized.

    "Salt and pepper to taste" gives two ingredients when both halves are known.
    """
    quantity, unit = parse_quantity_and_unit(line)
    optional = "optional" in line.lower()

    cleaned = _preclean(line)
    name = resolve_ingredient(cleaned, lookup)
    if name is not None:
        return [MappedIngredient(name, quantity, unit, optional, line)]

    # "salt and pepper": only accepted when BOTH halves are recognized.
    key = normalize_ingredient(cleaned)
    if " and " in key:
        names = [resolve_ingredient(part, lookup) for part in key.split(" and ")]
        if all(names):
            return [MappedIngredient(n, None, None, optional, line) for n in names]
    return None


def map_recipe(
    raw: RawRecipe,
    lookup: dict[str, str],
    *,
    max_unrecognized: int = 0,
    min_ingredients: int = _MIN_INGREDIENTS,
) -> MappingResult:
    """Map every ingredient line of a parsed recipe and decide whether to keep it."""
    mapped: list[MappedIngredient] = []
    unrecognized: list[str] = []
    seen: set[str] = set()

    for line in raw.ingredient_lines:
        if not line.strip() or _is_section_header(line):
            continue
        result = map_ingredient_line(line, lookup)
        if result is None:
            unrecognized.append(line)
            continue
        for item in result:
            # One row per ingredient: a second "salt" line adds nothing for matching.
            if item.name not in seen:
                seen.add(item.name)
                mapped.append(item)

    def rejected(reason: str) -> MappingResult:
        return MappingResult(False, tuple(mapped), tuple(unrecognized), reason)

    if not raw.ingredient_lines:
        return rejected("recipe has no ingredient lines")
    if len(unrecognized) > max_unrecognized:
        return rejected(f"{len(unrecognized)} unrecognized ingredient line(s)")
    if len(mapped) < min_ingredients:
        return rejected(f"only {len(mapped)} recognized ingredient(s)")
    return MappingResult(True, tuple(mapped), tuple(unrecognized))


def load_lookup_from_db(session: "Session") -> dict[str, str]:
    """Build the lookup from the ingredient and ingredient_synonym tables.

    Imported here so the pure functions above can be used without the models.
    """
    from sqlalchemy import select

    from app.db.models import Ingredient, IngredientSynonym

    names = list(session.execute(select(Ingredient.name)).scalars())
    rows = session.execute(
        select(IngredientSynonym.alias, Ingredient.name).join(
            Ingredient, Ingredient.ingredient_id == IngredientSynonym.ingredient_id
        )
    ).all()
    return build_lookup(names, {alias: name for alias, name in rows})
