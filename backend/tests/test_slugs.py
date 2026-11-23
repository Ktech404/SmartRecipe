"""Recipe slugs (SCRUM-39). No database needed."""

import pytest

from app.services.slugs import make_slug, parse_slug_id, slugify


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Lemon Garlic Chicken", "lemon-garlic-chicken"),
        ("Lemon & Garlic Chicken!", "lemon-garlic-chicken"),
        ("  Mac   and  Cheese  ", "mac-and-cheese"),
        ("Crème brûlée", "creme-brulee"),
        ("Grandma's 5-Ingredient Soup", "grandma-s-5-ingredient-soup"),
        ("!!!", "recipe"),
        ("", "recipe"),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_long_titles_are_cut_at_a_word():
    slug = slugify("one pot creamy garlic chicken and rice with lemon and fresh herbs and parmesan")
    assert len(slug) <= 60
    assert not slug.endswith("-")
    assert "one-pot-creamy-garlic-chicken" in slug


def test_slug_ends_with_the_id():
    assert make_slug("Lemon Garlic Chicken", 12) == "lemon-garlic-chicken-12"


@pytest.mark.parametrize(
    "slug, expected",
    [
        ("lemon-garlic-chicken-12", 12),
        ("Lemon-Garlic-Chicken-12", 12),
        ("recipe-7", 7),
        ("7", 7),
        ("5-ingredient-soup-31", 31),
        ("  chicken-3  ", 3),
    ],
)
def test_parse_slug_id(slug, expected):
    assert parse_slug_id(slug) == expected


@pytest.mark.parametrize("slug", ["", "chicken", "chicken-", "chicken-12a", "chicken--", "12-chicken"])
def test_slugs_without_an_id_are_rejected(slug):
    assert parse_slug_id(slug) is None


@pytest.mark.parametrize("title", ["Lemon Garlic Chicken", "5-Ingredient Soup", "!!!", "Mac & Cheese 2"])
def test_round_trip(title):
    assert parse_slug_id(make_slug(title, 4321)) == 4321
