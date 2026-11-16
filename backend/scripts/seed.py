import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.db.session import SessionLocal
from app.db.models import Ingredient, IngredientSynonym, Preference

# The ingredient vocabulary lives in CSV files so it is easy to review and edit.
# backend/seed/ingredients.csv          -> name, category, is_staple
# backend/seed/ingredient_synonyms.csv  -> alias, canonical
SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

PREFERENCES = [
    ("vegetarian", "dietary"), ("vegan", "dietary"), ("gluten-free", "dietary"),
    ("dairy-free", "dietary"), ("keto", "dietary"),
    ("italian", "cuisine"), ("mexican", "cuisine"), ("indian", "cuisine"),
    ("chinese", "cuisine"), ("ugandan", "cuisine"),
]


def load_ingredients(seed_dir: Path = SEED_DIR):
    """Return [(name, category, is_staple), ...] from ingredients.csv."""
    with open(seed_dir / "ingredients.csv", newline="", encoding="utf-8") as f:
        return [
            (r["name"].strip(), r["category"].strip(),
             r["is_staple"].strip().lower() == "true")
            for r in csv.DictReader(f)
        ]


def load_synonyms(seed_dir: Path = SEED_DIR):
    """Return {alias: canonical} from ingredient_synonyms.csv."""
    with open(seed_dir / "ingredient_synonyms.csv", newline="", encoding="utf-8") as f:
        return {r["alias"].strip(): r["canonical"].strip()
                for r in csv.DictReader(f)}


def seed(session):
    for name, category, staple in load_ingredients():
        session.execute(
            insert(Ingredient)
            .values(name=name, category=category, is_staple=staple)
            .on_conflict_do_nothing(index_elements=["name"]))
    session.flush()
    ids = {row.name: row.ingredient_id
           for row in session.execute(select(Ingredient)).scalars()}
    for alias, canonical in load_synonyms().items():
        if canonical not in ids:
            raise ValueError(f"Synonym {alias!r} points at unknown ingredient {canonical!r}")
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
