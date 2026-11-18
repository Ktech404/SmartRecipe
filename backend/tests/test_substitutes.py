"""Substitute suggestions: pure functions, no database."""

from app.services.substitutes import substitutes_for

# cheese > (cheddar, mozzarella, parmesan); garlic and pasta have no parent
PARENTS = {1: None, 2: 1, 3: 1, 4: 1, 5: None, 6: None}
NAMES = {1: "cheese", 2: "cheddar cheese", 3: "mozzarella cheese", 4: "parmesan", 5: "garlic", 6: "pasta"}


def test_an_owned_sibling_is_suggested():
    assert substitutes_for(3, {2, 6}, PARENTS, NAMES) == ["cheddar cheese"]


def test_several_siblings_are_listed_in_order():
    assert substitutes_for(3, {4, 2}, PARENTS, NAMES) == ["cheddar cheese", "parmesan"]


def test_the_ingredient_itself_is_never_its_own_substitute():
    assert substitutes_for(3, {3, 2}, PARENTS, NAMES) == ["cheddar cheese"]


def test_unrelated_owned_ingredients_are_not_suggested():
    assert substitutes_for(3, {5, 6}, PARENTS, NAMES) == []


def test_an_ingredient_with_no_parent_has_no_suggestions():
    assert substitutes_for(5, {6}, PARENTS, NAMES) == []
    assert substitutes_for(99, {6}, PARENTS, NAMES) == []
