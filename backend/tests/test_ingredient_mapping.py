from pathlib import Path

import pytest

from app.providers.base import RawRecipe
from app.services.ingredient_mapping import (
    map_ingredient_line,
    map_recipe,
    parse_quantity_and_unit,
)
from app.services.normalization import build_lookup, load_seed_lookup

NAMES = ["garlic", "pasta", "salt", "black pepper", "olive oil", "chicken breast",
         "egg", "rice", "onion", "butter", "chicken thigh", "ginger", "lime"]
SYNONYMS = {"eggs": "egg", "pepper": "black pepper"}
LOOKUP = build_lookup(NAMES, SYNONYMS)


def _recipe(*lines):
    return RawRecipe(source_url="https://example.com/r", title="T", ingredient_lines=tuple(lines))


# ---- quantity and unit --------------------------------------------------------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("2 cloves garlic, minced", (2.0, "clove")),
        ("1 1/2 cups rice", (1.5, "cup")),
        ("1/2 tsp salt", (0.5, "tsp")),
        ("500g chicken breast", (500.0, "g")),
        ("2 tablespoons olive oil", (2.0, "tbsp")),
        ("1 lb chicken breast", (1.0, "lb")),
        ("2 pounds chicken breast", (2.0, "lb")),
        ("2-3 large eggs", (2.0, None)),
        ("3 eggs", (3.0, None)),
        ("½ cup rice", (0.5, "cup")),
        ("Salt to taste", (None, None)),
        ("garlic", (None, None)),
    ],
)
def test_quantity_and_unit(line, expected):
    assert parse_quantity_and_unit(line) == expected


# ---- one line -----------------------------------------------------------------


def test_simple_line_is_mapped_with_quantity_and_unit():
    [item] = map_ingredient_line("2 cloves garlic, minced", LOOKUP)
    assert (item.name, item.quantity, item.unit) == ("garlic", 2.0, "clove")
    assert item.line == "2 cloves garlic, minced" and item.is_optional is False


def test_synonym_maps_to_the_canonical_name():
    [item] = map_ingredient_line("3 eggs", LOOKUP)
    assert item.name == "egg"


def test_optional_is_detected():
    [item] = map_ingredient_line("1 tbsp butter (optional)", LOOKUP)
    assert item.name == "butter" and item.is_optional is True


def test_salt_and_pepper_becomes_two_ingredients():
    items = map_ingredient_line("Salt and pepper to taste", LOOKUP)
    assert [i.name for i in items] == ["salt", "black pepper"]
    assert all(i.quantity is None for i in items)


@pytest.mark.parametrize(
    "line", ["Salt to taste", "salt, to taste", "Salt as needed", "olive oil for frying"]
)
def test_serving_notes_do_not_block_recognition(line):
    [item] = map_ingredient_line(line, LOOKUP)
    assert item.name in ("salt", "olive oil")


@pytest.mark.parametrize(
    "line, expected",
    [
        ("1 1/2 lbs boneless, skinless chicken thighs", "chicken thigh"),
        ("1 cup uncooked rice", "rice"),
        ("1 inch piece fresh ginger, grated", "ginger"),
        ("2-inch knob of ginger", "ginger"),
        ("juice of 1 lime", "lime"),
        ("zest of a lime", "lime"),
    ],
)
def test_common_recipe_wording_is_understood(line, expected):
    [item] = map_ingredient_line(line, LOOKUP)
    assert item.name == expected


def test_compound_line_needs_both_halves_known():
    assert map_ingredient_line("salt and unicorn dust", LOOKUP) is None


def test_unknown_line_returns_none():
    assert map_ingredient_line("1 cup dragon fruit", LOOKUP) is None


# ---- whole recipe -------------------------------------------------------------


def test_clean_recipe_is_ok():
    result = map_recipe(_recipe("200 g pasta", "2 cloves garlic", "salt"), LOOKUP)
    assert result.ok and result.reason is None
    assert [i.name for i in result.ingredients] == ["pasta", "garlic", "salt"]
    assert result.unrecognized == ()


