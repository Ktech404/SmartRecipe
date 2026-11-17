
export const API_ENDPOINTS = {
  // Authentication
  REGISTER: "/auth/register",
  LOGIN: "/auth/login",
  LOGOUT: "/auth/logout",

  // User account
  CURRENT_USER: "/users/me",
  USER_PREFERENCES: "/users/preferences",

  // Recipes
  SEARCH_RECIPES: "/recipes/search",
  GENERATE_RECIPE: "/recipes/generate",
  RECIPE_DETAILS: (id: string) => `/recipes/${id}`,

  // Saved recipes
  SAVED_RECIPES: "/recipes/saved",
  SAVE_RECIPE: (id: string) => `/recipes/saved/${id}`,
  REMOVE_SAVED_RECIPE: (id: string) => `/recipes/saved/${id}`,

  // Shopping list
  SHOPPING_LIST: "/shopping-list",
  SHOPPING_LIST_ITEM: (id: string) => `/shopping-list/${id}`,

};
