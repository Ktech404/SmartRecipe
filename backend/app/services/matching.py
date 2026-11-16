"""Score recipes against the ingredients a user owns, and tier them.  (SCRUM-34)

This module is pure Python: no database, no web framework. It answers one
question: "how well does this recipe match what the user has?"

    score = covered required ingredients / required ingredients

Rules (DEV_PLAN section 2, "Scoring sketch"):
- Optional ingredients are ignored.
- Pantry staples (salt, pepper, water, oil: ingredient.is_staple) are ignored,
  because nearly everyone has them. This is `MatchConfig.ignore_staples`.
- An ingredient counts fully if the user owns it, or owns something more
  specific (owns "cheddar cheese", recipe wants "cheese").
- An ingredient counts for half (`substitute_credit`) if the user owns a close
  relative: a sibling under the same parent (owns "cheddar", recipe wants
  "mozzarella") or something more general (owns "cheese", recipe wants
  "cheddar"). Those ingredients still appear in `missing`, with the owned
  relatives listed as `substitutes`, so the UI can suggest the swap.

The relatives come from `ingredient.parent_ingredient_id` (the hierarchy added
in migration 90bc5c5275ed). If no parents are filled in yet, only exact matches
count and everything else still works.

Tiers (thresholds live in MatchConfig so the team can tune them):
    best     score >= best_min     (default 1.0: you have everything)
    partial  score >= partial_min  (default 0.5)
    low      score >= low_min      (default 0.25)
    below low_min: the recipe is not returned
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

BEST = "best"
PARTIAL = "partial"
LOW = "low"


@dataclass(frozen=True)
class MatchConfig:
    best_min: float = 1.0
    partial_min: float = 0.5
    low_min: float = 0.25
    substitute_credit: float = 0.5
    ignore_staples: bool = True

    def __post_init__(self):
        if not (0 < self.low_min <= self.partial_min <= self.best_min <= 1.0):
            raise ValueError("thresholds must satisfy 0 < low <= partial <= best <= 1")
        if not (0 <= self.substitute_credit < 1):
            raise ValueError("substitute_credit must be at least 0 and below 1")

    def tier_for(self, score: float) -> str | None:
        """The tier name for a score, or None when the recipe is too weak to show."""
        if score >= self.best_min - 1e-9:
            return BEST
        if score >= self.partial_min:
            return PARTIAL
        if score >= self.low_min:
            return LOW
        return None


# --------------------------------------------------------------------------
# Ingredient hierarchy
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IngredientNode:
    ingredient_id: int
    name: str
    parent_id: int | None = None
    is_staple: bool = False


class IngredientGraph:
    """The ingredient table as a tree (each ingredient has at most one parent)."""

    def __init__(self, nodes: Iterable[IngredientNode]):
        self._nodes = {n.ingredient_id: n for n in nodes}
        self._children: dict[int, set[int]] = {}
        for node in self._nodes.values():
            if node.parent_id in self._nodes:
                self._children.setdefault(node.parent_id, set()).add(node.ingredient_id)

    def __contains__(self, ingredient_id: int) -> bool:
        return ingredient_id in self._nodes

    def name(self, ingredient_id: int) -> str:
        node = self._nodes.get(ingredient_id)
        return node.name if node else str(ingredient_id)

    def is_staple(self, ingredient_id: int) -> bool:
        node = self._nodes.get(ingredient_id)
        return bool(node and node.is_staple)

    def parent(self, ingredient_id: int) -> int | None:
        node = self._nodes.get(ingredient_id)
        if node is None or node.parent_id not in self._nodes:
            return None
        return node.parent_id

    def ancestors(self, ingredient_id: int) -> set[int]:
        """Every parent above this ingredient. Safe even if the data has a loop."""
        found: set[int] = set()
        current = self.parent(ingredient_id)
        while current is not None and current not in found and current != ingredient_id:
            found.add(current)
            current = self.parent(current)
        return found

    def descendants(self, ingredient_id: int) -> set[int]:
        """Every ingredient below this one (children, grandchildren, ...)."""
        found: set[int] = set()
        stack = list(self._children.get(ingredient_id, ()))
        while stack:
            current = stack.pop()
            if current in found or current == ingredient_id:
                continue
            found.add(current)
            stack.extend(self._children.get(current, ()))
        return found

    def siblings(self, ingredient_id: int) -> set[int]:
        parent = self.parent(ingredient_id)
        if parent is None:
            return set()
        return self._children.get(parent, set()) - {ingredient_id}


# --------------------------------------------------------------------------
# What the user owns
# --------------------------------------------------------------------------


class OwnedMatcher:
    """Answers "does the user have this?" for any ingredient id.

    full: ids that count completely (owned, or a more general ingredient than
          something owned).
    partial: ids that count for substitute_credit (relatives of owned ones).
    """

    def __init__(self, graph: IngredientGraph, owned_ids: Iterable[int]):
        self.graph = graph
        self.owned = {i for i in owned_ids}
        self.full: set[int] = set(self.owned)
        self.partial: set[int] = set()
        for ingredient_id in self.owned:
            self.full |= graph.ancestors(ingredient_id)
            self.partial |= graph.descendants(ingredient_id)
            self.partial |= graph.siblings(ingredient_id)
        self.partial -= self.full

    @property
    def candidate_ids(self) -> set[int]:
        """Every id that earns any credit: used to find recipes worth scoring."""
        return self.full | self.partial

    def substitutes_for(self, ingredient_id: int) -> list[str]:
        """Names of owned ingredients that could stand in for this one."""
        graph = self.graph
        parent = graph.parent(ingredient_id)
        general = graph.ancestors(ingredient_id)
        names = []
        for owned_id in self.owned:
            if owned_id == ingredient_id:
                continue
            if owned_id in general or (parent is not None and graph.parent(owned_id) == parent):
                names.append(graph.name(owned_id))
        return sorted(set(names))


# --------------------------------------------------------------------------
# Scoring one recipe
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RecipeLine:
    """One ingredient row of a stored recipe."""

    ingredient_id: int
    name: str
    quantity: float | None = None
    unit: str | None = None
    is_optional: bool = False
    is_staple: bool = False


@dataclass(frozen=True)
class MissingLine:
    ingredient_id: int
    name: str
    quantity: float | None = None
    unit: str | None = None
    substitutes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeMatch:
    score: float
    tier: str
    required: int  # how many ingredients counted toward the score
    missing: tuple[MissingLine, ...] = field(default_factory=tuple)


def score_recipe(
    lines: Sequence[RecipeLine],
    matcher: OwnedMatcher,
    config: MatchConfig = MatchConfig(),
) -> RecipeMatch | None:
    """Score one recipe. Returns None when it is not worth showing.

    That means: it has no countable ingredients, or its score is below the
    lowest tier.
    """
    required: list[RecipeLine] = []
    seen: set[int] = set()
    for line in lines:
        if line.is_optional or line.ingredient_id in seen:
            continue
        if config.ignore_staples and line.is_staple:
            continue
        seen.add(line.ingredient_id)
        required.append(line)
    if not required:
        return None

    total = 0.0
    missing: list[MissingLine] = []
    for line in required:
        if line.ingredient_id in matcher.full:
            total += 1.0
            continue
        if line.ingredient_id in matcher.partial:
            total += config.substitute_credit
        missing.append(
            MissingLine(
                ingredient_id=line.ingredient_id,
                name=line.name,
                quantity=line.quantity,
                unit=line.unit,
                substitutes=tuple(matcher.substitutes_for(line.ingredient_id)),
            )
        )

    score = total / len(required)
    tier = config.tier_for(score)
    if tier is None:
        return None
    return RecipeMatch(score=score, tier=tier, required=len(required), missing=tuple(missing))


def rank_key(recipe_id: int, match: RecipeMatch) -> tuple:
    """Sort key: best score first, then fewest missing, then a stable tie-break."""
    return (-match.score, len(match.missing), recipe_id)
