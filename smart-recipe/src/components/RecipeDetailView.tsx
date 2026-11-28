"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@/src/api/client";
import { getRecipeBySlug } from "@/src/services/recipeService";
import type { RecipeDetail, RecipeIngredientDetail } from "@/src/types/recipeApi";

type State =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "done"; recipe: RecipeDetail };

async function load(slug: string): Promise<State> {
  try {
    return { status: "done", recipe: await getRecipeBySlug(slug) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return { status: "not-found" };
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Something went wrong. Please try again.",
    };
  }
}

function amount(item: RecipeIngredientDetail) {
  if (item.quantity == null) return "";
  const quantity = Number.isInteger(item.quantity)
    ? String(item.quantity)
    : item.quantity.toFixed(2).replace(/0+$/, "");
  return item.unit ? `${quantity} ${item.unit}` : quantity;
}

export default function RecipeDetailView({ slug }: { slug: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    load(slug).then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (state.status === "loading") {
    return (
      <main className="page-container" role="status">
        Loading recipe…
      </main>
    );
  }

  if (state.status === "not-found" || state.status === "error") {
    return (
      <main className="page-container">
        <section className="panel empty-state">
          <h3>{state.status === "not-found" ? "Recipe not found" : "We couldn't load that recipe"}</h3>
          <p role={state.status === "error" ? "alert" : undefined}>
            {state.status === "error" ? state.message : "This recipe may have been removed."}
          </p>
          <Link href="/search" className="button button-primary">
            Back to recipe search
          </Link>
        </section>
      </main>
    );
  }

  const { recipe } = state;
  const sourceName = recipe.source_name ?? "the original site";

  return (
    <main className="page-container">
      <Link href="/search/results" className="text-link">
        ← Back to recipe results
      </Link>

      <header className="page-heading" style={{ marginTop: 24 }}>
        {recipe.cuisine && <span className="eyebrow">{recipe.cuisine}</span>}
        <h1>{recipe.title}</h1>
        {recipe.source_name && <p>From {recipe.source_name}</p>}

        <div className="recipe-meta">
          {recipe.total_minutes != null && <span>{recipe.total_minutes} minutes</span>}
          {recipe.servings != null && <span>{recipe.servings} servings</span>}
          {recipe.rating_avg != null && <span>★ {recipe.rating_avg}</span>}
        </div>
      </header>

      {recipe.restricted && (
        <section className="panel" role="alert" style={{ marginBottom: 24 }}>
          <strong>Heads up:</strong> this recipe contains an ingredient from your
          allergies or blacklist. Check the ingredients carefully before cooking it.
        </section>
      )}

      <section className="panel recipe-ingredients">
        <h2>Ingredients</h2>
        <ul>
          {recipe.ingredients.map((item) => (
            <li key={item.ingredient_id}>
              <span>
                {item.name}
                {item.is_optional ? " (optional)" : ""}
              </span>
              <strong>{amount(item) || item.text || ""}</strong>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel recipe-instructions">
        <h2>Cooking instructions</h2>

        {recipe.instructions.length > 0 ? (
          <ol>
            {recipe.instructions.map((instruction, index) => (
              <li key={index}>
                <span className="instruction-number">{index + 1}</span>
                <p>{instruction}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p>The steps for this recipe are on the original site.</p>
        )}

        {recipe.source_url && (
          <p>
            <a
              className="text-link"
              href={recipe.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View the full recipe on {sourceName} →
            </a>
          </p>
        )}
      </section>
    </main>
  );
}
