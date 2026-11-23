"""Seeding the ingredient hierarchy into the PostgreSQL test database.  (SCRUM-40)"""
from sqlalchemy import select

from app.db.models import Ingredient, IngredientSynonym
from app.services.ingredient_mapping import load_lookup_from_db
from app.services.normalization import resolve_ingredient
from app.services.recipe_search import load_parents
from app.services.substitutes import substitutes_for
from scripts.seed import load_ingredient_parents, seed


def _ids(session):
    return {r.name: r.ingredient_id for r in session.execute(select(Ingredient)).scalars()}


def test_seed_sets_every_parent(session):
    seed(session)
    ids, parents = _ids(session), load_parents(session)
    for child, parent in load_ingredient_parents():
        assert parents[ids[child]] == ids[parent], f"{child} -> {parent}"
    assert parents[ids["cream cheese"]] is None


def test_seeding_twice_keeps_the_same_hierarchy(session):
    seed(session)
    first = load_parents(session)
    seed(session)
    assert load_parents(session) == first


def test_owned_cheddar_is_offered_for_missing_mozzarella(session):
    seed(session)
    ids, parents = _ids(session), load_parents(session)
    names = {i: n for n, i in ids.items()}
    found = substitutes_for(ids["mozzarella cheese"], {ids["cheddar cheese"]}, parents, names)
    assert found == ["cheddar cheese"]
    found = substitutes_for(ids["chicken thigh"], {ids["chicken breast"]}, parents, names)
    assert found == ["chicken breast"]


def test_seeding_replaces_old_synonyms_so_the_lookup_still_builds(session):
    """A database seeded before "chicken" became its own ingredient still has the old
    alias rows. Seeding again must fix them (this broke every search once)."""
    seed(session)
    ids = _ids(session)
    for alias, target in [("chicken", "chicken breast"), ("shredded chicken", "chicken breast"),
                          ("zzz old alias", "garlic")]:
        row = session.execute(select(IngredientSynonym).where(IngredientSynonym.alias == alias)).scalar_one_or_none()
        if row is None:
            session.add(IngredientSynonym(alias=alias, ingredient_id=ids[target]))
        else:
            row.ingredient_id = ids[target]
    session.flush()

    seed(session)

    lookup = load_lookup_from_db(session)  # raises if two aliases clash
    assert resolve_ingredient("chicken", lookup) == "chicken"
    assert resolve_ingredient("shredded chicken", lookup) == "chicken"
    assert resolve_ingredient("zzz old alias", lookup) is None
