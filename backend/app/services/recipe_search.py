"""Search the stored recipes by the ingredients a user owns.  (SCRUM-34)

This is the database half of matching. The scoring rules live in matching.py
and need no database; this module:

1. turns ingredient names into ids (resolve_ingredient_ids),
2. finds stored recipes that share at least one ingredient with the user,
3. drops recipes that break the user's restrictions (allergies, blacklist and
   allergen groups, including everything below a restricted ingredient),
4. applies the time and tool filters,
5. scores, tiers and ranks what is left, and
6. returns one page of RecipeResult objects (the response model from
   app/schemas/search.py) plus the total count.

The POST /recipes/search route (SCRUM-35) calls search_stored_recipes() first and
adds live results when the stored ones are thin. Nothing here calls a network API.

Filters
- max_minutes: recipes with no stored time are kept (unknown is not "too long").
- tools: the tools the user HAS. A recipe is dropped if it needs a tool that is
  not in the list. Recipes that list no tools are kept. Empty list: no filter.
"""

from collections.abc import Iterable, Sequence
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
    IngredientGraph,
    IngredientNode,
    MatchConfig,
    OwnedMatcher,
    RecipeLine,
    RecipeMatch,
    rank_key,
    score_recipe,
)
from app.services.normalization import resolve_ingredient


@dataclass(frozen=True)
class Restrictions:
    """What a user must never be shown."""

    ingredient_ids: frozenset[int] = frozenset()  # allergies and blacklist
    allergen_group_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class ResolvedIngredients:
    ids: list[int] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)  # names we could not recognize


@dataclass(frozen=True)
class StoredSearchResult:
    results: list[RecipeResult]
    total: int  # matching recipes before limit/offset


def load_graph(session: Session) -> IngredientGraph:
    rows = session.execute(
        select(
            Ingredient.ingredient_id,
            Ingredient.name,
            Ingredient.parent_ingredient_id,
            Ingredient.is_staple,
        )
    ).all()
    return IngredientGraph(
        IngredientNode(r.ingredient_id, r.name, r.parent_ingredient_id, bool(r.is_staple))
        for r in rows
    )


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
    ingredient_ids = session.execute(
        select(UserRestricted.ingredient_id).where(UserRestricted.user_id == user_id)
    ).scalars()
    group_ids = session.execute(
        select(UserAllergenGroup.allergen_group_id).where(UserAllergenGroup.user_id == user_id)
    ).scalars()
    return Restrictions(frozenset(ingredient_ids), frozenset(group_ids))


def excluded_ingredient_ids(
    session: Session, graph: IngredientGraph, restrictions: Restrictions
) -> set[int]:
    """Every ingredient id a recipe must not contain.

    A restricted ingredient also excludes everything below it: an allergy to
    "cheese" excludes recipes with "cheddar cheese".
    """
    excluded = set(restrictions.ingredient_ids)
    if restrictions.allergen_group_ids:
        excluded |= set(
            session.execute(
                select(IngredientAllergenGroup.ingredient_id).where(
                    IngredientAllergenGroup.allergen_group_id.in_(
                        sorted(restrictions.allergen_group_ids)
                    )
                )
            ).scalars()
        )
    for ingredient_id in list(excluded):
        excluded |= graph.descendants(ingredient_id)
    return excluded


def _unit(value: str | None) -> Unit | None:
    try:
        return Unit(value) if value else None
    except ValueError:
        return None


def _to_result(recipe: Recipe, match: RecipeMatch) -> RecipeResult:
    return RecipeResult(
        recipe_id=recipe.recipe_id,
        title=recipe.title,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_name=recipe.source_name,
        total_minutes=recipe.total_minutes,
        rating_avg=float(recipe.rating_avg) if recipe.rating_avg is not None else None,
        rating_count=recipe.rating_count,
        is_generated=bool(recipe.generated_tag),
        tier=MatchTier(match.tier),
        match_score=round(min(match.score, 1.0), 4),
        missing_ingredients=[
            MissingIngredient(
                ingredient_id=m.ingredient_id,
                name=m.name,
                quantity=m.quantity,
                unit=_unit(m.unit),
                substitutes=list(m.substitutes),
            )
            for m in match.missing
        ],
    )


def search_stored_recipes(
    session: Session,
    owned_ids: Iterable[int],
    *,
    max_minutes: int | None = None,
    tools: Sequence[str] = (),
    restrictions: Restrictions = Restrictions(),
    config: MatchConfig = MatchConfig(),
    limit: int = 20,
    offset: int = 0,
    graph: IngredientGraph | None = None,
) -> StoredSearchResult:
    owned = {int(i) for i in owned_ids}
    if not owned:
        return StoredSearchResult([], 0)

    graph = graph or load_graph(session)
    matcher = OwnedMatcher(graph, owned)
    excluded = excluded_ingredient_ids(session, graph, restrictions)

    shares_an_ingredient = select(RecipeIngredient.recipe_id).where(
        RecipeIngredient.ingredient_id.in_(sorted(matcher.candidate_ids))
    )
    query = select(Recipe).where(Recipe.recipe_id.in_(shares_an_ingredient))
    if excluded:
        query = query.where(
            ~Recipe.recipe_id.in_(
                select(RecipeIngredient.recipe_id).where(
                    RecipeIngredient.ingredient_id.in_(sorted(excluded))
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
    lines: dict[int, list[RecipeLine]] = {}
    for r in rows:
        lines.setdefault(r.recipe_id, []).append(
            RecipeLine(
                ingredient_id=r.ingredient_id,
                name=r.name,
                quantity=float(r.quantity) if r.quantity is not None else None,
                unit=r.unit,
                is_optional=bool(r.is_optional),
                is_staple=bool(r.is_staple),
            )
        )

    scored: list[tuple[int, RecipeMatch]] = []
    for recipe_id in recipes:
        match = score_recipe(lines.get(recipe_id, []), matcher, config)
        if match is not None:
            scored.append((recipe_id, match))
    scored.sort(key=lambda item: rank_key(*item))

    page = scored[offset : offset + limit]
    return StoredSearchResult(
        results=[_to_result(recipes[recipe_id], match) for recipe_id, match in page],
        total=len(scored),
    )
