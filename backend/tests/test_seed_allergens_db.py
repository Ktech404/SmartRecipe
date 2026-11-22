"""Seeding allergen groups into the PostgreSQL test database."""
from sqlalchemy import func, select

from app.db.models import AllergenGroup, Ingredient, IngredientAllergenGroup
from scripts.seed import load_ingredient_allergen_groups, seed


def _pairs(session):
    rows = session.execute(
        select(Ingredient.name, AllergenGroup.name)
        .join(IngredientAllergenGroup, IngredientAllergenGroup.ingredient_id == Ingredient.ingredient_id)
        .join(AllergenGroup, AllergenGroup.allergen_group_id == IngredientAllergenGroup.allergen_group_id)
    ).all()
    return {(i, g) for i, g in rows}


def test_seed_loads_allergen_groups_and_mappings(session):
    seed(session)
    pairs = _pairs(session)
    assert ("shrimp", "shellfish") in pairs
    assert ("milk", "dairy") in pairs
    assert ("soy sauce", "gluten") in pairs and ("soy sauce", "soy") in pairs
    assert pairs == set(load_ingredient_allergen_groups())


def test_seeding_twice_does_not_duplicate_anything(session):
    seed(session)
    first = session.execute(select(func.count()).select_from(IngredientAllergenGroup)).scalar_one()
    groups = session.execute(select(func.count()).select_from(AllergenGroup)).scalar_one()
    seed(session)
    assert session.execute(select(func.count()).select_from(IngredientAllergenGroup)).scalar_one() == first
    assert session.execute(select(func.count()).select_from(AllergenGroup)).scalar_one() == groups
