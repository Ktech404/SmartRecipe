import { Suspense } from "react";
import RecipeDetailView from "@/src/components/RecipeDetailView";

type RecipePageProps = {
  params: Promise<{ slug: string }>;
};

async function RecipeFromParams({ params }: RecipePageProps) {
  const { slug } = await params;
  return <RecipeDetailView slug={slug} />;
}

// The recipe itself is loaded in the browser (it needs the signed-in user's token),
// so this page only reads the slug from the address.
export default function RecipeDetailPage({ params }: RecipePageProps) {
  return (
    <Suspense
      fallback={
        <main className="page-container" role="status">
          Loading recipe…
        </main>
      }
    >
      <RecipeFromParams params={params} />
    </Suspense>
  );
}
