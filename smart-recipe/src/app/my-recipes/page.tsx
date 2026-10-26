
"use client";

import { useMemo, useState } from "react";

type SavedRecipe = {
  id: number;
  name: string;
  time: number;
  rating: number;
  reviews: number;
  cuisine: string;
  starred: boolean;
};

//place holder recipes to get a feel for the site until backend is up.
const initialRecipes: SavedRecipe[] = [
  {
    id: 1,
    name: "Lemon garlic chicken",
    time: 25,
    rating: 4.6,
    reviews: 128,
    cuisine: "Mediterranean",
    starred: true,
  },
  {
    id: 2,
    name: "Chicken fried rice",
    time: 20,
    rating: 4.4,
    reviews: 310,
    cuisine: "Asian",
    starred: false,
  },
  {
    id: 3,
    name: "Spaghetti aglio e olio",
    time: 15,
    rating: 4.7,
    reviews: 561,
    cuisine: "Italian",
    starred: true,
  },
  {
    id: 4,
    name: "Black bean tacos",
    time: 30,
    rating: 4.5,
    reviews: 92,
    cuisine: "Mexican",
    starred: false,
  },
  {
    id: 5,
    name: "Roasted vegetable pasta",
    time: 35,
    rating: 4.3,
    reviews: 76,
    cuisine: "Italian",
    starred: false,
  },
  {
    id: 6,
    name: "Creamy mushroom rice",
    time: 25,
    rating: 4.5,
    reviews: 104,
    cuisine: "European",
    starred: true,
  },
];

export default function MyRecipesPage() {
  const [recipes, setRecipes] = useState(initialRecipes);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recent");

  const visibleRecipes = useMemo(() => {
    let result = recipes.filter((recipe) =>
      recipe.name.toLowerCase().includes(query.toLowerCase())
    );

    if (filter === "starred") {
      result = result.filter((recipe) => recipe.starred);
    }

    if (filter === "quick") {
      result = result.filter((recipe) => recipe.time <= 25);
    }

    if (filter === "italian") {
      result = result.filter((recipe) => recipe.cuisine === "Italian");
    }

    if (sort === "name") {
      result.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sort === "time") {
      result.sort((a, b) => a.time - b.time);
    } else if (sort === "rating") {
      result.sort((a, b) => b.rating - a.rating);
    }

    return result;
  }, [recipes, query, filter, sort]);

  function toggleStar(id: number) {
    setRecipes((current) =>
      current.map((recipe) =>
        recipe.id === id
          ? { ...recipe, starred: !recipe.starred }
          : recipe
      )
    );
  }

  return (
    <div className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR PERSONAL COOKBOOK</span>
        <h1>My Recipes</h1>
        <p>
          Your saved favourites, ready whenever you need a little inspiration.
        </p>
      </div>

      <section className="panel library-toolbar">
        <div className="search-input-wrap">
          <span aria-hidden="true">⌕</span>
          <label className="sr-only" htmlFor="recipe-search">
            Search saved recipes
          </label>
          <input
            id="recipe-search"
            type="search"
            placeholder="Search your saved recipes..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="sort-control">
          <label htmlFor="recipe-sort">Sort by</label>
          <select
            id="recipe-sort"
            value={sort}
            onChange={(event) => setSort(event.target.value)}
          >
            <option value="recent">Last added</option>
            <option value="name">Name</option>
            <option value="time">Cooking time</option>
            <option value="rating">Rating</option>
          </select>
        </div>
      </section>

      <section className="section-block">
        <div className="filter-row">
          <span className="filter-label">Quick filters</span>
          {[
            //tentative filters!
            { id: "all", label: "All recipes" },
            { id: "quick", label: "Under 25 min" },
            { id: "starred", label: "★ Starred" },
            { id: "italian", label: "Italian" },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              className={`chip ${filter === item.id ? "chip-active" : ""}`}
              aria-pressed={filter === item.id}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="section-heading">
          <h2>Saved recipes</h2>
          <span className="count-badge">
            {visibleRecipes.length} recipes
          </span>
        </div>

        {visibleRecipes.length > 0 ? (
          <div className="recipe-grid">
            {visibleRecipes.map((recipe, index) => (
              <article className="panel recipe-card" key={recipe.id}>
                <div className={`recipe-art recipe-art-${(index % 4) + 1}`}>
                  <span>{recipe.cuisine}</span>
                  <button
                    type="button"
                    className={`star-button ${recipe.starred ? "is-starred" : ""}`}
                    aria-label={
                      recipe.starred
                        ? `Remove ${recipe.name} from starred recipes`
                        : `Star ${recipe.name}`
                    }
                    aria-pressed={recipe.starred}
                    onClick={() => toggleStar(recipe.id)}
                  >
                    {recipe.starred ? "★" : "☆"}
                  </button>
                </div>

                <div className="recipe-card-body">
                  <h3>{recipe.name}</h3>
                  <div className="recipe-meta-row">
                    <span>◷ {recipe.time} min</span>
                    <span>
                      ★ {recipe.rating}{" "}
                      <span className="muted">
                        ({recipe.reviews})
                      </span>
                    </span>
                  </div>
                  <p className="muted">
                    {recipe.cuisine} cuisine
                  </p>
                  <button
                    type="button"
                    className="button button-secondary button-full"
                    onClick={() =>
                      window.alert(
                        `${recipe.name}: recipe details will be available when the recipe-detail functionality is added.`
                      )
                    }
                  >
                    View recipe
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="panel empty-state">
            <span className="empty-state-icon">♡</span>
            <h3>No recipes found</h3>
            <p>
              Try another search or select a different filter.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
