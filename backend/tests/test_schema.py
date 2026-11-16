import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (AllergenGroup, Ingredient, IngredientAllergenGroup,
                           IngredientSynonym, Recipe, RecipeIngredient, User,
                           UserAllergenGroup, UserInventory, UserRestricted)
from scripts.seed import seed


def make_user(session, name="manuel"):
    u = User(username=name, email=f"{name}@example.com", password_hash="x")
    session.add(u)
    session.flush()
    return u


def make_ingredient(session, name="garlic"):
    i = Ingredient(name=name)
    session.add(i)
    session.flush()
    return i


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_synonym_alias_is_unique_case_insensitive(session):
    ing = make_ingredient(session)
    session.add(IngredientSynonym(ingredient_id=ing.ingredient_id, alias="Spaghetti"))
    session.flush()
    session.add(IngredientSynonym(ingredient_id=ing.ingredient_id, alias="spaghetti"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_invalid_restriction_type_is_rejected(session):
    u, ing = make_user(session), make_ingredient(session)
    session.add(UserRestricted(user_id=u.user_id, ingredient_id=ing.ingredient_id,
                               restriction_type="banana"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_inventory_has_one_row_per_user_ingredient(session):
    u, ing = make_user(session), make_ingredient(session)
    session.add(UserInventory(user_id=u.user_id, ingredient_id=ing.ingredient_id))
    session.flush()
    session.add(UserInventory(user_id=u.user_id, ingredient_id=ing.ingredient_id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_user_cascades_to_inventory(session):
    u, ing = make_user(session), make_ingredient(session)
    session.add(UserInventory(user_id=u.user_id, ingredient_id=ing.ingredient_id))
    session.flush()
    session.delete(u)
    session.flush()
    assert count(session, UserInventory) == 0


def test_seed_is_idempotent(session):
    seed(session)
    first = count(session, Ingredient)
    seed(session)
    assert first > 0
    assert count(session, Ingredient) == first

def test_ingredient_can_have_a_parent(session):
    beef = make_ingredient(session, "beef")
    sirloin = Ingredient(name="sirloin steak", parent_ingredient_id=beef.ingredient_id)
    session.add(sirloin)
    session.flush()
    assert sirloin.parent_ingredient_id == beef.ingredient_id


def test_deleting_parent_ingredient_keeps_child(session):
    beef = make_ingredient(session, "beef")
    sirloin = Ingredient(name="sirloin steak", parent_ingredient_id=beef.ingredient_id)
    session.add(sirloin)
    session.flush()
    session.delete(beef)
    session.flush()
    session.refresh(sirloin)
    assert sirloin.parent_ingredient_id is None


def test_allergen_group_name_is_unique_case_insensitive(session):
    session.add(AllergenGroup(name="Dairy"))
    session.flush()
    session.add(AllergenGroup(name="dairy"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_ingredient_allergen_group_pair_is_unique(session):
    milk = make_ingredient(session, "milk")
    dairy = AllergenGroup(name="dairy")
    session.add(dairy)
    session.flush()
    row = {"ingredient_id": milk.ingredient_id,
           "allergen_group_id": dairy.allergen_group_id}
    session.execute(insert(IngredientAllergenGroup).values(**row))
    with pytest.raises(IntegrityError):
        session.execute(insert(IngredientAllergenGroup).values(**row))


def test_deleting_user_cascades_to_allergen_groups(session):
    u = make_user(session)
    nuts = AllergenGroup(name="tree nuts")
    session.add(nuts)
    session.flush()
    session.add(UserAllergenGroup(user_id=u.user_id,
                                  allergen_group_id=nuts.allergen_group_id))
    session.flush()
    session.delete(u)
    session.flush()
    assert count(session, UserAllergenGroup) == 0


def test_recipe_ingredient_keeps_raw_text(session):
    garlic = make_ingredient(session, "garlic")
    recipe = Recipe(title="Garlic bread")
    session.add(recipe)
    session.flush()
    line = RecipeIngredient(recipe_id=recipe.recipe_id,
                            ingredient_id=garlic.ingredient_id,
                            raw_text="2 cloves garlic, minced")
    session.add(line)
    session.flush()
    session.refresh(line)
    assert line.raw_text == "2 cloves garlic, minced"
