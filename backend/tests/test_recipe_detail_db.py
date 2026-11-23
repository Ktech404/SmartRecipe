"""GET /recipes/slug/{slug} against the PostgreSQL test database.  (SCRUM-39)"""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_session
from app.db.models import Ingredient, Recipe, RecipeIngredient, User, UserRestricted
from app.main import create_app
from app.security import create_access_token
from app.services.recipe_detail import split_steps
from app.services.slugs import make_slug


@pytest.fixture()
def user(session):
    row = User(username="reader", email="reader@example.com", password_hash="x")
    session.add(row)
    session.flush()
    return row


@pytest.fixture()
def auth(user):
    token, _ = create_access_token(user.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


@pytest.fixture()
def recipe(session):
    ids = {}
    for name in ["garlic", "pasta", "peanut"]:
        row = Ingredient(name=name, category="test", is_staple=False)
        session.add(row)
        session.flush()
        ids[name] = row.ingredient_id
    row = Recipe(
        title="Garlic Pasta",
        source_url="https://example.com/garlic-pasta",
        source_name="Example",
        instructions="1. Boil the pasta.\n2) Fry the garlic.\n\nToss together.",
        total_minutes=20,
        servings=2,
        cuisine="Italian",
        tools=["stove"],
    )
    session.add(row)
    session.flush()
    session.add(RecipeIngredient(recipe_id=row.recipe_id, ingredient_id=ids["pasta"], quantity=200, unit="g", raw_text="200 g pasta"))
    session.add(RecipeIngredient(recipe_id=row.recipe_id, ingredient_id=ids["garlic"], quantity=2, unit="clove", is_optional=True))
    session.add(RecipeIngredient(recipe_id=row.recipe_id, ingredient_id=ids["peanut"], quantity=1, unit="cup"))
    session.flush()
    return row, ids


def test_split_steps_removes_numbers_and_blank_lines():
    assert split_steps("1. Boil.\n2) Fry.\n\nStep 3: Serve.") == ["Boil.", "Fry.", "Serve."]
    assert split_steps(None) == []
    assert split_steps("  \n ") == []


def test_returns_the_full_recipe(client, auth, recipe):
    row, ids = recipe
    response = client.get(f"/recipes/slug/{make_slug(row.title, row.recipe_id)}", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] == row.recipe_id
    assert body["slug"] == f"garlic-pasta-{row.recipe_id}"
    assert body["title"] == "Garlic Pasta"
    assert body["source_url"] == "https://example.com/garlic-pasta"
    assert body["total_minutes"] == 20
    assert body["servings"] == 2
    assert body["cuisine"] == "Italian"
    assert body["tools"] == ["stove"]
    assert body["instructions"] == ["Boil the pasta.", "Fry the garlic.", "Toss together."]
    assert [i["name"] for i in body["ingredients"]] == ["pasta", "garlic", "peanut"]
    assert body["ingredients"][0]["text"] == "200 g pasta"
    assert body["ingredients"][1]["is_optional"] is True
    assert body["restricted"] is False


def test_the_words_in_the_slug_do_not_matter(client, auth, recipe):
    row, _ = recipe
    response = client.get(f"/recipes/slug/an-old-title-{row.recipe_id}", headers=auth)
    assert response.status_code == 200
    assert response.json()["slug"] == f"garlic-pasta-{row.recipe_id}"


@pytest.mark.parametrize("slug", ["garlic-pasta-999999999", "garlic-pasta", "999999999"])
def test_unknown_recipe_is_404_in_the_standard_error_format(client, auth, slug):
    response = client.get(f"/recipes/slug/{slug}", headers=auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_login_is_required(client, recipe):
    row, _ = recipe
    assert client.get(f"/recipes/slug/garlic-pasta-{row.recipe_id}").status_code == 401


def test_recipe_that_breaks_the_users_allergy_is_flagged_not_hidden(client, auth, user, session, recipe):
    row, ids = recipe
    session.add(UserRestricted(user_id=user.user_id, ingredient_id=ids["peanut"], restriction_type="allergy"))
    session.flush()
    body = client.get(f"/recipes/slug/garlic-pasta-{row.recipe_id}", headers=auth).json()
    assert body["restricted"] is True
    assert len(body["ingredients"]) == 3
