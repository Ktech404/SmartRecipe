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
def _split_glued_mixed_number(match: re.Match) -> str:
    """'11/2' is '1 1/2' with the space lost; '12/3' is '1 2/3'. Leave '10/2' alone."""
    whole, numerator, denominator = match.group(1), match.group(2), match.group(3)
    if 0 < int(numerator) < int(denominator):
        return f"{whole} {numerator}/{denominator}"
    return match.group(0)


_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6"}

_CLEANUP_RULES = [
    # list bullets copied from the page: "-1 tsp salt", "* 2 carrots", "\u2022 1 onion"
    (re.compile(r"^\s*[-\u2013\u2022*]+\s*(?=\w)"), ""),
    # "4 4-ounce pork chops": the count comes first, then the size of each
    (re.compile(r"^\s*(\d+)\s+\d+(?:\.\d+)?[\s-]*(?:ounces?|oz)\b\.?\s+(?!(?:cans?|jars?|packages?|pkgs?|boxe?s?|cartons?|bottles?|blocks?|bags?)\b)(?=[A-Za-z])", re.I), r"\1 "),
    # quantities: "1½" -> "1 ½", "1-1/3" -> "1 1/3", "11/2" -> "1 1/2", "One cucumber" -> "1 cucumber"
    (re.compile(r"(\d)([\u00bc-\u00be\u2150-\u215e])"), r"\1 \2"),
    (re.compile(r"(\d)-(\d+/\d+)"), r"\1 \2"),
    (re.compile(r"\b(\d)(\d)/([2348])\b"), _split_glued_mixed_number),
    (re.compile(r"^\s*(one|two|three|four|five|six)\s+", re.I),
     lambda m: _NUMBER_WORDS[m.group(1).lower()] + " "),
    # "2 Tbsp. and 2 tsp. vegetable oil": keep the first measure only
    (re.compile(r"\b(?:and|plus)\s+\d+(?:\s+\d+/\d+|/\d+)?\s*(?:tsp|tbsp|teaspoons?|tablespoons?|cups?|c)\b\.?\s*", re.I), ""),
    # "2/3 c. green onion": "c." means cup
    (re.compile(r"(?<=\d)\s+c\b\.?\s+(?=[A-Za-z])", re.I), " cup "),
    # "4 large cloves garlic": the size word sits between the number and the unit
    (re.compile(r"(?<=\d)\s+(?:large|medium|small)\s+", re.I), " "),
    # "1/2 bulb of garlic"
    (re.compile(r"\b(?:bulbs?|heads?)\s+of\s+", re.I), ""),
    # "5 or 6 large sweet potatoes": a range written with "or"
    (re.compile(r"^\s*(\d+(?:/\d+)?)\s+or\s+(\d+(?:/\d+)?)\b"), r"\1-\2"),
    # misspelled or abbreviated units
    (re.compile(r"\b(?:tblsp|tblspn|tbl)\b\.?", re.I), "tbsp"),
    (re.compile(r"(?<=\d)\s+tins?\b", re.I), " can"),
    (re.compile(r"(?<=\d)\s+pkgs?\b\.?", re.I), " package"),
    # "1 15-ounce can black beans", "one 14-oz. block tofu": keep the count, drop the package size
    (re.compile(r"^\s*(\d+)\s+\d+(?:\.\d+)?[\s-]*(?:ounces?|oz)\.?\s+(?:cans?|jars?|packages?|pkgs?|boxe?s?|cartons?|bottles?|blocks?|bags?)\b\.?\s*(?:of\s+)?", re.I), r"\1 can "),
    # "14 oz block of tofu": keep the weight, drop the package word
    (re.compile(r"(\d+(?:\.\d+)?[\s-]*(?:ounces?|oz|g|ml))\.?\s+(?:blocks?|bags?|boxe?s?|jars?|packages?|cartons?|bottles?)\s+(?:of\s+)?", re.I), r"\1 "),
    # "1 can (15 oz) can black beans"
    (re.compile(r"\bcan\s+(?:\([^)]*\)\s+)?can\b", re.I), "can"),
    # "Pinch of salt", "Dash of black pepper", "a pinch red pepper flakes"
    (re.compile(r"^\s*(?:an?\s+)?(pinch|dash)(?:es)?\s+(?:of\s+)?", re.I), r"1 \1 "),
    (re.compile(r"^\s*(?:an?\s+)?(?:shake|splash|handful|bunch)\s+of\s+", re.I), "1 "),
    # "Salt & pepper"
    (re.compile(r"\s&\s"), " and "),
    # "peeled and deveined shrimp": the "and" would split the line in two
    (re.compile(r"\b(?:peeled\s+)?and\s+deveined\s+", re.I), ""),
    # "diced tomatoes in juice"
    (re.compile(r"\b(?:in|with)\s+juice\b", re.I), ""),
    # "1 small container mascarpone cheese"
    (re.compile(r"(?<=\d)\s+(?:small\s+|large\s+)?(?:containers?|tubs?)\s+(?:of\s+)?", re.I), " "),
    # "1 loaf French bread", "2 ears fresh corn"
    (re.compile(r"(?<=\d)\s+loaf\s+(?:of\s+)?", re.I), " "),
    (re.compile(r"(?<=\d)\s+ears?\s+(?:of\s+)?", re.I), " "),
    # "1/2 tsp each of salt and pepper", "2 each eggs"
    (re.compile(r"\beach\b(?:\s+of\b)?\s*", re.I), ""),
    # "medium-sized potatoes", "filets"
    (re.compile(r"\b(?:large|medium|small)[\s-]sized\s+", re.I), ""),
    (re.compile(r"\bfilet(s?)\b", re.I), r"fillet\1"),
    # notes that follow the ingredient: "- divided use", "+ extra", "cut into 2 fillets",
    # a trailing sentence ("... You can use dried.")
    (re.compile(r"\s+[-\u2013]\s+(?:divided|plus|use|see).*$", re.I), ""),
    (re.compile(r"\s*\+\s*(?:extra|more)\b.*$", re.I), ""),
    (re.compile(r"\s+cut\s+into\s+.*$", re.I), ""),
    (re.compile(r"\.\s+(?:You|It|This|If|I|Use|Or|Note|See)\b.*$"), ""),
    (re.compile(r"\b(?:for the pan|for greasing|for brushing|for the grill)\b", re.I), " "),
    (re.compile(r"\bgood[\s-]quality\s+", re.I), ""),
    (re.compile(r"\blite\s+(?=soy)", re.I), ""),
    # "1 bell pepper red, yellow, or orange, chopped"
    (re.compile(r"\b(bell pepper)\s+(?:red|green|yellow|orange)\b.*$", re.I), r"\1"),
    # wording that describes the product, not which ingredient it is
    (re.compile(r"\b(?:low|reduced)[\s-](?:sodium|fat)\b,?\s*", re.I), ""),
    (re.compile(r"\b(?:fat|sugar)[\s-]free\b,?\s*", re.I), ""),
    (re.compile(r"\bnon[\s-]?fat\b,?\s*", re.I), ""),
    (re.compile(r"\bbone[\s-]in\b,?\s*", re.I), ""),
    (re.compile(r"\b(?:hot|warm|cold|ice|boiling|lukewarm)\s+water\b", re.I), "water"),
    (re.compile(r"\b(?:cooked and chilled|chilled)\s+", re.I), ""),
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
    text = unicodedata.normalize("NFKD", _preclean(line)).replace("⁄", "/").strip()
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


# Words that usually describe the form, not the ingredient. They are only dropped
# when the line is NOT recognized as written, so "ground beef" and "dried
# cranberries" still match exactly when the vocabulary has them, while "ground
# cinnamon" falls back to "cinnamon".
_SOFT_WORDS = frozenset(
    "dried ground whole light cooked raw plain toasted unsalted salted sweetened unsweetened lean crushed canned steamed boiled thin thick dry cold coarse cracked".split()
)


def _resolve(text: str, lookup: dict[str, str]) -> str | None:
    name = resolve_ingredient(text, lookup)
    if name is not None:
        return name
    words = normalize_ingredient(text).split()
    kept = [w for w in words if w not in _SOFT_WORDS]
    if kept and len(kept) < len(words):
        return lookup.get(" ".join(kept))
    return None


def _is_section_header(line: str) -> bool:
    """'For the sauce:' is a heading inside an ingredient list, not an ingredient."""
    stripped = line.strip()
    return stripped.endswith(":") and not any(ch.isdigit() for ch in stripped)


def map_ingredient_line(line: str, lookup: dict[str, str]) -> list[MappedIngredient] | None:
    """Map one line to one or two ingredients, or None if it is not recognized.

    "Salt and pepper to taste" gives two ingredients when both halves are known.
    """
    cleaned = _preclean(line)
    quantity, unit = parse_quantity_and_unit(cleaned)
    optional = "optional" in line.lower()

    name = _resolve(cleaned, lookup)
    if name is not None:
        return [MappedIngredient(name, quantity, unit, optional, line)]

    key = normalize_ingredient(cleaned)
    # "salt and pepper": only accepted when BOTH halves are recognized.
    if " and " in key:
        names = [_resolve(part, lookup) for part in key.split(" and ")]
        if all(names):
            return [MappedIngredient(n, None, None, optional, line) for n in names]
    # "butter or margarine", "sweet or smoked paprika": the first alternative we know.
    if " or " in key:
        for part in key.split(" or "):
            name = _resolve(re.sub(r"^other\s+", "", part.strip()), lookup)
            if name is not None:
                return [MappedIngredient(name, quantity, unit, optional, line)]
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