def test_one_unrecognized_line_rejects_the_recipe_by_default():
    result = map_recipe(_recipe("200 g pasta", "2 cloves garlic", "1 cup dragon fruit"), LOOKUP)
    assert not result.ok
    assert result.unrecognized == ("1 cup dragon fruit",)
    assert "unrecognized" in result.reason
    assert len(result.ingredients) == 2  # the good ones are still reported


def test_limit_can_be_loosened():
    lines = ("200 g pasta", "2 cloves garlic", "1 cup dragon fruit")
    assert map_recipe(_recipe(*lines), LOOKUP, max_unrecognized=1).ok


def test_section_headers_and_blank_lines_are_ignored():
    result = map_recipe(_recipe("For the sauce:", "", "  ", "2 cloves garlic", "salt"), LOOKUP)
    assert result.ok and result.unrecognized == ()


def test_duplicate_ingredients_are_listed_once_keeping_the_first():
    result = map_recipe(_recipe("1 tsp salt", "2 cloves garlic", "salt, to taste"), LOOKUP)
    assert [i.name for i in result.ingredients] == ["salt", "garlic"]
    assert result.ingredients[0].quantity == 1.0


def test_too_few_ingredients_is_rejected():
    result = map_recipe(_recipe("2 cloves garlic"), LOOKUP)
    assert not result.ok and "only 1" in result.reason
    assert map_recipe(_recipe("2 cloves garlic"), LOOKUP, min_ingredients=1).ok


def test_no_ingredient_lines_is_rejected():
    result = map_recipe(_recipe(), LOOKUP)
    assert not result.ok and "no ingredient lines" in result.reason


# ---- with the real vocabulary (arrives with SCRUM-38) -------------------------

SEED = Path(__file__).resolve().parent.parent / "seed"


@pytest.mark.skipif(
    not (SEED / "ingredients.csv").exists(), reason="seed CSVs arrive with SCRUM-38"
)
def test_realistic_recipe_with_the_seed_vocabulary():
    lookup = load_seed_lookup(SEED)
    lines = (
        "2 lbs boneless skinless chicken breasts",
        "3 cloves garlic, minced",
        "1 cup rice",
        "2 tablespoons olive oil",
        "Salt and pepper to taste",
    )
    result = map_recipe(_recipe(*lines), lookup)
    assert result.ok, (result.reason, result.unrecognized)
    names = [i.name for i in result.ingredients]
    assert {"chicken breast", "garlic", "olive oil", "salt"} <= set(names)


# ---- real recipe-page wording, against the real vocabulary ---------------------
# These lines came from a live ingestion run that rejected every recipe.


@pytest.fixture(scope="module")
def seed_lookup():
    return load_seed_lookup(SEED)


@pytest.mark.parametrize(
    "line, expected",
    [
        ("6 skinless, bone-in chicken thighs", "chicken thigh"),
        ("1 teaspoon sweet or smoked paprika", "smoked paprika"),
        ("4 large cloves garlic (minced)", "garlic"),
        ("11/2 cups long grain white rice", "rice"),
        ("11/2 cups low-sodium, fat free chicken broth", "chicken broth"),
        ("11/2 cups hot water", "water"),
        ("1/2 teaspoon dried Italian Seasoning", "italian seasoning"),
        ("2 Tbsp. and 2 tsp. vegetable oil, divided", "vegetable oil"),
        ("2/3 c. green onion, chopped", "green onion"),
        ("4 c. cooked brown rice, cooled", "brown rice"),
        ("2 Tbsp. and 2 tsp. low sodium soy sauce", "soy sauce"),
        ("1-1/3 c. frozen green peas, thawed", "pea"),
        ("1 can bamboo shoots, drained", "bamboo shoot"),
        ("One cucumber", "cucumber"),
        ("1 chicken cube", "chicken bouillon"),
        ("1/2 bulb of garlic", "garlic"),
        ("Light soy sauce", "soy sauce"),
        ("3 tablespoons grapeseed or other neutral oil, divided", "vegetable oil"),
        ("4 cups cooked and chilled long-grain white rice, preferably jasmine rice (see headnote)", "rice"),
        ("1 teaspoon ground cinnamon", "cinnamon"),
        ("1/2 cup unsalted butter", "butter"),
    ],
)
def test_real_page_wording_is_recognized(seed_lookup, line, expected):
    items = map_ingredient_line(line, seed_lookup)
    assert items is not None, line
    assert items[0].name == expected


