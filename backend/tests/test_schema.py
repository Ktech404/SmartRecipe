import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import (Ingredient, IngredientSynonym, User,
                           UserInventory, UserRestricted)
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
