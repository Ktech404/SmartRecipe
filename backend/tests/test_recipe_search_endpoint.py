"""POST /recipes/search against the PostgreSQL test database.  (SCRUM-35)

The web search is replaced by a fake, so these tests need no API keys or quota.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_session
from app.api.recipes import get_live_fetcher, get_live_settings, get_recent_searches
from app.db.models import Ingredient, Recipe, RecipeIngredient, User, UserRestricted
from app.main import create_app
from app.security import create_access_token
from app.services.live_search import LiveOutcome, LiveSearchSettings, RecentSearchCache


class FakeLive:
    """Stands in for the web search. `on_fetch` can add recipes like the real one would."""

    def __init__(self, outcome=None, on_fetch=None, error=None):
        self.outcome = outcome or LiveOutcome(True, 0)
        self.on_fetch = on_fetch
        self.error = error
        self.queries = []

    def fetch(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        if self.on_fetch:
            self.on_fetch()
        return self.outcome


@pytest.fixture()
def kitchen(session):
    ids = {}
    for name in ["garlic", "pasta", "basil", "tomato", "peanut", "rice"]:
        row = Ingredient(name=name, category="test", is_staple=False)
        session.add(row)
        session.flush()
        ids[name] = row.ingredient_id
    return ids


@pytest.fixture()
def user(session):
    row = User(username="searcher", email="searcher@example.com", password_hash="x")
    session.add(row)
    session.flush()
    return row


@pytest.fixture()
def auth(user):
    token, _ = create_access_token(user.user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_client(session):
    def build(live=None, **settings):
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_live_fetcher] = lambda: live
        app.dependency_overrides[get_live_settings] = lambda: LiveSearchSettings(**settings)
        recent = RecentSearchCache()  # a fresh memory for every client
        app.dependency_overrides[get_recent_searches] = lambda: recent
        return TestClient(app)

    return build


def add_recipe(session, kitchen, title, names, **fields):
    recipe = Recipe(title=title, source_url=f"https://example.com/{title.replace(' ', '-')}", **fields)
    session.add(recipe)
    session.flush()
    for name in names:
        session.add(RecipeIngredient(recipe_id=recipe.recipe_id, ingredient_id=kitchen[name], quantity=1, unit="cup"))
    session.flush()
    return recipe


def search(client, auth, names=("garlic", "pasta"), **extra):
    body = {"ingredients": [{"name": n} for n in names], **extra}
    return client.post("/recipes/search", json=body, headers=auth)


# ---- checking the request ---------------------------------------------------


def test_login_is_required(make_client):
    response = make_client().post("/recipes/search", json={"ingredients": [{"name": "garlic"}]})
    assert response.status_code == 401


def test_too_few_ingredients_returns_the_standard_error(make_client, auth, kitchen):
    response = search(make_client(), auth, names=("garlic",))
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "too_few_ingredients", "message": "Enter at least 2 different ingredients."}
    }


def test_the_same_ingredient_twice_is_still_too_few(make_client, auth, kitchen):
    assert search(make_client(), auth, names=("garlic", "Garlic")).status_code == 422


def test_unrecognized_ingredients_are_listed(make_client, auth, kitchen):
    response = search(make_client(), auth, names=("garlic", "dragon fruit", "moon dust"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_ingredients"
    assert error["invalid_ingredients"] == ["dragon fruit", "moon dust"]


def test_schema_problems_use_the_validation_error_shape(make_client, auth):
    response = make_client().post("/recipes/search", json={"ingredients": [], "limit": 500}, headers=auth)
    assert response.status_code == 422 and "detail" in response.json()


# ---- searching stored recipes -----------------------------------------------


def test_stored_recipes_are_returned_with_tiers(make_client, auth, session, kitchen):
    add_recipe(session, kitchen, "Garlic Pasta", ["garlic", "pasta"])
    add_recipe(session, kitchen, "Tomato Pasta", ["tomato", "pasta", "garlic", "basil"])
    live = FakeLive()
    response = search(make_client(live, thin_threshold=1), auth)
    assert response.status_code == 200
    body = response.json()
    assert [r["title"] for r in body["results"]] == ["Garlic Pasta", "Tomato Pasta"]
    assert [r["tier"] for r in body["results"]] == ["best", "partial"]
    assert body["total"] == 2 and body["limit"] == 20 and body["offset"] == 0
    assert body["degraded"] is False
    assert [m["name"] for m in body["results"][1]["missing_ingredients"]] == ["tomato", "basil"]
    assert live.queries == []  # enough good matches: no web search


def test_filters_are_applied(make_client, auth, session, kitchen):
    add_recipe(session, kitchen, "Quick", ["garlic", "pasta"], total_minutes=15)
    add_recipe(session, kitchen, "Slow", ["garlic", "pasta"], total_minutes=120)
    response = search(make_client(None, enabled=False), auth, max_minutes=30)
    assert [r["title"] for r in response.json()["results"]] == ["Quick"]


def test_the_users_allergies_are_respected(make_client, auth, session, kitchen, user):
    add_recipe(session, kitchen, "Peanut Pasta", ["pasta", "peanut", "garlic"])
    add_recipe(session, kitchen, "Plain Pasta", ["pasta", "garlic"])
    session.add(UserRestricted(user_id=user.user_id, ingredient_id=kitchen["peanut"], restriction_type="allergy"))
    session.flush()
    response = search(make_client(None, enabled=False), auth, names=("pasta", "garlic", "peanut"))
    assert [r["title"] for r in response.json()["results"]] == ["Plain Pasta"]


def test_paging_returns_a_page_and_the_total(make_client, auth, session, kitchen):
    for i in range(4):
        add_recipe(session, kitchen, f"Pasta {i}", ["garlic", "pasta"])
    client = make_client(None, enabled=False)
    page = search(client, auth, limit=3, offset=2).json()
    assert page["total"] == 4 and len(page["results"]) == 2 and page["offset"] == 2


# ---- web search fallback ----------------------------------------------------


def test_thin_results_trigger_a_web_search_and_the_new_recipes_are_included(make_client, auth, session, kitchen):
    live = FakeLive(
        LiveOutcome(True, 1),
        on_fetch=lambda: add_recipe(session, kitchen, "Fresh From The Web", ["garlic", "pasta"]),
    )
    response = search(make_client(live, thin_threshold=3), auth, max_minutes=45, tools=["oven"])
    body = response.json()
    assert [r["title"] for r in body["results"]] == ["Fresh From The Web"]
    assert body["degraded"] is False
    [query] = live.queries
    assert query.ingredients == ("garlic", "pasta")
    assert query.max_minutes == 45 and query.tools == ("oven",) and query.limit == 6


def test_a_failed_web_search_returns_stored_results_marked_degraded(make_client, auth, session, kitchen):
    add_recipe(session, kitchen, "Stored Pasta", ["garlic", "pasta"])
    live = FakeLive(LiveOutcome(False, 0, "rate limited"))
    body = search(make_client(live, thin_threshold=5), auth).json()
    assert body["degraded"] is True
    assert [r["title"] for r in body["results"]] == ["Stored Pasta"]


def test_a_crashing_web_search_never_breaks_the_stored_search(make_client, auth, session, kitchen):
    add_recipe(session, kitchen, "Stored Pasta", ["garlic", "pasta"])
    live = FakeLive(error=RuntimeError("boom"))
    response = search(make_client(live, thin_threshold=5), auth)
    assert response.status_code == 200
    assert response.json()["degraded"] is True
    assert [r["title"] for r in response.json()["results"]] == ["Stored Pasta"]


def test_not_configured_live_search_is_degraded_when_results_are_thin(make_client, auth, session, kitchen):
    body = search(make_client(None, thin_threshold=5), auth).json()
    assert body["degraded"] is True and body["results"] == []


def test_turning_live_search_off_is_not_degraded(make_client, auth, session, kitchen):
    live = FakeLive()
    body = search(make_client(live, enabled=False), auth).json()
    assert body["degraded"] is False and live.queries == []


def test_later_pages_never_trigger_a_web_search(make_client, auth, session, kitchen):
    live = FakeLive()
    search(make_client(live, thin_threshold=5), auth, offset=20)
    assert live.queries == []


def test_a_repeat_search_skips_the_web_and_uses_stored_results(make_client, auth, session, kitchen):
    live = FakeLive(LiveOutcome(True, 0))
    client = make_client(live, thin_threshold=5)
    search(client, auth)
    body = search(client, auth, names=("pasta", "garlic")).json()  # same set, other order
    assert len(live.queries) == 1
    assert body["degraded"] is False


def test_a_failed_web_search_is_not_remembered(make_client, auth, session, kitchen):
    live = FakeLive(LiveOutcome(False, 0, "rate limited"))
    client = make_client(live, thin_threshold=5)
    search(client, auth)
    search(client, auth)
    assert len(live.queries) == 2


def test_a_different_ingredient_set_searches_the_web_again(make_client, auth, session, kitchen):
    live = FakeLive(LiveOutcome(True, 0))
    client = make_client(live, thin_threshold=5)
    search(client, auth, names=("garlic", "pasta"))
    search(client, auth, names=("garlic", "basil"))
    assert len(live.queries) == 2


def test_cache_hours_zero_turns_the_memory_off(make_client, auth, session, kitchen):
    live = FakeLive(LiveOutcome(True, 0))
    client = make_client(live, thin_threshold=5, cache_hours=0)
    search(client, auth)
    search(client, auth)
    assert len(live.queries) == 2
