"""Stored-recipe search against the PostgreSQL test database.  (SCRUM-34)

Each test runs inside a rolled-back transaction (see conftest.py), so nothing
here leaks between tests.
"""

import pytest

from app.db.models import (
    AllergenGroup,
    Ingredient,
    IngredientAllergenGroup,
    IngredientSynonym,
    Recipe,
    RecipeIngredient,
    User,
    UserAllergenGroup,
    UserRestricted,
)
from app.services.recipe_search import (
    Restrictions,
    load_restrictions,
    resolve_ingredient_ids,
    search_stored_recipes,
)


@pytest.fixture()
def kitchen(session):
    """A small vocabulary: cheese > (cheddar, mozzarella), plus plain ingredients."""
    ids = {}

    def add(name, parent=None, staple=False):
        row = Ingredient(
            name=name,
            category="test",
            is_staple=staple,
            parent_ingredient_id=ids[parent] if parent else None,
        )
        session.add(row)
        session.flush()
        ids[name] = row.ingredient_id

    add("cheese")
    add("cheddar cheese", "cheese")
    add("mozzarella cheese", "cheese")
    for name in ["garlic", "pasta", "basil", "tomato", "peanut"]:
        add(name)
    add("salt", staple=True)
    return ids


def make_recipe(session, kitchen, title, lines, **fields):
    """lines: [(ingredient name, quantity, unit)] or [(name, quantity, unit, True)] for optional."""
    recipe = Recipe(title=title, source_url=f"https://example.com/{title.replace(' ', '-')}", **fields)
    session.add(recipe)
    session.flush()
    for line in lines:
        name, quantity, unit, *rest = line
        session.add(
            RecipeIngredient(
                recipe_id=recipe.recipe_id,
                ingredient_id=kitchen[name],
                quantity=quantity,
                unit=unit,
                is_optional=bool(rest and rest[0]),
            )
        )
    session.flush()
    return recipe


def owned(kitchen, *names):
    return [kitchen[n] for n in names]


def titles(result):
    return [r.title for r in result.results]


def test_results_are_tiered_and_ordered(session, kitchen):
    make_recipe(session, kitchen, "Garlic Pasta", [("garlic", 2, "clove"), ("pasta", 200, "g")])
    make_recipe(
        session, kitchen, "Tomato Pasta",
        [("tomato", 3, None), ("pasta", 200, "g"), ("garlic", 1, "clove"), ("basil", None, None)],
    )
    make_recipe(
        session, kitchen, "Big Dinner",
        [("tomato", 1, None), ("basil", 1, None), ("peanut", 1, None), ("pasta", 1, "g")],
    )

    result = search_stored_recipes(session, owned(kitchen, "garlic", "pasta"))

    assert titles(result) == ["Garlic Pasta", "Tomato Pasta", "Big Dinner"]
    assert [r.tier.value for r in result.results] == ["best", "partial", "low"]
    assert [r.match_score for r in result.results] == [1.0, 0.5, 0.25]
    assert result.total == 3


def test_missing_ingredients_are_listed_with_quantity_and_unit(session, kitchen):
    make_recipe(
        session, kitchen, "Garlic Tomato Pasta",
        [("garlic", 2, "clove"), ("pasta", 200, "g"), ("tomato", 2.5, "cup")],
    )
    [r] = search_stored_recipes(session, owned(kitchen, "garlic", "pasta")).results
    [missing] = r.missing_ingredients
    assert missing.name == "tomato"
    assert missing.ingredient_id == kitchen["tomato"]
    assert missing.quantity == 2.5 and missing.unit.value == "cup"


def test_staples_and_optional_ingredients_do_not_count(session, kitchen):
    make_recipe(
        session, kitchen, "Simple Pasta",
        [("pasta", 200, "g"), ("salt", 1, "tsp"), ("basil", None, None, True)],
    )
    [r] = search_stored_recipes(session, owned(kitchen, "pasta")).results
    assert r.tier.value == "best" and r.missing_ingredients == []


def test_recipes_with_nothing_in_common_are_not_returned(session, kitchen):
    make_recipe(session, kitchen, "Tomato Basil", [("tomato", 1, None), ("basil", 1, None)])
    result = search_stored_recipes(session, owned(kitchen, "garlic"))
    assert result.results == [] and result.total == 0


def test_no_owned_ingredients_returns_nothing(session, kitchen):
    make_recipe(session, kitchen, "Garlic Pasta", [("garlic", 2, "clove"), ("pasta", 200, "g")])
    assert search_stored_recipes(session, []).total == 0


def test_names_resolve_through_synonyms_and_unknown_names_are_reported(session, kitchen):
    session.add(IngredientSynonym(ingredient_id=kitchen["garlic"], alias="garlic cloves"))
    session.flush()
    resolved = resolve_ingredient_ids(session, ["Garlic cloves", "pasta", "dragon fruit"])
    assert resolved.ids == [kitchen["garlic"], kitchen["pasta"]]
    assert resolved.unknown == ["dragon fruit"]


def test_hierarchy_owning_cheddar_covers_a_recipe_that_wants_cheese(session, kitchen):
    make_recipe(session, kitchen, "Cheesy Pasta", [("cheese", 1, "cup"), ("pasta", 200, "g")])
    [r] = search_stored_recipes(session, owned(kitchen, "cheddar cheese", "pasta")).results
    assert r.tier.value == "best" and r.missing_ingredients == []