@pytest.mark.parametrize(
    "line, quantity, unit",
    [
        ("11/2 cups hot water", 1.5, "cup"),
        ("13/4 cups flour", 1.75, "cup"),
        ("1-1/3 c. frozen green peas", 1 + 1 / 3, "cup"),
        ("2/3 c. green onion", 2 / 3, "cup"),
        ("2 Tbsp. and 2 tsp. vegetable oil", 2.0, "tbsp"),
        ("One cucumber", 1.0, None),
        ("1½ cups rice", 1.5, "cup"),
        ("10/2 cups rice", 5.0, "cup"),  # a real 10/2 is left alone
    ],
)
def test_quantity_wording_variants(line, quantity, unit):
    q, u = parse_quantity_and_unit(line)
    assert q == pytest.approx(quantity) and u == unit


def test_lines_that_bundle_several_ingredients_are_still_rejected(seed_lookup):
    for line in (
        "1/2 teaspoon garlic powder salt and freshly ground black pepper (to taste)",
        "1/2 teaspoon dried oregano chopped fresh parsley (for garnish)",
        "1 dragon fruit",
    ):
        assert map_ingredient_line(line, seed_lookup) is None


def test_exact_vocabulary_wins_over_the_soft_word_fallback(seed_lookup):
    # "ground beef" is its own ingredient, so "ground" must not be stripped from it
    [item] = map_ingredient_line("1 lb ground beef", seed_lookup)
    assert item.name == "ground beef"


@pytest.mark.parametrize(
    "line, expected",
    [
        # lines taken from a real 20-search ingestion run that were rejected before
        ("4 Tbsp. oil", "vegetable oil"),
        ("1 cup corn kernels, fresh or frozen", "corn"),
        ("1/2 cup dry white wine", "white wine"),
        ("1/4 cup sliced black olives", "olive"),
        ("1/2 cup real mayonnaise", "mayonnaise"),
        ("1 tsp of crushed red pepper flakes", "red pepper flake"),
        ("6 fresh basil leaves, chopped", "basil"),
        ("1 celery stalk (diced into 1/4-1/2-inch pieces)", "celery"),
        ("lemon slices, for garnish (optional)", "lemon"),
        ("1 pound salmon fillet", "salmon"),
        ("1 pound fresh salmon cut into 2 fillets", "salmon"),
        ("4 cups small broccoli florets", "broccoli"),
        ("14 oz block of extra-firm tofu", "tofu"),
        ("one 14-oz. block extra-firm tofu", "tofu"),
        ("1 pkg (16 oz) firm tofu, drained", "tofu"),
        ("1 tsp. corn starch", "cornstarch"),
        ("2 cups (475 ml) apple juice", "apple juice"),
        ("1 teaspoon Chinese rice wine", "rice wine"),
        ("1 loaf French bread", "bread"),
        ("1 15 ounce can black beans, rinsed", "black bean"),
        ("1 can (15.5 oz.) can black beans, drained", "black bean"),
        ("1/2 cup good quality olive oil", "olive oil"),
        ("Flat-leaf parsley", "parsley"),
        ("1 teaspoon dried thyme leaves", "thyme"),
        ("1 tin cherry tomatoes", "cherry tomato"),
        ("2 tsp Sea Salt Flakes", "sea salt"),
        ("1 lb. cremini or baby bella mushrooms", "mushroom"),
        ("1 small container mascarpone cheese (8 oz)", "mascarpone cheese"),
        ("1 cup dry brown lentils", "lentil"),
        ("2 ears fresh corn, kernels removed from the cob", "corn"),
        ("1 pound thin asparagus", "asparagus"),
        ("6 thinly sliced cold boiled potatoes", "potato"),
        ("3 tablespoons butter - divided use", "butter"),
        ("2 tbsp extra virgin olive oil + extra", "olive oil"),
        ("1 tablespoon plus 2 teaspoons olive oil", "olive oil"),
        ("3 tblsp butter", "butter"),
        ("5 or 6 large sweet potatoes, peeled", "sweet potato"),
        ("grape seed oil for the pan", "vegetable oil"),
        ("1 tsp. fresh minced ginger. You can use dried if needed", "ginger"),
        ("1 15-ounce jar of salsa", "salsa"),
    ],
)
def test_wording_seen_in_a_real_ingestion_run(seed_lookup, line, expected):
    items = map_ingredient_line(line, seed_lookup)
    assert items is not None, line
    assert items[0].name == expected


