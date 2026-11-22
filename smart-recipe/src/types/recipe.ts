export interface Ingredient {
  id?: string;
  name: string;
  quantity: string;
}

export interface Recipe {
  id: string;
  name: string;
  slug: string;
  description: string;
  image?: string;
  time: number;
  servings: number;
  cuisine: string;
  rating?: number;
  ingredients: Ingredient[];
  instructions: string[];
}

export interface RecipeSearchCriteria {
  ingredients: string[];
  excludedIngredients?: string[];
  cuisine?: string;
  maxTime?: number;
  servings?: number;
}

export interface RecipeSearchResponse {
  recipes: Recipe[];
  total: number;
}

export interface GenerateRecipeRequest {
  ingredients: string[];
  excludedIngredients?: string[];
  cuisine?: string;
  servings?: number;
}

export interface SavedRecipe {
  id: string;
  recipe: Recipe;
  savedAt: string;
}
