
import Link from "next/link";
import { recipes } from "@/src/data/recipes";

type ResultsPageProps = {
  searchParams: Promise<{ q?: string }>;
};

export default async function ResultsPage() {
  // Temporary prototype behaviour: every search returns all recipes.
  //We'll update this ofc once we connect to backend.
  const results = recipes;

  return (
    <main className="page-container">
      <div className="page-heading">
        <span className="eyebrow">YOUR NEXT MEAL</span>
        <h1>Recipe results</h1>
      </div>

      <div className="section-heading">
        <h2>Found recipes</h2>
        <span className="count-badge">
          {results.length} recipes
        </span>
      </div>

      {results.length > 0 ? (
        <div className="recipe-grid">
          {results.map((recipe) => (
            <Link
              href={`/recipes/${recipe.slug}`}
              className="panel recipe-card"
              key={recipe.id}
            >
            
            {/* Placeholder for image handling.
              <div className="recipe-image">
                <Image
                  src={recipe.image}
                  alt={recipe.name}
                  fill
                  sizes="(max-width: 640px) 100vw, (max-width: 900px) 50vw, 33vw"
                  style={{ objectFit: "cover" }}
                />
              </div>
            */}
              <div className="recipe-card-body">
                <span className="eyebrow">{recipe.cuisine}</span>
                <h3>{recipe.name}</h3>
                <p>{recipe.description}</p>

                <div className="recipe-meta-row">
                  <span>{recipe.time} min</span>
                  <span>★ {recipe.rating}</span>
                </div>

                <span className="text-link">
                  View recipe →
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <section className="panel empty-state">
          <h3>No recipes found</h3>
          <p>
            Try another ingredient or search term.
          </p>
          <Link href="/search" className="button button-primary">
            Back to recipe search
          </Link>
        </section>
      )}
    </main>
  );
}
