from app.services.matching import Candidate, RecipeLine
from app.services.restrictions import (Restrictions, filter_safe,
                                       find_violations, is_safe)

BEEF, SIRLOIN, FLANK, MILK, CHEESE, CHEDDAR, ALMOND, SALT = 1, 2, 3, 4, 5, 6, 7, 8
PARENTS = {SIRLOIN: BEEF, FLANK: BEEF, CHEDDAR: CHEESE}
DAIRY, TREE_NUTS = 100, 101
GROUPS = {MILK: {DAIRY}, CHEESE: {DAIRY}, ALMOND: {TREE_NUTS}}


def line(ingredient_id, name="x", **kwargs):
    return RecipeLine(ingredient_id=ingredient_id, name=name, **kwargs)


def safe(lines, **restrictions):
    r = Restrictions(**{k: frozenset(v) for k, v in restrictions.items()})
    return is_safe(lines, r, PARENTS, GROUPS)


def test_no_restrictions_means_everything_is_safe():
    assert safe([line(BEEF), line(MILK)])


def test_direct_allergy_blocks_the_recipe():
    assert not safe([line(MILK)], allergies={MILK})


def test_allergy_to_a_general_ingredient_blocks_the_specific_one():
    assert not safe([line(SIRLOIN)], allergies={BEEF})


def test_allergy_to_a_specific_ingredient_blocks_the_general_one():
    assert not safe([line(BEEF)], allergies={SIRLOIN})


def test_allergy_does_not_block_a_sibling():
    assert safe([line(SIRLOIN)], allergies={FLANK})


def test_an_allergen_in_an_optional_line_still_blocks():
    assert not safe([line(BEEF), line(MILK, is_optional=True)], allergies={MILK})


def test_an_allergen_in_a_staple_line_still_blocks():
    assert not safe([line(MILK, is_staple=True)], allergies={MILK})


def test_allergen_group_blocks_its_members():
    assert not safe([line(MILK)], allergen_groups={DAIRY})
    assert not safe([line(ALMOND)], allergen_groups={TREE_NUTS})


def test_allergen_group_is_inherited_from_the_parent_ingredient():
    # cheddar has no group of its own, but its parent (cheese) is dairy
    assert not safe([line(CHEDDAR)], allergen_groups={DAIRY})


def test_other_allergen_groups_do_not_block():
    assert safe([line(MILK)], allergen_groups={TREE_NUTS})


def test_blacklist_blocks_the_ingredient_and_its_children():
    assert not safe([line(BEEF)], blacklist={BEEF})
    assert not safe([line(SIRLOIN)], blacklist={BEEF})


def test_blacklisting_a_specific_ingredient_does_not_block_the_general_one():
    assert safe([line(BEEF)], blacklist={SIRLOIN})


def test_violations_explain_what_was_hit():
    r = Restrictions(allergies=frozenset({MILK}))
    found = find_violations([line(BEEF, "beef"), line(MILK, "milk")], r, PARENTS, GROUPS)
    assert [(v.name, v.kind) for v in found] == [("milk", "allergy")]


def test_one_ingredient_can_hit_several_rules():
    r = Restrictions(allergies=frozenset({MILK}), allergen_groups=frozenset({DAIRY}))
    kinds = {v.kind for v in find_violations([line(MILK, "milk")], r, PARENTS, GROUPS)}
    assert kinds == {"allergy", "allergen_group"}


def test_filter_safe_keeps_order_and_drops_unsafe_recipes():
    a = Candidate(1, "A", (line(BEEF),))
    b = Candidate(2, "B", (line(MILK),))
    c = Candidate(3, "C", (line(FLANK),))
    r = Restrictions(allergen_groups=frozenset({DAIRY}))
    assert [x.title for x in filter_safe([a, b, c], r, PARENTS, GROUPS)] == ["A", "C"]


def test_a_loop_in_the_hierarchy_does_not_hang():
    loop = {1: 2, 2: 1}
    r = Restrictions(allergies=frozenset({2}))
    assert not is_safe([line(1)], r, loop, {})