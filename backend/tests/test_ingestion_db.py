"""SqlRecipeRepository and a full ingestion run against the PostgreSQL test database."""

from sqlalchemy import select

from app.db.models import Ingredient, Recipe, RecipeIngredient
from app.providers.base import RawRecipe, RecipeSearchQuery
from app.providers.fake import FakeRecipeProvider
from app.services.ingestion import Ingestor, SqlRecipeRepository
from app.services.ingredient_mapping import load_lookup_from_db
from app.services.recipe_parser import GeminiRecipeParser, GenerateResult, ParsedRecipe
from app.services.recipe_storage import IngredientEntry, RecipeToStore


def _ingredients(session):
    for name in ["garlic", "pasta"]:
        session.add(Ingredient(name=name, category="test", is_staple=False))
    session.flush()


def test_repository_checks_and_saves(session):
    _ingredients(session)
    repo = SqlRecipeRepository(session)
    recipe = RecipeToStore(
        title="Garlic Pasta",
        source_url="https://example.com/gp",
        source_name="example.com",
        ingredients=[IngredientEntry("garlic"), IngredientEntry("pasta")],
    )
    assert not repo.has_url("https://example.com/gp")
    assert not repo.has_title("example.com", "Garlic Pasta")

    assert repo.save(recipe) is True

    assert repo.has_url("https://example.com/gp")
    assert repo.has_title("example.com", "garlic pasta")
    assert not repo.has_title("other.com", "Garlic Pasta")
    assert repo.save(recipe) is False  # the same recipe again is a duplicate


def test_full_run_stores_recipe_and_original_lines(session):
    _ingredients(session)
    page = RawRecipe(
        source_url="https://www.example.com/gp?utm_source=x",
        title="Garlic Pasta page",
        source_name="example.com",
        page_text="Garlic Pasta. Ingredients: pasta, garlic.",
    )
    parsed = ParsedRecipe(
        is_recipe=True,
        title="Garlic Pasta",
        ingredient_lines=["2 cloves garlic, minced", "200 g pasta"],
        instructions=["Boil.", "Mix."],
    )
    parser = GeminiRecipeParser(
        generate=lambda prompt, limit: GenerateResult(parsed, "STOP"), sleep=lambda s: None
    )
    def new_ingestor():
        # a fresh Ingestor each time, so only the DATABASE can know about earlier runs
        return Ingestor(
            FakeRecipeProvider([page]),
            parser,
            load_lookup_from_db(session),
            SqlRecipeRepository(session),
            search_delay=0,
            parse_delay=0,
        )

    ingestor = new_ingestor()
    report = ingestor.run([RecipeSearchQuery(ingredients=("garlic",))])

    assert report.stored == 1
    recipe = session.execute(select(Recipe)).scalars().one()
    assert recipe.source_url == "https://example.com/gp"  # tracking parameter removed
    assert recipe.instructions == "Boil.\nMix."
    rows = session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.recipe_id)
    ).scalars().all()
    assert sorted(r.raw_text for r in rows) == ["2 cloves garlic, minced", "200 g pasta"]

    # a new run finds the URL already stored in the database
    second = new_ingestor().run([RecipeSearchQuery(ingredients=("garlic",))])
    assert second.stored == 0 and second.duplicate_url == 1
