"""Search the stored recipes by the ingredients a user owns.  (SCRUM-34)

This is the database half of matching. The rules live in pure modules that need
no database:

- matching.py       scores and tiers recipes (best / partial / low)
- restrictions.py   removes recipes the user must not see (allergies, allergen
                    groups, blacklist)
- substitutes.py    suggests owned ingredients that could stand in for a missing one

This module loads the data they need and puts the steps in order:

1. turn ingredient names into ids (resolve_ingredient_ids),
2. find stored recipes that share at least one ingredient with the user,
   applying the time filter,
3. apply the tool filter,
4. drop recipes that break the user's restrictions, then score, tier and rank
   what is left (rank_stored, no database), and
5. return one page of RecipeResult objects (app/schemas/search.py) plus the total.

The POST /recipes/search route (SCRUM-35) calls search_stored_recipes() first and
adds live results when the stored ones are thin. Nothing here calls a network API.

Filters
- max_minutes: recipes with no stored time are kept (unknown is not "too long").
- tools: the tools the user HAS. A recipe is dropped if it needs a tool that is
  not in the list. Recipes that list no tools are kept. Empty list: no filter.

Very weak matches
- Recipes scoring below LOW_MIN_SCORE (one ingredient in four) are not returned:
  a recipe that shares a single ingredient with a long list is just noise.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Ingredient,
    IngredientAllergenGroup,
    Recipe,
    RecipeIngredient,
    UserAllergenGroup,
    UserRestricted,
)
from app.schemas.search import MatchTier, MissingIngredient, RecipeResult, Unit
from app.services.ingredient_mapping import load_lookup_from_db
from app.services.matching import (
    BEST_MIN_SCORE,
    PARTIAL_MIN_SCORE,
    Candidate,
    Match,
    RecipeLine,
    ancestors,
    rank_matches,
)
from app.services.normalization import resolve_ingredient
from app.services.restrictions import Restrictions, filter_safe
from app.services.slugs import make_slug
from app.services.substitutes import substitutes_for

LOW_MIN_SCORE = 0.25  # below this a recipe is not worth showing


@dataclass(frozen=True)
class ResolvedIngredients:
    ids: list[int] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)  # names we could not recognize


@dataclass(frozen=True)
class StoredSearchResult:
    results: list[RecipeResult]
    total: int  # matching recipes before limit/offset
    # How many of them are in the best or partial tier, across all pages. The
    # search endpoint uses this to decide whether the stored results are "thin".
    strong: int = 0


# --------------------------------------------------------------------------
# Pure steps (no database)
# --------------------------------------------------------------------------


def related_ids(owned: Iterable[int], parents: Mapping[int, int | None]) -> set[int]:
    """Every ingredient id that can earn credit for what the user owns.

    That is the owned ingredient itself, anything more general (owning
    "cheddar" covers a recipe that wants "cheese") and anything more specific
    (owning "cheese" covers "cheddar"). Used to find recipes worth scoring.
    """
    owned = set(owned)
    children: dict[int, set[int]] = defaultdict(set)
    for child, parent in parents.items():
        if parent is not None:
            children[parent].add(child)

    found = set(owned)
    for ingredient_id in owned:
        found |= ancestors(ingredient_id, parents)
    stack = list(owned)
    below: set[int] = set()
    while stack:
        for child in children.get(stack.pop(), ()):
            if child not in below:
                below.add(child)
                stack.append(child)
    return found | below


def rank_stored(
    candidates: Sequence[Candidate],
    owned: Collection[int],
    parents: Mapping[int, int | None],
    restrictions: Restrictions = Restrictions(),
    ingredient_groups: Mapping[int, Collection[int]] | None = None,
    *,
    min_score: float = LOW_MIN_SCORE,
    best_min: float = BEST_MIN_SCORE,
    partial_min: float = PARTIAL_MIN_SCORE,
) -> list[Match]:
    """Remove unsafe recipes, score the rest, drop very weak ones, best first."""
    safe = filter_safe(candidates, restrictions, parents, ingredient_groups)
    matches = rank_matches(safe, owned, parents, best_min=best_min, partial_min=partial_min)
    return [m for m in matches if m.score >= min_score - 1e-9]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_parents(session: Session) -> dict[int, int | None]:
    """ingredient_id -> parent_ingredient_id for the whole vocabulary."""
    rows = session.execute(
        select(Ingredient.ingredient_id, Ingredient.parent_ingredient_id)
    ).all()
    return {r.ingredient_id: r.parent_ingredient_id for r in rows}


def resolve_ingredient_ids(session: Session, names: Iterable[str]) -> ResolvedIngredients:
    """Names as the user typed them -> ingredient ids, using synonyms and cleanup.

    "Chicken Breasts" and "sirloin steak" both resolve if the vocabulary knows
    them. Names that do not resolve are returned in `unknown` so the caller can
    report them (requirement 1.3.12).
    """
    lookup = load_lookup_from_db(session)
    id_by_name = {
        row.name: row.ingredient_id
        for row in session.execute(select(Ingredient.ingredient_id, Ingredient.name)).all()
    }
    ids: list[int] = []
    unknown: list[str] = []
    for name in names:
        canonical = resolve_ingredient(name, lookup)
        ingredient_id = id_by_name.get(canonical) if canonical else None
        if ingredient_id is None:
            unknown.append(name)
        elif ingredient_id not in ids:
            ids.append(ingredient_id)
    return ResolvedIngredients(ids, unknown)


def load_restrictions(session: Session, user_id: int) -> Restrictions:
    """The user's allergies, blacklist and allergen groups (see restrictions.py)."""
    rows = session.execute(
        select(UserRestricted.ingredient_id, UserRestricted.restriction_type).where(
            UserRestricted.user_id == user_id
        )
    ).all()
    group_ids = session.execute(
        select(UserAllergenGroup.allergen_group_id).where(UserAllergenGroup.user_id == user_id)
    ).scalars()
    return Restrictions(
        allergies=frozenset(r.ingredient_id for r in rows if r.restriction_type == "allergy"),
        blacklist=frozenset(r.ingredient_id for r in rows if r.restriction_type == "blacklist"),
        allergen_groups=frozenset(group_ids),
    )


