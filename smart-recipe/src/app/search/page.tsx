
"use client";

import { useState } from "react";

type Ingredient = {
  id: number;
  name: string;
  quantity: string;
  unit: string;
};

{/*Sample recipe data.*/}
const initialIngredients: Ingredient[] = [
  { id: 1, name: "Chicken breast", quantity: "500", unit: "g" },
  { id: 2, name: "Rice", quantity: "2", unit: "cups" },
  { id: 3, name: "Garlic", quantity: "4", unit: "cloves" },
  { id: 4, name: "Lemon", quantity: "2", unit: "whole" },
];

const sampleResults = [
  {
    name: "Lemon garlic chicken",
    time: "25 min",
    match: "Best match",
    description: "A bright, simple chicken dinner with garlic and lemon.",
  },
  {
    name: "Chicken fried rice",
    time: "20 min",
    match: "Partial match",
    description: "A quick rice dish with chicken and aromatic garlic.",
  },
  {
    name: "Lemon rice bowl",
    time: "15 min",
    match: "Low match",
    description: "A flexible rice bowl with fresh lemon flavours.",
  },
];

export default function SearchPage() {
  const [ingredients, setIngredients] =
    useState<Ingredient[]>(initialIngredients);
  const [ingredientName, setIngredientName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("whole");
  const [maxTime, setMaxTime] = useState("30");
  const [servings, setServings] = useState("2");
  const [tools, setTools] = useState<string[]>(["Oven"]);
  const [mealDescription, setMealDescription] = useState("");
  const [mode, setMode] = useState("search");
  const [searched, setSearched] = useState(false);

  function addIngredient() {
    if (!ingredientName.trim()) return;

    setIngredients((current) => [
      ...current,
      {
        id: Date.now(),
        name: ingredientName.trim(),
        quantity: quantity.trim() || "1",
        unit,
      },
    ]);

    setIngredientName("");
    setQuantity("");
  }

  function removeIngredient(id: number) {
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

  function discoverRecipes(selectedMode: string) {
    setMode(selectedMode);
    setSearched(true);
  }

  return (
    <div className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR NEXT MEAL STARTS HERE</span>
        <h1>Search &amp; generate recipes</h1>
        <p>
          Use your current ingredients or your cuisine preferences to find your next favorite meal.
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
          <span>Find meals from what's already in your kitchen.</span>
          <span className="text-link">Find matches →</span>
        </button>

        <button
          className="discovery-card panel"
          onClick={() => discoverRecipes("preferences")}
          type="button"
        >
          <span className="discovery-icon">◎</span>
          <strong>Explore my preferences</strong>
          <span>Discover meals based on cuisines and dietary needs.</span>
          <span className="text-link">Explore meals →</span>
        </button>
        {/*Still have the option to add the "surprise me", might cut.*/}
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
                {/*give the user the option to enter their own time.*/}
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
              {["Oven", "Air fryer", "Stovetop", "Microwave", "Blender", "Food processor"].map(
                (tool) => (
                  <button
                    type="button"
                    key={tool}
                    className={`chip ${tools.includes(tool) ? "chip-active" : ""}`}
                    aria-pressed={tools.includes(tool)}
                    onClick={() => toggleTool(tool)}
                  >
                    {tool}
                  </button>
                )
              )}
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
          <button type="submit" className="button button-primary button-large">
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


{/*TO-DO!!! The site should display results on a different page, this is just a place*/
/*Also, each recipe card should be a link/expand into it's own card page/display...*/
/*---------------------------------------------------*/}

      {searched && (
        <section className="section-block results-section">see where inspiration takes you
          <div className="section-heading">
            <div>
              <span className="eyebrow">YOUR INSPIRATION</span>
              <h2>
                {mode === "generate"
                  ? "Recipe ideas for you"
                  : mode === "surprise"
                    ? "A little surprise"
                    : "Recipes to explore"}
              </h2>
            </div>
            <span className="count-badge">
              {sampleResults.length} examples
            </span>
          </div>

          <p className="muted">
            Demo results using your current selections: {ingredients.length}{" "}
            ingredients, up to {maxTime} minutes, {servings || "2"} servings.
            {mealDescription ? ` Your meal idea: ${mealDescription}` : ""}
          </p>

          <div className="recipe-grid">
            {sampleResults.map((recipe, index) => (
              <article className="panel recipe-card" key={recipe.name}>
                <div className={`recipe-art recipe-art-${index + 1}`}>
                  {/*The recipe-art span should change color based on the quanity of the match */}
                  <span>{recipe.match}</span>
                </div>
                <div className="recipe-card-body">
                  <h3>{recipe.name}</h3>
                  <p>{recipe.description}</p>
                  <span className="recipe-meta">◷ {recipe.time}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