def test_hierarchy_a_sibling_is_offered_as_a_substitute(session, kitchen):
    make_recipe(session, kitchen, "Caprese Pasta", [("mozzarella cheese", 1, "cup"), ("pasta", 200, "g")])
    [r] = search_stored_recipes(session, owned(kitchen, "cheddar cheese", "pasta")).results
    assert r.tier.value == "partial" and r.match_score == 0.75
    [missing] = r.missing_ingredients
    assert missing.name == "mozzarella cheese" and missing.substitutes == ["cheddar cheese"]


def test_max_minutes_filters_but_keeps_recipes_without_a_time(session, kitchen):
    lines = [("garlic", 1, "clove"), ("pasta", 100, "g")]
    make_recipe(session, kitchen, "Quick", lines, total_minutes=20)
    make_recipe(session, kitchen, "Slow", lines, total_minutes=90)
    make_recipe(session, kitchen, "Unknown time", lines)
    result = search_stored_recipes(session, owned(kitchen, "garlic", "pasta"), max_minutes=30)
    assert sorted(titles(result)) == ["Quick", "Unknown time"]


def test_tools_filter_drops_recipes_that_need_a_missing_tool(session, kitchen):
    lines = [("garlic", 1, "clove"), ("pasta", 100, "g")]
    make_recipe(session, kitchen, "Oven bake", lines, tools=["oven", "baking dish"])
    make_recipe(session, kitchen, "Stovetop", lines, tools=["stove"])
    make_recipe(session, kitchen, "No tools listed", lines)
    mine = owned(kitchen, "garlic", "pasta")

    assert sorted(titles(search_stored_recipes(session, mine, tools=["Stove"]))) == [
        "No tools listed", "Stovetop"
    ]
    assert sorted(titles(search_stored_recipes(session, mine, tools=["oven", "baking dish", "stove"]))) == [
        "No tools listed", "Oven bake", "Stovetop"
    ]
    assert len(search_stored_recipes(session, mine).results) == 3  # no tools given: no filter


def test_an_allergy_excludes_recipes_even_when_they_match_well(session, kitchen):
    make_recipe(session, kitchen, "Peanut Pasta", [("pasta", 200, "g"), ("peanut", 30, "g")])
    make_recipe(session, kitchen, "Plain Pasta", [("pasta", 200, "g"), ("garlic", 1, "clove")])
    mine = owned(kitchen, "pasta", "peanut", "garlic")
    restrictions = Restrictions(ingredient_ids=frozenset({kitchen["peanut"]}))
    assert titles(search_stored_recipes(session, mine, restrictions=restrictions)) == ["Plain Pasta"]


def test_a_restricted_ingredient_also_excludes_what_is_below_it(session, kitchen):
    make_recipe(session, kitchen, "Cheddar Pasta", [("pasta", 200, "g"), ("cheddar cheese", 1, "cup")])
    make_recipe(session, kitchen, "Plain Pasta", [("pasta", 200, "g")])
    restrictions = Restrictions(ingredient_ids=frozenset({kitchen["cheese"]}))
    result = search_stored_recipes(session, owned(kitchen, "pasta"), restrictions=restrictions)
    assert titles(result) == ["Plain Pasta"]


def test_an_allergen_group_excludes_every_ingredient_in_it(session, kitchen):
    group = AllergenGroup(name="tree nuts and peanuts")
    session.add(group)
    session.flush()
    session.add(IngredientAllergenGroup(ingredient_id=kitchen["peanut"], allergen_group_id=group.allergen_group_id))
    session.flush()
    make_recipe(session, kitchen, "Peanut Pasta", [("pasta", 200, "g"), ("peanut", 30, "g")])
    make_recipe(session, kitchen, "Plain Pasta", [("pasta", 200, "g")])
    restrictions = Restrictions(allergen_group_ids=frozenset({group.allergen_group_id}))
    result = search_stored_recipes(session, owned(kitchen, "pasta"), restrictions=restrictions)
    assert titles(result) == ["Plain Pasta"]


def test_load_restrictions_reads_the_users_allergies_and_groups(session, kitchen):
    user = User(username="cook", email="cook@example.com", password_hash="x")
    group = AllergenGroup(name="shellfish")
    session.add_all([user, group])
    session.flush()
    session.add_all(
        [
            UserRestricted(user_id=user.user_id, ingredient_id=kitchen["peanut"], restriction_type="allergy"),
            UserAllergenGroup(user_id=user.user_id, allergen_group_id=group.allergen_group_id),
        ]
    )
    session.flush()
    r = load_restrictions(session, user.user_id)
    assert r.ingredient_ids == {kitchen["peanut"]}
    assert r.allergen_group_ids == {group.allergen_group_id}


def test_pagination_returns_a_page_and_the_full_total(session, kitchen):
    for i in range(5):
        make_recipe(session, kitchen, f"Pasta {i}", [("pasta", 100, "g"), ("garlic", 1, "clove")])
    mine = owned(kitchen, "pasta", "garlic")
    first = search_stored_recipes(session, mine, limit=2, offset=0)
    last = search_stored_recipes(session, mine, limit=2, offset=4)
    assert first.total == 5 and len(first.results) == 2
    assert len(last.results) == 1
    assert len({r.recipe_id for r in first.results} | {r.recipe_id for r in last.results}) == 3


def test_an_unrecognized_unit_is_left_out_not_an_error(session, kitchen):
    make_recipe(session, kitchen, "Odd Unit", [("garlic", 1, "clove"), ("pasta", 1, "handful"), ("tomato", 1, "bunchy")])
    [r] = search_stored_recipes(session, owned(kitchen, "garlic", "pasta")).results
    assert r.missing_ingredients[0].unit is None
