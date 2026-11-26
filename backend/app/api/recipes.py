"""POST /recipes/search: find recipes for the ingredients a user has.  (SCRUM-35)
GET /recipes/slug/{slug}: one stored recipe with its ingredients and steps.  (SCRUM-39)

Flow
1. Check the request: enough ingredients, and every one recognized (1.3.2, 1.3.7,
   1.3.12). Problems return the standard error body:
       {"error": {"code": "...", "message": "...", "invalid_ingredients": [...]}}
2. Search the stored recipes, hiding anything that breaks the user's allergies,
   blacklist or allergen groups (1.3.10).
3. If fewer than LIVE_SEARCH_THIN_THRESHOLD good matches were found, search the
   web, store the new recipes and search again. Only on the first page
   (offset 0), so paging never triggers another web search. The same ingredient
   set is not searched on the web again for LIVE_SEARCH_CACHE_HOURS.
4. If the web search is unavailable, return the stored results with
   `degraded: true` (2.2.1.3).

The route is mounted at /recipes/search, like /auth/... today. When the whole API
moves under /api/v1 (DEV_PLAN section 5), change the prefix in one place.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_session
from app.db.models import User
from app.providers.base import RecipeSearchQuery
from app.schemas.recipe_detail import RecipeDetail
from app.schemas.search import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.live_search import (
    LiveFetcher,
    LiveSearchSettings,
    RecentSearchCache,
    build_live_fetcher,
    get_recent_searches,
)
from app.services.recipe_detail import load_recipe_detail
from app.services.recipe_search import (
    load_restrictions,
    resolve_ingredient_ids,
    search_stored_recipes,
)
from app.services.slugs import parse_slug_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes", tags=["Recipes"])

# Confirm with the team (requirement 1.3.12). One ingredient matches too much to be useful.
MIN_INGREDIENTS = 2


def get_live_settings() -> LiveSearchSettings:
    return LiveSearchSettings.from_env()


def get_live_fetcher(
    session: Session = Depends(get_session),
    settings: LiveSearchSettings = Depends(get_live_settings),
) -> LiveFetcher | None:
    return build_live_fetcher(session, settings)


def _error(code: ErrorCode, message: str, invalid: list[str] | None = None) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, invalid_ingredients=invalid)
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json", exclude_none=True))


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={422: {"model": ErrorResponse, "description": "Too few or unrecognized ingredients"}},
)
def search_recipes(
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    live: LiveFetcher | None = Depends(get_live_fetcher),
    settings: LiveSearchSettings = Depends(get_live_settings),
    recent: RecentSearchCache = Depends(get_recent_searches),
):
    names = [item.name for item in payload.ingredients]
    if len({name.lower() for name in names}) < MIN_INGREDIENTS:
        return _error(
            ErrorCode.TOO_FEW_INGREDIENTS,
            f"Enter at least {MIN_INGREDIENTS} different ingredients.",
        )

    resolved = resolve_ingredient_ids(session, names)
    if resolved.unknown:
        return _error(
            ErrorCode.INVALID_INGREDIENTS,
            "Some ingredients were not recognized as food: " + ", ".join(resolved.unknown),
            resolved.unknown,
        )
    if len(resolved.ids) < MIN_INGREDIENTS:
        return _error(
            ErrorCode.TOO_FEW_INGREDIENTS,
            f"Enter at least {MIN_INGREDIENTS} different ingredients.",
        )

    restrictions = load_restrictions(session, user.user_id)

    def stored_search():
        return search_stored_recipes(
            session,
            resolved.ids,
            max_minutes=payload.max_minutes,
            tools=payload.tools,
            restrictions=restrictions,
            limit=payload.limit,
            offset=payload.offset,
        )

    result = stored_search()
    degraded = False

    thin = settings.enabled and payload.offset == 0 and result.strong < settings.thin_threshold
    searched_key = tuple(sorted(resolved.ids))
    if thin and not recent.seen(searched_key, settings.cache_hours * 3600):
        if live is None:
            degraded = True  # live search is not configured here
        else:
            outcome = None
            try:
                outcome = live.fetch(
                    RecipeSearchQuery(
                        ingredients=tuple(names),
                        max_minutes=payload.max_minutes,
                        servings=payload.servings,
                        tools=tuple(payload.tools),
                        description=payload.description,
                        limit=settings.max_pages,
                    )
                )
            except Exception as error:  # a web problem must never break a stored search
                if isinstance(error, SQLAlchemyError):
                    session.rollback()  # a failed database write leaves the session unusable
                log.warning("live recipe search failed: %s", type(error).__name__)
            if outcome is None or not outcome.ok:
                degraded = True
            else:
                recent.remember(searched_key)  # do not repeat this web search for a while
            if outcome is not None and outcome.stored:
                result = stored_search()

    return SearchResponse(
        results=result.results,
        total=result.total,
        limit=payload.limit,
        offset=payload.offset,
        degraded=degraded,
    )


@router.get(
    "/slug/{slug}",
    response_model=RecipeDetail,
    responses={404: {"model": ErrorResponse, "description": "No recipe at this address"}},
)
def get_recipe_by_slug(
    slug: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """The full recipe page. The id at the end of the slug is what is looked up."""
    recipe_id = parse_slug_id(slug)
    detail = (
        load_recipe_detail(session, recipe_id, load_restrictions(session, user.user_id))
        if recipe_id is not None
        else None
    )
    if detail is None:
        body = ErrorResponse(
            error=ErrorDetail(code=ErrorCode.NOT_FOUND, message="Recipe not found.")
        )
        return JSONResponse(status_code=404, content=body.model_dump(mode="json", exclude_none=True))
    return detail
