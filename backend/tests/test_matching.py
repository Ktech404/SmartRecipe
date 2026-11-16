import pytest

from app.services.matching import (
    BEST,
    LOW,
    PARTIAL,
    IngredientGraph,
    IngredientNode,
    MatchConfig,
    OwnedMatcher,
    RecipeLine,
    rank_key,
    score_recipe,
)

# ids: 1 cheese > (2 cheddar, 3 mozzarella, 4 feta); 5 chicken > (6 chicken breast);
# 7 garlic; 8 pasta; 9 salt (staple); 10 basil; 11 tomato
NODES = [
    IngredientNode(1, "cheese"),
    IngredientNode(2, "cheddar cheese", 1),
    IngredientNode(3, "mozzarella cheese", 1),
    IngredientNode(4, "feta cheese", 1),
    IngredientNode(5, "chicken"),
    IngredientNode(6, "chicken breast", 5),
    IngredientNode(7, "garlic"),
    IngredientNode(8, "pasta"),
    IngredientNode(9, "salt", None, True),
    IngredientNode(10, "basil"),
    IngredientNode(11, "tomato"),
]


@pytest.fixture()
def graph():
    return IngredientGraph(NODES)


def line(ingredient_id, **kw):
    name = next(n.name for n in NODES if n.ingredient_id == ingredient_id)
    staple = next(n.is_staple for n in NODES if n.ingredient_id == ingredient_id)
    return RecipeLine(ingredient_id, name, is_staple=staple, **kw)


def match(graph, owned, lines, config=MatchConfig()):
    return score_recipe(lines, OwnedMatcher(graph, owned), config)


# ---- graph -----------------------------------------------------------------


def test_graph_relationships(graph):
    assert graph.ancestors(2) == {1}
    assert graph.descendants(1) == {2, 3, 4}
    assert graph.siblings(2) == {3, 4}
    assert graph.siblings(1) == set()
    assert graph.ancestors(7) == set()


def test_graph_handles_deep_trees_and_unknown_ids():
    g = IngredientGraph([IngredientNode(1, "a"), IngredientNode(2, "b", 1), IngredientNode(3, "c", 2)])
    assert g.ancestors(3) == {1, 2}
    assert g.descendants(1) == {2, 3}
    assert g.ancestors(99) == set() and g.descendants(99) == set()


def test_graph_survives_a_loop_in_the_data():
    g = IngredientGraph([IngredientNode(1, "a", 2), IngredientNode(2, "b", 1)])
    assert g.ancestors(1) == {2}
    assert 1 not in g.descendants(1)


def test_parent_that_is_not_in_the_table_is_ignored():
    g = IngredientGraph([IngredientNode(1, "a", 42)])
    assert g.parent(1) is None and g.siblings(1) == set()


# ---- tiers -----------------------------------------------------------------


def test_everything_owned_is_best(graph):
    m = match(graph, {7, 8}, [line(7), line(8)])
    assert m.tier == BEST and m.score == 1.0 and m.missing == ()


def test_one_of_four_missing_is_partial(graph):
    m = match(graph, {7, 8, 10}, [line(7), line(8), line(10), line(11)])
    assert m.tier == PARTIAL and m.score == pytest.approx(0.75)
    assert [x.name for x in m.missing] == ["tomato"]


def test_two_of_four_missing_is_still_partial_at_the_boundary(graph):
    m = match(graph, {7, 8}, [line(7), line(8), line(10), line(11)])
    assert m.tier == PARTIAL and m.score == pytest.approx(0.5)


def test_one_of_three_is_low(graph):
    m = match(graph, {7}, [line(7), line(8), line(10)])
    assert m.tier == LOW and m.score == pytest.approx(1 / 3)


def test_below_the_lowest_tier_is_dropped(graph):
    assert match(graph, {7}, [line(7), line(8), line(10), line(11), line(2)]) is None
    assert match(graph, {7}, [line(8), line(10)]) is None  # nothing in common


def test_custom_thresholds(graph):
    config = MatchConfig(best_min=0.8, partial_min=0.5, low_min=0.1)
    m = match(graph, {7, 8, 10}, [line(7), line(8), line(10), line(11)], config)
    assert m.tier == "partial"  # 0.75 is below the custom best_min of 0.8
    m = match(graph, {7, 8, 10, 11}, [line(7), line(8), line(10), line(11)], config)
    assert m.tier == BEST


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(low_min=0.6, partial_min=0.5),
        dict(partial_min=0.9, best_min=0.8),
        dict(best_min=1.5),
        dict(low_min=0),
        dict(substitute_credit=1.0),
    ],
)
def test_bad_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        MatchConfig(**kwargs)