def load_ingredient_groups(
    session: Session, group_ids: Collection[int]
) -> dict[int, set[int]]:
    """ingredient_id -> the given allergen groups it belongs to."""
    if not group_ids:
        return {}
    rows = session.execute(
        select(IngredientAllergenGroup.ingredient_id, IngredientAllergenGroup.allergen_group_id)
        .where(IngredientAllergenGroup.allergen_group_id.in_(sorted(group_ids)))
    ).all()
    groups: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        groups[r.ingredient_id].add(r.allergen_group_id)
    return dict(groups)


def _unit(value: str | None) -> Unit | None:
    try:
        return Unit(value) if value else None
    except ValueError:
        return None


def _to_result(
    recipe: Recipe,
    match: Match,
    owned: Collection[int],
    parents: Mapping[int, int | None],
    names: Mapping[int, str],
) -> RecipeResult:
    return RecipeResult(
        recipe_id=recipe.recipe_id,
        slug=make_slug(recipe.title, recipe.recipe_id),
        title=recipe.title,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_name=recipe.source_name,
        total_minutes=recipe.total_minutes,
        rating_avg=float(recipe.rating_avg) if recipe.rating_avg is not None else None,
        rating_count=recipe.rating_count,
        is_generated=bool(recipe.generated_tag),
        tier=match.tier,
        match_score=round(min(match.score, 1.0), 4),
        missing_ingredients=[
            MissingIngredient(
                ingredient_id=line.ingredient_id,
                name=line.name,
                quantity=line.quantity,
                unit=_unit(line.unit),
                substitutes=substitutes_for(line.ingredient_id, owned, parents, names),
            )
            for line in match.missing
        ],
    )


# --------------------------------------------------------------------------
# The search
# --------------------------------------------------------------------------


def search_stored_recipes(
    session: Session,
    owned_ids: Iterable[int],
    *,
    max_minutes: int | None = None,
    tools: Sequence[str] = (),
    restrictions: Restrictions = Restrictions(),
    limit: int = 20,
    offset: int = 0,
) -> StoredSearchResult:
    owned = {int(i) for i in owned_ids}
    if not owned:
        return StoredSearchResult([], 0)

    parents = load_parents(session)

    query = select(Recipe).where(
        Recipe.recipe_id.in_(
            select(RecipeIngredient.recipe_id).where(
                RecipeIngredient.ingredient_id.in_(sorted(related_ids(owned, parents)))
            )
        )
    )
    if max_minutes is not None:
        query = query.where(
            or_(Recipe.total_minutes.is_(None), Recipe.total_minutes <= max_minutes)
        )
    recipes = {r.recipe_id: r for r in session.execute(query).scalars()}

    if tools:
        have = {t.strip().lower() for t in tools}
        recipes = {
            rid: r
            for rid, r in recipes.items()
            if not r.tools or {t.strip().lower() for t in r.tools} <= have
        }
    if not recipes:
        return StoredSearchResult([], 0)

    rows = session.execute(
        select(
            RecipeIngredient.recipe_id,
            RecipeIngredient.ingredient_id,
            Ingredient.name,
            RecipeIngredient.quantity,
            RecipeIngredient.unit,
            RecipeIngredient.is_optional,
            Ingredient.is_staple,
        )
        .join(Ingredient, Ingredient.ingredient_id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id.in_(sorted(recipes)))
        .order_by(RecipeIngredient.recipe_ingredient_id)
    ).all()
    lines: dict[int, list[RecipeLine]] = defaultdict(list)
    for r in rows:
        lines[r.recipe_id].append(
            RecipeLine(
                ingredient_id=r.ingredient_id,
                name=r.name,
                quantity=float(r.quantity) if r.quantity is not None else None,
                unit=r.unit,
                is_optional=bool(r.is_optional),
                is_staple=bool(r.is_staple),
            )
        )
    candidates = [
        Candidate(recipe_id=rid, title=recipe.title, lines=tuple(lines.get(rid, ())))
        for rid, recipe in recipes.items()
    ]

    matches = rank_stored(
        candidates,
        owned,
        parents,
        restrictions,
        load_ingredient_groups(session, restrictions.allergen_groups),
    )

    page = matches[offset : offset + limit]
    names = {
        row.ingredient_id: row.name
        for row in session.execute(
            select(Ingredient.ingredient_id, Ingredient.name).where(
                Ingredient.ingredient_id.in_(sorted(owned))
            )
        ).all()
    }
    return StoredSearchResult(
        results=[
            _to_result(recipes[m.recipe_id], m, owned, parents, names) for m in page
        ],
        total=len(matches),
        strong=sum(1 for m in matches if m.tier in (MatchTier.BEST, MatchTier.PARTIAL)),
    )
