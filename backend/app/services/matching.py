"""Score stored recipes against the ingredients a user has.

Pure Python, like normalization.py: no database or network access. The search
endpoint loads recipes and the ingredient hierarchy, then calls rank_matches().

How a recipe is scored
- Only required ingredients count. Optional ingredients and staples (salt,
  water, oil) are ignored.
- score = covered required ingredients / required ingredients.
- An ingredient is covered when the user owns it, or owns something more
  general in the hierarchy ("beef" covers "sirloin steak"), or something more
  specific ("sirloin steak" covers a recipe that just says "beef").
- Siblings do NOT cover each other: owning "flank steak" does not cover
  "sirloin steak".

Tiers: best >= BEST_MIN_SCORE, partial >= PARTIAL_MIN_SCORE, otherwise low.
Recipes that share no ingredient with the user (score 0) are dropped.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from app.schemas.search import MatchTier

# Tune these to taste. They can be overridden per call.
BEST_MIN_SCORE = 0.8
PARTIAL_MIN_SCORE = 0.5


@dataclass(frozen=True)
class RecipeLine:
    """One ingredient line of a stored recipe."""

    ingredient_id: int
    name: str
    quantity: float | None = None
    unit: str | None = None
    is_optional: bool = False
    is_staple: bool = False


@dataclass(frozen=True)
class Candidate:
    """A stored recipe, loaded with its ingredient lines."""

    recipe_id: int
    title: str
    lines: tuple[RecipeLine, ...]


@dataclass(frozen=True)
class Match:
    recipe_id: int
    title: str
    score: float
    tier: MatchTier
    missing: tuple[RecipeLine, ...]


def ancestors(ingredient_id: int, parents: Mapping[int, int | None]) -> set[int]:
    """All ingredients above this one in the hierarchy (parent, grandparent...).

    parents maps ingredient_id -> parent_ingredient_id. A loop in bad data
    cannot hang this: each ingredient is visited once.
    """
    seen: set[int] = set()
    current = parents.get(ingredient_id)
    while current is not None and current not in seen:
        seen.add(current)
        current = parents.get(current)
    seen.discard(ingredient_id)
    return seen


def _owned_and_ancestors(
    owned: Collection[int], parents: Mapping[int, int | None]
) -> set[int]:
    reach: set[int] = set(owned)
    for ingredient_id in owned:
        reach |= ancestors(ingredient_id, parents)
    return reach


def _is_covered(
    line_id: int,
    owned: Collection[int],
    owned_reach: set[int],
    parents: Mapping[int, int | None],
) -> bool:
    if line_id in owned_reach:  # owned it, or owned something more specific
        return True
    return bool(ancestors(line_id, parents) & set(owned))  # owned something general


def tier_for(
    score: float,
    best_min: float = BEST_MIN_SCORE,
    partial_min: float = PARTIAL_MIN_SCORE,
) -> MatchTier:
    if score >= best_min:
        return MatchTier.BEST
    if score >= partial_min:
        return MatchTier.PARTIAL
    return MatchTier.LOW


def score_recipe(
    candidate: Candidate,
    owned: Collection[int],
    parents: Mapping[int, int | None],
    *,
    best_min: float = BEST_MIN_SCORE,
    partial_min: float = PARTIAL_MIN_SCORE,
) -> Match:
    """Score one recipe. owned is the set of ingredient ids the user has."""
    # One entry per ingredient, even if the recipe lists it twice.
    needed: dict[int, RecipeLine] = {}
    for line in candidate.lines:
        if not line.is_optional and not line.is_staple:
            needed.setdefault(line.ingredient_id, line)

    owned_reach = _owned_and_ancestors(owned, parents)
    missing = tuple(
        line
        for line in needed.values()
        if not _is_covered(line.ingredient_id, owned, owned_reach, parents)
    )

    # A recipe with nothing to score (only staples/optionals) never ranks.
    score = (len(needed) - len(missing)) / len(needed) if needed else 0.0
    return Match(
        recipe_id=candidate.recipe_id,
        title=candidate.title,
        score=score,
        tier=tier_for(score, best_min, partial_min),
        missing=missing,
    )


def rank_matches(
    candidates: Sequence[Candidate],
    owned: Collection[int],
    parents: Mapping[int, int | None],
    *,
    best_min: float = BEST_MIN_SCORE,
    partial_min: float = PARTIAL_MIN_SCORE,
) -> list[Match]:
    """Score every recipe, drop zero scores, best first.

    Ties: fewer missing ingredients, then title, then recipe_id, so the order
    is the same every time.
    """
    matches = [
        score_recipe(c, owned, parents, best_min=best_min, partial_min=partial_min)
        for c in candidates
    ]
    matches = [m for m in matches if m.score > 0]
    matches.sort(key=lambda m: (-m.score, len(m.missing), m.title.lower(), m.recipe_id))
    return matches
