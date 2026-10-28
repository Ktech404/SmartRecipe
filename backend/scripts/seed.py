from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.db.session import SessionLocal
from app.db.models import Ingredient, IngredientSynonym, Preference

INGREDIENTS = [
    ("chicken breast", "protein", False), ("beef", "protein", False),
    ("garlic", "produce", False), ("onion", "produce", False),
    ("tomato", "produce", False), ("rice", "grain", False),
    ("pasta", "grain", False), ("egg", "dairy", False),
    ("milk", "dairy", False), ("cheddar cheese", "dairy", False),
    ("salt", "pantry", True), ("black pepper", "pantry", True),
    ("water", "pantry", True), ("olive oil", "pantry", True),
]

SYNONYMS = {  # alias -> canonical ingredient
    "sirloin steak": "beef", "ground beef": "beef",
    "eggs": "egg", "spaghetti": "pasta", "chicken": "chicken breast",
}

PREFERENCES = [
    ("vegetarian", "dietary"), ("vegan", "dietary"), ("gluten-free", "dietary"),
    ("dairy-free", "dietary"), ("keto", "dietary"),
    ("italian", "cuisine"), ("mexican", "cuisine"), ("indian", "cuisine"),
    ("chinese", "cuisine"), ("ugandan", "cuisine"),
]


def seed(session):
    for name, category, staple in INGREDIENTS:
        session.execute(
            insert(Ingredient)
            .values(name=name, category=category, is_staple=staple)
            .on_conflict_do_nothing(index_elements=["name"]))
    session.flush()
    ids = {row.name: row.ingredient_id
           for row in session.execute(select(Ingredient)).scalars()}
    for alias, canonical in SYNONYMS.items():
        session.execute(
            insert(IngredientSynonym)
            .values(alias=alias, ingredient_id=ids[canonical])
            .on_conflict_do_nothing(index_elements=["alias"]))
    for name, ptype in PREFERENCES:
        session.execute(
            insert(Preference)
            .values(name=name, type=ptype)
            .on_conflict_do_nothing(index_elements=["name", "type"]))
    session.commit()


if __name__ == "__main__":
    with SessionLocal() as s:
        seed(s)
    print("Seeded.")
