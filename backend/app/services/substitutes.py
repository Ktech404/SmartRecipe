"""Suggest what the user already owns that could stand in for a missing ingredient.

Pure Python, no database. Suggestions are advice only: they never change a
recipe's score (the scoring rules in matching.py decide that).

An owned ingredient is offered as a substitute when it shares a parent with the
missing one: owning "cheddar cheese" for a recipe that wants "mozzarella cheese".
Ingredients with no parent have no relatives, so they get no suggestions.
"""

from collections.abc import Collection, Mapping


def substitutes_for(
    ingredient_id: int,
    owned: Collection[int],
    parents: Mapping[int, int | None],
    names: Mapping[int, str],
) -> list[str]:
    """Names of owned ingredients that share a parent with this one, A to Z."""
    parent = parents.get(ingredient_id)
    if parent is None:
        return []
    found = {
        names[owned_id]
        for owned_id in owned
        if owned_id != ingredient_id and parents.get(owned_id) == parent and owned_id in names
    }
    return sorted(found)
