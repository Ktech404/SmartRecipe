// Types for the backend recipe API (search and recipe page).
// Put this file at smart-recipe/src/types/recipeApi.ts and use these instead of the
// old RecipeSearchCriteria / RecipeSearchResponse in recipe.ts.
// Field names match the backend exactly (snake_case), so no renaming is needed.

// ---- POST /recipes/search --------------------------------------------------

export interface SearchIngredient {
  name: string;
  quantity?: number;
  unit?: string;
}

export interface RecipeSearchRequest {
  ingredients: SearchIngredient[]; // at least 2 different ones
  max_minutes?: number;
  servings?: number;
  tools?: string[]; // the tools the user HAS, e.g. ["oven"]
  description?: string;
  limit?: number; // 1-50, default 20
  offset?: number;
}

export interface MissingIngredient {
  ingredient_id: number | null;
  name: string;
  quantity: number | null;
  unit: string | null;
  substitutes: string[];
}

export type MatchTier = "best" | "partial" | "low";

export interface RecipeResult {
  recipe_id: number;
  slug: string; // use for the link to the recipe page
  title: string;
  image_url: string | null;
  source_url: string | null;
  source_name: string | null;
  total_minutes: number | null;
  rating_avg: number | null;
  rating_count: number | null;
  is_generated: boolean;
  tier: MatchTier;
  match_score: number; // 0 to 1
  missing_ingredients: MissingIngredient[];
}

export interface RecipeSearchResult {
  results: RecipeResult[];
  total: number;
  limit: number;
  offset: number;
  degraded: boolean; // true = web lookup failed, stored recipes only
}

// ---- GET /recipes/slug/{slug} ----------------------------------------------

export interface RecipeIngredientDetail {
  ingredient_id: number;
  name: string;
  quantity: number | null;
  unit: string | null;
  is_optional: boolean;
  text: string | null; // the line as the source page wrote it
}

export interface RecipeDetail {
  recipe_id: number;
  slug: string;
  title: string;
  image_url: string | null;
  source_url: string | null; // link back to the original page
  source_name: string | null;
  total_minutes: number | null;
  servings: number | null;
  rating_avg: number | null;
  rating_count: number | null;
  cuisine: string | null;
  tools: string[];
  is_generated: boolean;
  instructions: string[]; // one entry per step; can be empty
  ingredients: RecipeIngredientDetail[];
  restricted: boolean; // true = breaks the user's allergies/blacklist: show a warning
}

// ---- Errors ----------------------------------------------------------------
// 422: too_few_ingredients | invalid_ingredients (see invalid_ingredients) | validation_error
// 404: not_found      401: log in again

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    invalid_ingredients?: string[];
  };
}

// ---- Example use with the existing apiRequest helper -----------------------
//
// import { apiRequest } from "@/src/api/client";
// import { API_ENDPOINTS } from "@/src/api/endpoints";
//
// export function searchRecipes(body: RecipeSearchRequest) {
//   return apiRequest<RecipeSearchResult>(API_ENDPOINTS.SEARCH_RECIPES, {
//     method: "POST",
//     body: JSON.stringify(body),
//   });
// }
//
// export function getRecipeBySlug(slug: string) {
//   return apiRequest<RecipeDetail>(API_ENDPOINTS.RECIPE_DETAILS(slug));
// }
//
// Search can take 10-20 seconds, so show a loading state while it runs.
