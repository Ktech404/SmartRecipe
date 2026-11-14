
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { recipes } from "@/src/data/recipes";

export function generateStaticParams() {
  return recipes.map((recipe) => ({
    slug: recipe.slug,
  }));
}

type RecipePageProps = {
  params: Promise<{ slug: string }>;
};

export default async function RecipeDetailPage({
  params,
}: RecipePageProps) {
  const { slug } = await params;
  const recipe = recipes.find((item) => item.slug === slug);

  if (!recipe) {
    notFound();
  }

  return (
    <main className="page-container">
      <Link href="/search/results" className="text-link">
        ← Back to recipe results
      </Link>

      <header className="page-heading" style={{ marginTop: 24 }}>
        <span className="eyebrow">{recipe.cuisine}</span>
        <h1>{recipe.name}</h1>
        <p>{recipe.description}</p>

        <div className="recipe-meta">
          <span>{recipe.time} minutes</span>
          <span>{recipe.servings} servings</span>
          <span>★ {recipe.rating}</span>
        </div>
      </header>

    {/*Keep in mind this won't work until we get connected to backend. */}
      <div className="recipe-detail-layout">
        <div className="recipe-detail-image">
          <Image
            src={recipe.image}
            alt={recipe.name}
            fill
            priority
            sizes="(max-width: 800px) 100vw, 60vw"
            style={{ objectFit: "cover" }}
          />
        </div>

        <section className="panel recipe-ingredients">
          <h2>Ingredients</h2>
          <p>For {recipe.servings} servings</p>

          <ul>
            {recipe.ingredients.map((ingredient) => (
              <li key={ingredient.name}>
                <span>{ingredient.name}</span>
                <strong>{ingredient.quantity}</strong>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="panel recipe-instructions">
        <h2>Cooking instructions</h2>

        <ol>
          {recipe.instructions.map((instruction, index) => (
            <li key={index}>
              <span className="instruction-number">
                {index + 1}
              </span>
              <p>{instruction}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