def test_package_size_is_dropped_but_the_count_is_kept(seed_lookup):
    [item] = map_ingredient_line("2 10-ounce cans black beans", seed_lookup)
    assert item.name == "black bean"
    assert item.quantity == 2.0 and item.unit == "can"
    [item] = map_ingredient_line("14 oz block of extra-firm tofu", seed_lookup)
    assert item.quantity == 14.0 and item.unit == "oz"


def test_salt_and_pepper_variants(seed_lookup):
    names = {i.name for i in map_ingredient_line("Coarse salt and ground pepper", seed_lookup)}
    assert names == {"salt", "black pepper"}
    assert map_ingredient_line("2 eggs per potato plus 1 extra", seed_lookup) is None


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Pinch of salt", "salt"),
        ("Dash of black pepper", "black pepper"),
        ("Pinch red pepper flakes", "red pepper flake"),
        ("1 lb (454 g) peeled and deveined shrimp", "shrimp"),
        ("2 cans (14 1/2 ounces each) diced tomatoes in juice", "tomato"),
        ("1 tsp cumin powder,", "cumin"),
        ("1 cup grated low fat Monterrey Jack cheese", "monterey jack cheese"),
        ("1 large brown onion, chopped", "onion"),
        ("1/4 cup low-sodium chicken bone broth", "chicken broth"),
        ("1 pound dry linguine pasta", "pasta"),
    ],
)
def test_second_batch_of_real_wording(seed_lookup, line, expected):
    items = map_ingredient_line(line, seed_lookup)
    assert items is not None, line
    assert items[0].name == expected


def test_salt_ampersand_pepper(seed_lookup):
    names = {i.name for i in map_ingredient_line("Salt & pepper", seed_lookup)}
    assert names == {"salt", "black pepper"}


@pytest.mark.parametrize(
    "line, expected",
    [
        ("-1 tsp salt", "salt"),
        ("-2 large carrots, fine diced", "carrot"),
        ("-2 Tbsp paprika", "paprika"),
        ("-1 small can tomato paste", "tomato paste"),
        ("-1 white onion, sliced", "onion"),
        ("• 2 cloves garlic", "garlic"),
        ("4 4-ounce boneless pork loin chops (about 1 inch thick)", "pork chop"),
        ("5 tbsp. panko breadcrumbs", "panko"),
        ("2 tbsp. honey mustard", "mustard"),
    ],
)
def test_list_bullets_and_per_item_sizes(seed_lookup, line, expected):
    items = map_ingredient_line(line, seed_lookup)
    assert items is not None, line
    assert items[0].name == expected


def test_a_leading_dash_does_not_turn_a_quantity_negative_or_lose_the_unit(seed_lookup):
    [item] = map_ingredient_line("-2 Tbsp paprika", seed_lookup)
    assert item.quantity == 2.0 and item.unit == "tbsp"


