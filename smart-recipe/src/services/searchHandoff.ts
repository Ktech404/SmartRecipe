// Hands the search from the search page to the results page.
// The search page saves the request here and the results page reads it, so the
// ingredient list does not have to be squeezed into the URL.

import type { RecipeSearchRequest } from "@/src/types/recipeApi";

const KEY = "smartrecipe.search";

export type SearchMode = "owned" | "search" | "preferences" | "generate";

export type PendingSearch = {
  mode: SearchMode;
  request: RecipeSearchRequest;
};

export function savePendingSearch(search: PendingSearch) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(search));
  } catch {
    /* Storage may be disabled; the results page will ask the user to search again. */
  }
}

export function readPendingSearch(): PendingSearch | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && Array.isArray(parsed.request?.ingredients) ? parsed : null;
  } catch {
    return null;
  }
}
