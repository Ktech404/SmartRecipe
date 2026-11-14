
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type Ingredient = {
  id: string;
  name: string;
  quantity: string;
  unit: string;
};

/* Sample ingredient data for the prototype. */
const initialIngredients: Ingredient[] = [
  { id: "1", name: "Chicken breast", quantity: "500", unit: "g" },
  { id: "2", name: "Rice", quantity: "2", unit: "cups" },
  { id: "3", name: "Garlic", quantity: "4", unit: "cloves" },
  { id: "4", name: "Lemon", quantity: "2", unit: "whole" },
];

export default function SearchPage() {
  const router = useRouter();

  const [ingredients, setIngredients] =
    useState<Ingredient[]>(initialIngredients);
  const [ingredientName, setIngredientName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("whole");
  const [maxTime, setMaxTime] = useState("30");
  const [servings, setServings] = useState("2");
  const [tools, setTools] = useState<string[]>(["Oven"]);
  const [mealDescription, setMealDescription] = useState("");

  function addIngredient() {
    if (!ingredientName.trim()) return;

    setIngredients((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        name: ingredientName.trim(),
        quantity: quantity.trim() || "1",
        unit,
      },
    ]);

    setIngredientName("");
    setQuantity("");
  }

  function removeIngredient(id: string) {
    setIngredients((current) =>
      current.filter((item) => item.id !== id)
    );
  }

  function toggleTool(tool: string) {
    setTools((current) =>
      current.includes(tool)
        ? current.filter((item) => item !== tool)
        : [...current, tool]
    );
  }

  function discoverRecipes(mode: string) {
    // Keep the search details in the URL for future functionality.
    const params = new URLSearchParams();

    const query = [
      ...ingredients.map((ingredient) => ingredient.name),
      mealDescription.trim(),
    ]
      .filter(Boolean)
      .join(" ");

    if (query) {
      params.set("q", query);
    }

    params.set("mode", mode);
    params.set("time", maxTime);
    params.set("servings", servings || "2");

    if (tools.length > 0) {
      params.set("tools", tools.join(","));
    }

    router.push(`/search/results?${params.toString()}`);
  }

  return (
    <div className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR NEXT MEAL STARTS HERE</span>
        <h1>Search &amp; generate recipes</h1>
        <p>
          Use your current ingredients or your cuisine preferences to find
          your next favorite meal.
        </p>
      </div>

      <section className="discovery-grid">
        <button
          className="discovery-card panel"
          onClick={() => discoverRecipes("owned")}
          type="button"
        >
          <span className="discovery-icon">✳</span>
          <strong>Use my ingredients</strong>
          <span>Find meals from what&apos;s already in your kitchen.</span>
          <span className="text-link">Find matches →</span>
        </button>

        <button
          className="discovery-card panel"
          onClick={() => discoverRecipes("preferences")}
          type="button"
        >
          <span className="discovery-icon">◎</span>
          <strong>Explore my preferences</strong>
          <span>
            Discover meals based on cuisines and dietary needs.
          </span>
          <span className="text-link">Explore meals →</span>
        </button>
      </section>

      <div className="or-divider">
        <span>OR BUILD YOUR OWN SEARCH</span>
      </div>

      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          discoverRecipes("search");
        }}
      >
        <section className="panel form-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">STEP 1</span>
              <h2>Your ingredients</h2>
            </div>
            <span className="count-badge">
              {ingredients.length} items
            </span>
          </div>

          <div className="ingredient-entry">
            <label className="sr-only" htmlFor="ingredient-name">
              Ingredient name
            </label>
            <input
              id="ingredient-name"
              value={ingredientName}
              onChange={(event) => setIngredientName(event.target.value)}
              placeholder="Ingredient name"
            />

            <label className="sr-only" htmlFor="ingredient-quantity">
              Quantity
            </label>
            <input
              id="ingredient-quantity"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="Qty"
              className="quantity-input"
            />

            <label className="sr-only" htmlFor="ingredient-unit">
              Unit
            </label>
            <select
              id="ingredient-unit"
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
            >
              <option value="whole">Whole</option>
              <option value="g">g</option>
              <option value="kg">kg</option>
              <option value="ml">ml</option>
              <option value="litres">litres</option>
              <option value="cups">cups</option>
              <option value="cloves">cloves</option>
              <option value="tbsp">tbsp</option>
              <option value="tsp">tsp</option>
            </select>

            <button
              type="button"
              className="button button-primary"
              onClick={addIngredient}
            >
              + Add
            </button>
          </div>

          <div className="ingredient-list">
            {ingredients.map((ingredient) => (
              <div className="ingredient-row" key={ingredient.id}>
                <span className="ingredient-dot" />
                <span className="ingredient-name">
                  {ingredient.name}
                </span>
                <span className="muted">
                  {ingredient.quantity} {ingredient.unit}
                </span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remove ${ingredient.name}`}
                  onClick={() => removeIngredient(ingredient.id)}
                >
                  ×
                </button>
              </div>
            ))}

            {ingredients.length === 0 && (
              <p className="empty-message">
                Add some ingredients to get started.
              </p>
            )}
          </div>
        </section>

        <section className="panel form-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">STEP 2</span>
              <h2>Recipe details</h2>
            </div>
          </div>

          <div className="field-group">
            <label htmlFor="max-time">Maximum cooking time</label>
            <select
              id="max-time"
              value={maxTime}
              onChange={(event) => setMaxTime(event.target.value)}
            >
              <option value="15">15 minutes</option>
              <option value="30">30 minutes</option>
              <option value="45">45 minutes</option>
              <option value="60">60 minutes</option>
              <option value="120">No time limit</option>
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="servings">Number of servings</label>
            <input
              id="servings"
              type="number"
              min="1"
              max="30"
              value={servings}
              onChange={(event) => setServings(event.target.value)}
            />
          </div>

          <div className="field-group">
            <span className="field-label">Cooking tools</span>
            <div className="chip-group">
              {[
                "Oven",
                "Air fryer",
                "Stovetop",
                "Microwave",
                "Blender",
                "Food processor",
              ].map((tool) => (
                <button
                  type="button"
                  key={tool}
                  className={`chip ${
                    tools.includes(tool) ? "chip-active" : ""
                  }`}
                  aria-pressed={tools.includes(tool)}
                  onClick={() => toggleTool(tool)}
                >
                  {tool}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel form-panel full-width">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">STEP 3</span>
              <h2>Describe your meal</h2>
            </div>
          </div>

          <label className="sr-only" htmlFor="meal-description">
            Describe your ideal meal
          </label>
          <textarea
            id="meal-description"
            rows={3}
            value={mealDescription}
            onChange={(event) => setMealDescription(event.target.value)}
            placeholder="For example, a cosy weeknight dinner that's light but filling..."
          />
        </section>

        <div className="form-actions full-width">
          <button
            type="submit"
            className="button button-primary button-large"
          >
            Search recipes →
          </button>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => discoverRecipes("generate")}
          >
            ✦ Generate a recipe
          </button>
        </div>
      </form>
    </div>
  );
}
