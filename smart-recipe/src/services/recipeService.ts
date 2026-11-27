import { apiRequest } from "@/src/api/client";
import { API_ENDPOINTS } from "@/src/api/endpoints";
import type { Recipe, GenerateRecipeRequest, SavedRecipe } from "@/src/types/recipe";
import type {
  RecipeDetail,
  RecipeSearchRequest,
  RecipeSearchResult,
} from "@/src/types/recipeApi";

export async function searchRecipes(
  request: RecipeSearchRequest
): Promise<RecipeSearchResult> {
  return apiRequest<RecipeSearchResult>(
    API_ENDPOINTS.SEARCH_RECIPES,
    {
      method: "POST",
      body: JSON.stringify(request),
    }
  );
}

export async function generateRecipe(
  data: GenerateRecipeRequest
): Promise<Recipe> {
  return apiRequest<Recipe>(
    API_ENDPOINTS.GENERATE_RECIPE,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function getRecipeBySlug(
  slug: string
): Promise<RecipeDetail> {
  return apiRequest<RecipeDetail>(
    API_ENDPOINTS.RECIPE_DETAILS(slug)
  );
}

export async function getSavedRecipes(): Promise<SavedRecipe[]> {
  return apiRequest<SavedRecipe[]>(
    API_ENDPOINTS.SAVED_RECIPES
  );
}

export async function saveRecipe(id: string): Promise<void> {
  return apiRequest<void>(
    API_ENDPOINTS.SAVE_RECIPE(id),
    {
      method: "POST",
    }
  );
}

export async function removeSavedRecipe(
  id: string
): Promise<void> {
  return apiRequest<void>(
    API_ENDPOINTS.REMOVE_SAVED_RECIPE(id),
    {
      method: "DELETE",
    }
  );
}
