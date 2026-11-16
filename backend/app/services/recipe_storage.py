"""Save a parsed recipe to the database, skipping duplicates.  (SCRUM-36)

Ingestion (SCRUM-33) parses a page, maps each ingredient line to a canonical
ingredient name (SCRUM-32), then calls store_recipe(). This module only stores:
it does no searching, parsing or matching.

Duplicate rules (SCRUM-29 helpers):
1. same normalized source URL  -> already stored
2. same content hash           -> same recipe found on another site

A duplicate is not an error: store_recipe() returns the existing recipe with
created=False, so ingestion can simply move on.

store_recipe() flushes but never commits. The caller decides when to commit, so
a failed batch can be rolled back as a whole.
"""

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Ingredient, Recipe, RecipeIngredient
from app.services.dedupe import content_hash, normalize_url


class RecipeStorageError(Exception):
    """Base class for storage problems."""


class InvalidRecipe(RecipeStorageError):
    """The recipe is missing something we require (title, usable URL, ingredients)."""


class UnknownIngredient(RecipeStorageError):
    """An ingredient name is not in the ingredient table. Nothing was stored."""

    def __init__(self, names: list[str]):
        super().__init__(f"Unknown ingredients: {', '.join(names)}")
        self.names = names


@dataclass(frozen=True)
class IngredientEntry:
    name: str  # canonical ingredient name, exactly as stored in the ingredient table
    quantity: float | None = None
    unit: str | None = None
    is_optional: bool = False
    raw_text: str | None = None  # the original line, e.g. "2 cloves garlic, minced"


@dataclass(frozen=True)
class RecipeToStore:
    title: str
    source_url: str
    ingredients: list[IngredientEntry] = field(default_factory=list)
    instructions: str | None = None  # None is fine: the source link is enough
    source_name: str | None = None
    image_url: str | None = None
    total_minutes: int | None = None
    servings: int | None = None
    cuisine: str | None = None


@dataclass(frozen=True)
class StoreResult:
    recipe: Recipe
    created: bool  # False means it was already stored


def _find_existing(session: Session, url: str, hash_: str | None) -> Recipe | None:
    conditions = [Recipe.source_url == url]
    if hash_ is not None:
        conditions.append(Recipe.content_hash == hash_)
    return session.execute(select(Recipe).where(or_(*conditions))).scalars().first()


def store_recipe(session: Session, recipe: RecipeToStore) -> StoreResult:
    title = (recipe.title or "").strip()
    if not title:
        raise InvalidRecipe("recipe has no title")
    url = normalize_url(recipe.source_url)
    if url is None:
        raise InvalidRecipe(f"unusable source URL: {recipe.source_url!r}")
    if not recipe.ingredients:
        raise InvalidRecipe("recipe has no ingredients")

    # Hash on canonical names so "2 cloves garlic" and "garlic, minced" agree.
    hash_ = content_hash(title, [e.name for e in recipe.ingredients])

    existing = _find_existing(session, url, hash_)
    if existing is not None:
        return StoreResult(existing, created=False)

    names = sorted({e.name for e in recipe.ingredients})
    ids = {
        row.name: row.ingredient_id
        for row in session.execute(
            select(Ingredient).where(Ingredient.name.in_(names))
        ).scalars()
    }
    missing = [n for n in names if n not in ids]
    if missing:
        raise UnknownIngredient(missing)

    row = Recipe(
        title=title,
        instructions=recipe.instructions,
        image_url=recipe.image_url,
        source_url=url,
        source_name=recipe.source_name,
        content_hash=hash_,
        total_minutes=recipe.total_minutes,
        servings=recipe.servings,
        cuisine=recipe.cuisine,
    )

    try:
        # The savepoint lets us recover if another worker stored the same recipe
        # between our check and our insert (the unique constraints catch it).
        with session.begin_nested():
            session.add(row)
            session.flush()
            session.add_all(
                RecipeIngredient(
                    recipe_id=row.recipe_id,
                    ingredient_id=ids[e.name],
                    quantity=e.quantity,
                    unit=e.unit,
                    is_optional=e.is_optional,
                    raw_text=e.raw_text,
                )
                for e in recipe.ingredients
            )
            session.flush()
    except IntegrityError:
        existing = _find_existing(session, url, hash_)
        if existing is None:
            raise
        return StoreResult(existing, created=False)

    return StoreResult(row, created=True)
