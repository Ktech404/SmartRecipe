"""Load one stored recipe for its detail page.  (SCRUM-39)

Nothing here calls a network API. The route (app/api/recipes.py) parses the slug
and passes the id and the user's restrictions in.
"""

import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, Recipe, RecipeIngredient
from app.schemas.recipe_detail import RecipeDetail, RecipeIngredientDetail
from app.services.matching import RecipeLine
from app.services.recipe_search import load_ingredient_groups, load_parents
from app.services.restrictions import Restrictions, is_safe
from app.services.slugs import make_slug

_STEP_NUMBER = re.compile(r"^\s*(?:step\s*)?\d+\s*[.):-]\s+", re.I)


def split_steps(text: str | None) -> list[str]:
    """Stored instructions are one block of text: one step per line, numbers removed."""
    if not text:
        return []
    steps = (_STEP_NUMBER.sub("", line).strip() for line in text.splitlines())
    return [step for step in steps if step]


def load_recipe_detail(
    session: Session, recipe_id: int, restrictions: Restrictions = Restrictions()
) -> RecipeDetail | None:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        return None

    rows = session.execute(
        select(
            RecipeIngredient.ingredient_id,
            Ingredient.name,
            RecipeIngredient.quantity,
            RecipeIngredient.unit,
            RecipeIngredient.is_optional,
            RecipeIngredient.raw_text,
            Ingredient.is_staple,
        )
        .join(Ingredient, Ingredient.ingredient_id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == recipe_id)
        .order_by(RecipeIngredient.recipe_ingredient_id)
    ).all()

    lines: Sequence[RecipeLine] = [
        RecipeLine(
            ingredient_id=r.ingredient_id,
            name=r.name,
            quantity=float(r.quantity) if r.quantity is not None else None,
            unit=r.unit,
            is_optional=bool(r.is_optional),
            is_staple=bool(r.is_staple),
        )
        for r in rows
    ]
    restricted = not is_safe(
        lines,
        restrictions,
        load_parents(session),
        load_ingredient_groups(session, restrictions.allergen_groups),
    )

    return RecipeDetail(
        recipe_id=recipe.recipe_id,
        slug=make_slug(recipe.title, recipe.recipe_id),
        title=recipe.title,
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        source_name=recipe.source_name,
        total_minutes=recipe.total_minutes,
        servings=recipe.servings,
        rating_avg=float(recipe.rating_avg) if recipe.rating_avg is not None else None,
        rating_count=recipe.rating_count,
        cuisine=recipe.cuisine,
        tools=list(recipe.tools or []),
        is_generated=bool(recipe.generated_tag),
        instructions=split_steps(recipe.instructions),
        ingredients=[
            RecipeIngredientDetail(
                ingredient_id=r.ingredient_id,
                name=r.name,
                quantity=float(r.quantity) if r.quantity is not None else None,
                unit=r.unit,
                is_optional=bool(r.is_optional),
                text=r.raw_text,
            )
            for r in rows
        ],
        restricted=restricted,
    )
