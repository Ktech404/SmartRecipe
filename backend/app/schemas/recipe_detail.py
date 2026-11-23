"""Response model for GET /recipes/slug/{slug}.  (SCRUM-39)

A search result is a summary. This is the full recipe page: ingredients and steps.
"""

from pydantic import BaseModel, Field


class RecipeIngredientDetail(BaseModel):
    ingredient_id: int
    name: str  # our ingredient name, e.g. "chicken breast"
    quantity: float | None = None
    unit: str | None = None
    is_optional: bool = False
    text: str | None = None  # the line as the source page wrote it


class RecipeDetail(BaseModel):
    recipe_id: int
    slug: str
    title: str
    image_url: str | None = None
    source_url: str | None = None  # link back to the original page
    source_name: str | None = None
    total_minutes: int | None = None
    servings: int | None = None
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    cuisine: str | None = None
    tools: list[str] = Field(default_factory=list)
    is_generated: bool = False
    instructions: list[str] = Field(default_factory=list)  # one entry per step; may be empty
    ingredients: list[RecipeIngredientDetail] = Field(default_factory=list)
    # True when this recipe breaks the signed-in user's allergies, allergen groups
    # or blacklist. Search never returns such recipes, but a saved link can still
    # open one, so the page should show a clear warning.
    restricted: bool = False
