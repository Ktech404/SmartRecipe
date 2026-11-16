import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Recipe


def test_recipe_can_be_saved_without_instructions(session):
    r = Recipe(
        title="Link only",
        instructions=None,
        source_url="https://example.com/a",
        source_name="Example",
    )
    session.add(r)
    session.flush()
    assert r.recipe_id is not None


def test_duplicate_content_hash_is_rejected(session):
    session.add(Recipe(title="A", content_hash="abc"))
    session.flush()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(Recipe(title="B", content_hash="abc"))
            session.flush()


def test_many_recipes_can_have_no_content_hash(session):
    session.add(Recipe(title="A"))
    session.add(Recipe(title="B"))
    session.flush()