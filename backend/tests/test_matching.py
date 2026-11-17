from app.schemas.search import MatchTier
from app.services.matching import (Candidate, RecipeLine, ancestors,
                                   rank_matches, score_recipe)

# Ingredient ids used below
BEEF, SIRLOIN, FLANK, GARLIC, RICE, SALT, PEPPER = 1, 2, 3, 4, 5, 6, 7
PARENTS = {SIRLOIN: BEEF, FLANK: BEEF}


def line(ingredient_id, name="x", **kwargs):
    return RecipeLine(ingredient_id=ingredient_id, name=name, **kwargs)


def recipe(*lines, recipe_id=1, title="Dish"):
    return Candidate(recipe_id=recipe_id, title=title, lines=tuple(lines))


def test_everything_covered_is_a_best_match():
    m = score_recipe(recipe(line(GARLIC), line(RICE)), {GARLIC, RICE}, {})
    assert m.score == 1.0
    assert m.tier == MatchTier.BEST
    assert m.missing == ()


def test_half_covered_is_partial():
    r = recipe(line(GARLIC), line(RICE), line(BEEF), line(SALT + 10))
    m = score_recipe(r, {GARLIC, RICE}, {})
    assert m.score == 0.5
    assert m.tier == MatchTier.PARTIAL


def test_one_in_four_is_low():
    r = recipe(line(GARLIC), line(RICE), line(BEEF), line(SALT + 10))
    m = score_recipe(r, {GARLIC}, {})
    assert m.score == 0.25
    assert m.tier == MatchTier.LOW


def test_staples_and_optional_lines_are_ignored():
    r = recipe(line(GARLIC), line(SALT, is_staple=True),
               line(PEPPER, is_optional=True))
    m = score_recipe(r, {GARLIC}, {})
    assert m.score == 1.0
    assert m.missing == ()


def test_owning_the_general_ingredient_covers_the_specific_one():
    m = score_recipe(recipe(line(SIRLOIN)), {BEEF}, PARENTS)
    assert m.score == 1.0


def test_owning_the_specific_ingredient_covers_the_general_one():
    m = score_recipe(recipe(line(BEEF)), {SIRLOIN}, PARENTS)
    assert m.score == 1.0


def test_siblings_do_not_cover_each_other():
    m = score_recipe(recipe(line(SIRLOIN, "sirloin steak")), {FLANK}, PARENTS)
    assert m.score == 0.0
    assert [x.name for x in m.missing] == ["sirloin steak"]


def test_missing_lists_only_what_is_needed():
    r = recipe(line(GARLIC, "garlic"), line(RICE, "rice"), line(BEEF, "beef"))
    m = score_recipe(r, {GARLIC}, {})
    assert {x.name for x in m.missing} == {"rice", "beef"}


def test_duplicate_lines_count_once():
    m = score_recipe(recipe(line(GARLIC), line(GARLIC), line(RICE)), {GARLIC}, {})
    assert m.score == 0.5


def test_recipe_with_nothing_to_score_gets_zero():
    m = score_recipe(recipe(line(SALT, is_staple=True)), {GARLIC}, {})
    assert m.score == 0.0


def test_a_loop_in_the_hierarchy_does_not_hang():
    loop = {1: 2, 2: 1}
    assert ancestors(1, loop) == {2}
    assert score_recipe(recipe(line(1)), {2}, loop).score == 1.0


def test_thresholds_can_be_overridden():
    r = recipe(line(GARLIC), line(RICE))
    m = score_recipe(r, {GARLIC}, {}, best_min=0.4)
    assert m.tier == MatchTier.BEST


def test_rank_drops_zero_scores_and_sorts_best_first():
    perfect = recipe(line(GARLIC), recipe_id=1, title="Perfect")
    partial = recipe(line(GARLIC), line(RICE), recipe_id=2, title="Partial")
    nothing = recipe(line(BEEF), recipe_id=3, title="Nothing")
    ranked = rank_matches([partial, nothing, perfect], {GARLIC}, {})
    assert [m.title for m in ranked] == ["Perfect", "Partial"]


def test_rank_breaks_ties_by_fewer_missing_then_title():
    a = recipe(line(GARLIC), line(RICE), line(BEEF), line(SALT + 10),
               recipe_id=1, title="A")           # 1 of 4
    b = recipe(line(GARLIC), line(RICE), recipe_id=2, title="B")  # 1 of 2
    c = recipe(line(GARLIC), line(RICE), recipe_id=3, title="C")  # 1 of 2
    ranked = rank_matches([c, a, b], {GARLIC}, {})
    assert [m.title for m in ranked] == ["B", "C", "A"]