# ---- what counts as covered -------------------------------------------------


def test_staples_and_optional_ingredients_are_ignored(graph):
    lines = [line(7), line(8), line(9), line(10, is_optional=True)]
    m = match(graph, {7, 8}, lines)
    assert m.tier == BEST and m.required == 2 and m.missing == ()


def test_staples_can_be_counted_when_configured(graph):
    m = match(graph, {7, 8}, [line(7), line(8), line(9)], MatchConfig(ignore_staples=False))
    assert m.required == 3 and m.score == pytest.approx(2 / 3)
    assert [x.name for x in m.missing] == ["salt"]


def test_a_recipe_of_only_staples_and_optionals_is_not_scored(graph):
    assert match(graph, {7}, [line(9), line(10, is_optional=True)]) is None
    assert match(graph, {7}, []) is None


def test_duplicate_lines_count_once(graph):
    m = match(graph, {7}, [line(7), line(7), line(8)])
    assert m.required == 2


def test_owning_a_specific_ingredient_covers_the_general_one(graph):
    # recipe wants "cheese"; user has cheddar
    m = match(graph, {2, 8}, [line(1), line(8)])
    assert m.tier == BEST and m.missing == ()


def test_owning_a_general_ingredient_gives_partial_credit_and_a_substitute(graph):
    # recipe wants cheddar; user only has "cheese"
    m = match(graph, {1, 8}, [line(2), line(8)])
    assert m.score == pytest.approx(0.75) and m.tier == PARTIAL
    [missing] = m.missing
    assert missing.name == "cheddar cheese" and missing.substitutes == ("cheese",)


def test_a_sibling_is_a_substitute(graph):
    # recipe wants mozzarella; user has cheddar
    m = match(graph, {2, 8}, [line(3), line(8)])
    assert m.score == pytest.approx(0.75)
    [missing] = m.missing
    assert missing.name == "mozzarella cheese" and missing.substitutes == ("cheddar cheese",)


def test_unrelated_ingredients_give_no_credit_and_no_substitutes(graph):
    m = match(graph, {7, 8}, [line(7), line(8), line(11)])
    [missing] = m.missing
    assert missing.substitutes == ()


def test_exact_match_beats_relative(graph):
    # owns cheddar and mozzarella; recipe wants mozzarella: fully covered, not missing
    m = match(graph, {2, 3}, [line(3), line(8)], MatchConfig(low_min=0.1, partial_min=0.2))
    assert [x.name for x in m.missing] == ["pasta"]


def test_without_any_hierarchy_only_exact_matches_count():
    g = IngredientGraph([IngredientNode(1, "a"), IngredientNode(2, "b")])
    m = score_recipe([RecipeLine(1, "a"), RecipeLine(2, "b")], OwnedMatcher(g, {1}))
    assert m.score == 0.5 and m.missing[0].substitutes == ()


def test_missing_line_keeps_quantity_and_unit(graph):
    m = match(graph, {7, 8, 10}, [line(7), line(8), line(10), line(11, quantity=2.0, unit="cup")])
    [missing] = m.missing
    assert missing.quantity == 2.0 and missing.unit == "cup" and missing.ingredient_id == 11


def test_candidate_ids_include_owned_ancestors_and_relatives(graph):
    matcher = OwnedMatcher(graph, {2})
    assert matcher.candidate_ids == {1, 2, 3, 4}
    assert matcher.full == {1, 2} and matcher.partial == {3, 4}


# ---- ranking ---------------------------------------------------------------


def test_ranking_orders_by_score_then_fewest_missing_then_id(graph):
    perfect = match(graph, {7, 8}, [line(7), line(8)])
    three_quarters = match(graph, {7, 8, 10}, [line(7), line(8), line(10), line(11)])
    ranked = sorted(
        [(30, three_quarters), (20, perfect), (10, perfect)],
        key=lambda item: rank_key(*item),
    )
    assert [recipe_id for recipe_id, _ in ranked] == [10, 20, 30]
