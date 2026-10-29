"""Request and response models for POST /api/v1/recipes/search.  (SCRUM-12)

This file is the "contract" for the search endpoint: it says exactly what the
frontend may send and what it gets back. Pydantic checks every incoming request
against these classes and FastAPI turns them into the API docs automatically.

Design notes
- recipe_id is the recipe's row number in OUR database. Search results come from
  recipes we have already fetched, parsed, and stored.
- A search result is a summary. Ingredients and steps are loaded by the recipe
  detail endpoint, not returned here.
- The minimum number of ingredients is NOT checked here. A separate validation
  step will do it so it can return our standard error format (requirement 1.3.12).
- Tier names follow the wireframe (best / partial / low). If the team settles on
  two tiers (requirement 1.3.5), delete LOW and tell the frontend.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_INGREDIENTS = 50
MAX_TOOLS = 20


# An Enum limits a field to a fixed set of values. Anything else is rejected
# with a 422 error before our code runs.
class Unit(str, Enum):
    """The controlled unit list from the dev plan."""

    G = "g"
    KG = "kg"
    OZ = "oz"
    LB = "lb"
    ML = "ml"
    L = "l"
    TSP = "tsp"
    TBSP = "tbsp"
    CUP = "cup"
    CLOVE = "clove"
    CAN = "can"
    PACK = "pack"
    COUNT = "count"


class MatchTier(str, Enum):
    BEST = "best"
    PARTIAL = "partial"
    LOW = "low"


class ErrorCode(str, Enum):
    TOO_FEW_INGREDIENTS = "too_few_ingredients"
    INVALID_INGREDIENTS = "invalid_ingredients"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


# --------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------

# A sample request. It shows up in the API docs, and a test checks it stays valid.
EXAMPLE_REQUEST = {
    "ingredients": [
        {"name": "Chicken breast", "quantity": 500, "unit": "g"},
        {"name": "Rice", "quantity": 2, "unit": "cup"},
        {"name": "Garlic", "quantity": 4, "unit": "clove"},
        {"name": "Lemon", "quantity": 2},
    ],
    "max_minutes": 30,
    "servings": 2,
    "tools": ["oven"],
    "description": "a cozy weeknight dinner that's light but filling",
    "limit": 20,
    "offset": 0,
}


class IngredientInput(BaseModel):
    # Field(...) adds rules. min_length/max_length limit text size,
    # gt=0 means "greater than zero".
    name: str = Field(min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0, le=100_000)
    unit: Unit | None = None

    # A validator runs after the basic checks and can clean or reject a value.
    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class SearchRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE_REQUEST]})

    ingredients: list[IngredientInput] = Field(max_length=MAX_INGREDIENTS)
    max_minutes: int | None = Field(default=None, ge=1, le=1440)
    servings: int | None = Field(default=None, ge=1, le=100)
    tools: list[str] = Field(default_factory=list, max_length=MAX_TOOLS)
    description: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)

    @field_validator("tools")
    @classmethod
    def clean_tools(cls, value: list[str]) -> list[str]:
        return [tool.strip().lower() for tool in value if tool.strip()]


# --------------------------------------------------------------------------
# Response
# --------------------------------------------------------------------------


class MissingIngredient(BaseModel):
    """An ingredient the recipe needs that the user did not list.

    ingredient_id is None when the ingredient is not in our own ingredient table.
    Shaped so the frontend can send it straight to the shopping list.
    """

    ingredient_id: int | None = None
    name: str
    quantity: float | None = None
    unit: Unit | None = None
    substitutes: list[str] = Field(default_factory=list)  # filled in later


class RecipeResult(BaseModel):
    recipe_id: int  # primary key of the recipe table
    title: str
    image_url: str | None = None
    source_url: str | None = None  # the page we got the recipe from
    source_name: str | None = None  # site name, for attribution (req. 2.8.2)
    total_minutes: int | None = None
    # Web pages rarely give us a clean rating. Optional, so the UI can hide them.
    rating_avg: float | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    is_generated: bool = False
    tier: MatchTier
    match_score: float = Field(ge=0, le=1)
    missing_ingredients: list[MissingIngredient] = Field(default_factory=list)


EXAMPLE_RESPONSE = {
    "results": [
        {
            "recipe_id": 1,
            "title": "Lemon garlic chicken",
            "image_url": None,
            "source_url": "https://example-recipes.com/lemon-garlic-chicken",
            "source_name": "Example Recipes",
            "total_minutes": 25,
            "rating_avg": None,
            "rating_count": None,
            "is_generated": False,
            "tier": "best",
            "match_score": 1.0,
            "missing_ingredients": [],
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
    "degraded": False,
}


class SearchResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE_RESPONSE]})

    results: list[RecipeResult]
    total: int = Field(ge=0)
    limit: int
    offset: int
    # True when the recipe provider was unavailable and only stored recipes
    # were returned (requirement 2.2.1.3).
    degraded: bool = False


# --------------------------------------------------------------------------
# Errors always look like: { "error": { "code": "...", "message": "..." } }
# --------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    invalid_ingredients: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
