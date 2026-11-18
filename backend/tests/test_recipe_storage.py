import pytest
from sqlalchemy import func, select

from app.db.models import Ingredient, Recipe, RecipeIngredient
from app.services.recipe_storage import (
    IngredientEntry,
    InvalidRecipe,
    RecipeToStore,
    UnknownIngredient,
    store_recipe,
)


@pytest.fixture()
def ingredients(session):
    for name in ["garlic", "pasta", "olive oil"]:
        session.add(Ingredient(name=name, category="test", is_staple=False))
    session.flush()


def _recipe(**overrides):
    data = dict(
        title="Garlic Pasta",
        source_url="https://example.com/garlic-pasta",
        source_name="Example",
        ingredients=[
            IngredientEntry("garlic", 2, "clove"),
            IngredientEntry("pasta", 200, "g"),
            IngredientEntry("olive oil", None, None, is_optional=True),
        ],
    )
    data.update(overrides)
    return RecipeToStore(**data)


def _count(session, model):
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def test_stores_recipe_without_instructions(session, ingredients):
    result = store_recipe(session, _recipe())
    r = result.recipe
    assert result.created is True
    assert r.recipe_id is not None
    assert r.instructions is None
    assert r.source_name == "Example"
    assert r.content_hash is not None and len(r.content_hash) == 64
    assert _count(session, RecipeIngredient) == 3


def test_source_url_is_stored_normalized(session, ingredients):
    r = store_recipe(
        session, _recipe(source_url="http://www.Example.com/garlic-pasta/?utm_source=x")
    ).recipe
    assert r.source_url == "https://example.com/garlic-pasta"


def test_same_url_with_tracking_is_a_duplicate(session, ingredients):
    first = store_recipe(session, _recipe())
    second = store_recipe(
        session, _recipe(source_url="https://www.example.com/garlic-pasta?utm_medium=email")
    )
    assert second.created is False
    assert second.recipe.recipe_id == first.recipe.recipe_id
    assert _count(session, Recipe) == 1


def test_same_recipe_on_another_site_is_a_duplicate(session, ingredients):
    first = store_recipe(session, _recipe())
    second = store_recipe(session, _recipe(source_url="https://other.com/pasta-with-garlic"))
    assert second.created is False
    assert second.recipe.recipe_id == first.recipe.recipe_id


def test_unknown_ingredient_stores_nothing(session, ingredients):
    bad = _recipe(ingredients=[IngredientEntry("garlic"), IngredientEntry("unicorn dust")])
    with pytest.raises(UnknownIngredient) as err:
        store_recipe(session, bad)
    assert err.value.names == ["unicorn dust"]
    assert _count(session, Recipe) == 0


@pytest.mark.parametrize(
    "overrides",
    [{"title": "  "}, {"source_url": "not a url"}, {"ingredients": []}],
)
def test_invalid_recipes_are_rejected(session, ingredients, overrides):
    with pytest.raises(InvalidRecipe):
        store_recipe(session, _recipe(**overrides))
    assert _count(session, Recipe) == 0


def test_original_ingredient_line_is_saved_as_raw_text(session, ingredients):
    recipe = _recipe(
        ingredients=[
            IngredientEntry("garlic", 2, "clove", raw_text="2 cloves garlic, minced"),
            IngredientEntry("pasta"),
        ]
    )
    stored = store_recipe(session, recipe).recipe
    rows = session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == stored.recipe_id)
    ).scalars().all()
    assert sorted((r.raw_text or "") for r in rows) == ["", "2 cloves garlic, minced"]
