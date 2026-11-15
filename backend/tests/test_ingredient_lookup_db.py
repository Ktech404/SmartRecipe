"""load_lookup_from_db against the real PostgreSQL test database."""

from app.db.models import Ingredient, IngredientSynonym
from app.services.ingredient_mapping import load_lookup_from_db
from app.services.normalization import resolve_ingredient


def test_lookup_reads_ingredients_and_synonyms_from_the_database(session):
    egg = Ingredient(name="egg", category="dairy", is_staple=False)
    garlic = Ingredient(name="garlic", category="vegetable", is_staple=False)
    session.add_all([egg, garlic])
    session.flush()
    session.add(IngredientSynonym(alias="eggs", ingredient_id=egg.ingredient_id))
    session.flush()

    lookup = load_lookup_from_db(session)

    assert resolve_ingredient("2 cloves garlic, minced", lookup) == "garlic"
    assert resolve_ingredient("3 large eggs", lookup) == "egg"
    assert resolve_ingredient("dragon fruit", lookup) is None
