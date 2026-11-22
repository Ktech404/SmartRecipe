"""The pure steps of the stored search: finding related ids and ranking. No database."""

from app.schemas.search import MatchTier
from app.services.matching import Candidate, RecipeLine
from app.services.recipe_search import LOW_MIN_SCORE, rank_stored, related_ids
from app.services.restrictions import Restrictions

# 1 cheese > (2 cheddar, 3 mozzarella); 2 cheddar > 7 sharp cheddar; 4 pasta; 5 garlic; 6 peanut
PARENTS = {1: None, 2: 1, 3: 1, 7: 2, 4: None, 5: None, 6: None}


def line(ingredient_id, name="x", **kw):
    return RecipeLine(ingredient_id=ingredient_id, name=name, **kw)


def recipe(recipe_id, title, *ids):
    return Candidate(recipe_id, title, tuple(line(i, f"i{i}") for i in ids))


def test_related_ids_include_owned_more_general_and_more_specific():
    assert related_ids({2}, PARENTS) == {1, 2, 7}
    assert related_ids({4}, PARENTS) == {4}
    assert related_ids({1}, PARENTS) == {1, 2, 3, 7}


def test_related_ids_do_not_include_siblings():
    assert 3 not in related_ids({2}, PARENTS)


def test_related_ids_survive_a_loop_in_bad_data():
    assert related_ids({1}, {1: 2, 2: 1}) == {1, 2}


def test_recipes_are_ranked_best_first_with_tiers():
    candidates = [
        recipe(1, "Half", 4, 6),
        recipe(2, "All", 4, 5),
    ]
    matches = rank_stored(candidates, {4, 5}, PARENTS)
    assert [m.title for m in matches] == ["All", "Half"]
    assert [m.tier for m in matches] == [MatchTier.BEST, MatchTier.PARTIAL]


def test_very_weak_matches_are_dropped():
    weak = recipe(1, "Weak", 4, 5, 6, 3, 2)  # owns only pasta: 1 of 5
    assert rank_stored([weak], {4}, PARENTS) == []
    assert LOW_MIN_SCORE == 0.25


def test_a_match_exactly_at_the_cutoff_is_kept():
    assert len(rank_stored([recipe(1, "Quarter", 4, 5, 6, 3)], {4}, PARENTS)) == 1


def test_unsafe_recipes_are_removed_before_ranking():
    peanut = recipe(1, "Peanut Pasta", 4, 6)
    plain = recipe(2, "Plain Pasta", 4, 5)
    restrictions = Restrictions(allergies=frozenset({6}))
    matches = rank_stored([peanut, plain], {4, 5, 6}, PARENTS, restrictions)
    assert [m.title for m in matches] == ["Plain Pasta"]


def test_allergen_groups_use_the_ingredient_groups_given():
    peanut = recipe(1, "Peanut Pasta", 4, 6)
    restrictions = Restrictions(allergen_groups=frozenset({9}))
    assert rank_stored([peanut], {4}, PARENTS, restrictions, {6: {9}}) == []
    assert len(rank_stored([peanut], {4}, PARENTS, restrictions, {})) == 1