# ---- wording found in real recipe pages (SCRUM-37) -----------------------------


@pytest.mark.skipif(not (SEED / "ingredients.csv").exists(), reason="seed CSVs missing")
@pytest.mark.parametrize(
    "line, name, quantity, unit",
    [
        ("1 cup crumbled feta cheese", "feta cheese", 1.0, "cup"),
        ("4 oz feta cheese crumbles", "feta cheese", 4.0, "oz"),
        ("2 ripe tomatoes", "tomato", 2.0, None),
        ("1 lb scrubbed potatoes", "potato", 1.0, "lb"),
        ("2 yellow-fleshed potatoes", "potato", 2.0, None),
        ("1 cup sushi rice", "rice", 1.0, "cup"),
        ("1 cup Japanese short grain rice", "rice", 1.0, "cup"),
        ("2 cups pre-cooked rice", "rice", 2.0, "cup"),
        ("1 cup hot cooked rice", "rice", 1.0, "cup"),
        ("8 oz angel hair pasta", "pasta", 8.0, "oz"),
        ("8 oz whole-wheat spaghetti", "spaghetti", 8.0, "oz"),
        ("1 lb turkey mince", "ground turkey", 1.0, "lb"),
        ("4 baby cremini mushrooms", "mushroom", 4.0, None),
        ("14 oz super firm tofu", "tofu", 14.0, "oz"),
        ("2 tbsp white vinegar", "white vinegar", 2.0, "tbsp"),
        ("1 sheet nori seaweed", "nori", 1.0, None),
        ("8 egg roll wrappers", "egg roll wrapper", 8.0, None),
        ("2 lb pork butt or shoulder", "pork shoulder", 2.0, "lb"),
        ("4 oz whipped cream cheese", "cream cheese", 4.0, "oz"),
        ("1 packet taco seasoning", "taco seasoning", 1.0, "package"),
        ("1 minced seeded jalapeno", "jalapeno pepper", 1.0, None),
        ("1 lb shelled and deveined shrimp", "shrimp", 1.0, "lb"),
        ("3 large garlic cloves peeled and chopped", "garlic", 3.0, None),
        ("1/2 head broccoli, cut into small florets", "broccoli", 0.5, None),
        ("4 skin-on salmon fillets", "salmon", 4.0, None),
        ("1 tsp garlic salt", "garlic salt", 1.0, "tsp"),
        ("1 tbs parsley flakes", "parsley", 1.0, "tbsp"),
        ("1 red chilli, thinly sliced", "chili pepper", 1.0, None),
        ("40 g of wheat flour", "all purpose flour", 40.0, "g"),
        ("2 cups cooked chicken", "chicken breast", 2.0, "cup"),
    ],
)
def test_real_page_wording_maps_to_one_ingredient(line, name, quantity, unit):
    [item] = map_ingredient_line(line, load_seed_lookup(SEED))
    assert (item.name, item.quantity, item.unit) == (name, quantity, unit)


@pytest.mark.skipif(not (SEED / "ingredients.csv").exists(), reason="seed CSVs missing")
def test_a_plain_chicken_search_resolves_to_chicken_breast():
    from app.services.normalization import resolve_ingredient

    assert resolve_ingredient("chicken", load_seed_lookup(SEED)) == "chicken breast"


@pytest.mark.skipif(not (SEED / "ingredients.csv").exists(), reason="seed CSVs missing")
def test_specific_names_are_not_swallowed_by_the_new_soft_words():
    lookup = load_seed_lookup(SEED)
    for line, name in [("1 cup hot sauce", "hot sauce"), ("2 tbsp whole wheat flour", "whole wheat flour"),
                       ("1 chicken breast", "chicken breast"), ("1 tsp garlic powder", "garlic powder")]:
        result = map_ingredient_line(line, lookup)
        if result is not None:  # skip a name the seed does not have
            assert result[0].name == name
