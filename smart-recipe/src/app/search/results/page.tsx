"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/src/api/client";
import { searchRecipes } from "@/src/services/recipeService";
import { readPendingSearch } from "@/src/services/searchHandoff";
import type {
  RecipeResult,
  RecipeSearchRequest,
  RecipeSearchResult,
} from "@/src/types/recipeApi";

type State =
  | { status: "loading" }
  | { status: "no-search" }
  | { status: "unsupported" }
  | { status: "error"; message: string }
  | { status: "done"; data: RecipeSearchResult };

// React runs effects twice in development. A search can start a 10-20 second web
// lookup on the backend, so searches that are already running are shared.
const running = new Map<string, Promise<RecipeSearchResult>>();

function searchOnce(request: RecipeSearchRequest) {
  const key = JSON.stringify(request);
  let promise = running.get(key);
  if (!promise) {
    promise = searchRecipes(request).finally(() => running.delete(key));
    running.set(key, promise);
  }
  return promise;
}

async function load(): Promise<State> {
  const pending = readPendingSearch();
  if (!pending) return { status: "no-search" };
  if (pending.mode === "preferences" || pending.mode === "generate") {
    return { status: "unsupported" };
  }
  try {
    return { status: "done", data: await searchOnce(pending.request) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return { status: "error", message: "Your session has ended. Please sign in again." };
    }
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Something went wrong. Please try again.",
    };
  }
}

function RecipeCard({ recipe }: { recipe: RecipeResult }) {
  return (
    <Link href={`/recipes/${recipe.slug}`} className="panel recipe-card">
      <div className="recipe-card-body">
        {recipe.source_name && <span className="eyebrow">{recipe.source_name}</span>}
        <h3>{recipe.title}</h3>

        <div className="recipe-meta-row">
          <span>{Math.round(recipe.match_score * 100)}% match</span>
          {recipe.total_minutes != null && <span>{recipe.total_minutes} min</span>}
        </div>

        {recipe.missing_ingredients.length > 0 && (
          <p>
            <strong>You&apos;re missing: </strong>
            {recipe.missing_ingredients
              .map((item) =>
                item.substitutes.length > 0
                  ? `${item.name} (try ${item.substitutes.join(" or ")})`
                  : item.name
              )
              .join(", ")}
          </p>
        )}

        <span className="text-link">View recipe →</span>
      </div>
    </Link>
  );
}

function Group({ title, recipes }: { title: string; recipes: RecipeResult[] }) {
  if (recipes.length === 0) return null;
  return (
    <section style={{ marginTop: 32 }}>
      <div className="section-heading">
        <h2>{title}</h2>
        <span className="count-badge">{recipes.length}</span>
      </div>
      <div className="recipe-grid">
        {recipes.map((recipe) => (
          <RecipeCard recipe={recipe} key={recipe.recipe_id} />
        ))}
      </div>
    </section>
  );
}

export default function ResultsPage() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    load().then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR NEXT MEAL</span>
        <h1>Recipe results</h1>
      </div>

      {state.status === "loading" && (
        <p role="status">
          Searching for recipes… this can take up to 20 seconds while we look for
          new ones.
        </p>
      )}

      {state.status === "error" && (
        <section className="panel empty-state">
          <h3>We couldn&apos;t complete that search</h3>
          <p role="alert">{state.message}</p>
          <Link href="/search" className="button button-primary">
            Back to recipe search
          </Link>
        </section>
      )}

      {(state.status === "no-search" || state.status === "unsupported") && (
        <section className="panel empty-state">
          <h3>
            {state.status === "unsupported"
              ? "This option isn't available yet"
              : "Start a search first"}
          </h3>
          <p>
            {state.status === "unsupported"
              ? "Searching with your ingredients works today. Preferences and recipe generation are coming soon."
              : "Add your ingredients on the search page and try again."}
          </p>
          <Link href="/search" className="button button-primary">
            Back to recipe search
          </Link>
        </section>
      )}

      {state.status === "done" && (
        <>
          {state.data.degraded && (
            <p role="status">
              We couldn&apos;t look for new recipes online just now, so these are
              saved recipes only.
            </p>
          )}

          <div className="section-heading">
            <h2>Found recipes</h2>
            <span className="count-badge">{state.data.total} recipes</span>
          </div>

          {state.data.results.length > 0 ? (
            <>
              <Group
                title="Best matches"
                recipes={state.data.results.filter((r) => r.tier === "best")}
              />
              <Group
                title="Partial matches"
                recipes={state.data.results.filter((r) => r.tier === "partial")}
              />
              <Group
                title="Weaker matches"
                recipes={state.data.results.filter((r) => r.tier === "low")}
              />
            </>
          ) : (
            <section className="panel empty-state">
              <h3>No recipes found</h3>
              <p>Try other ingredients or a longer cooking time.</p>
              <Link href="/search" className="button button-primary">
                Back to recipe search
              </Link>
            </section>
          )}
        </>
      )}
    </main>
  );
}
