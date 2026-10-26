
import Link from "next/link";

const steps = [
  {
    number: "01",
    title: "Add ingredients",
    description:
      "List what you have in your kitchen, including quantities.",
  },
  {
    number: "02",
    title: "Set the details",
    description:
      "Choose your cooking time, servings, tools and meal preferences.",
  },
  {
    number: "03",
    title: "Find or generate",
    description:
      "Browse matching recipes or explore a new meal idea.",
  },
  {
    number: "04",
    title: "Save and shop",
    description:
      "Save your favourites and collect missing ingredients in one list.",
  },
];

export default function HomePage() {
  return (
    <div className="page-container home-page">
      <section className="hero panel">
        <span className="eyebrow">YOUR KITCHEN, YOUR POSSIBILITIES</span>

        <h1>
          Good food starts
          <br />
          with <span className="accent-text">what you already have.</span>
        </h1>

        <p className="hero-description">
          Tell us what's in your kitchen. We'll help you
          find inspiration, discover recipes and decide
          what's for dinner.
        </p>

        <div className="hero-logo" aria-hidden="true">
          <span>SR</span>
        </div>

        <Link href="/search" className="button button-primary">
          Start searching <span aria-hidden="true">→</span>
        </Link>

        <p className="hero-note">
          Less food waste. More delicious possibilities.
        </p>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">SIMPLE BY DESIGN</span>
            <h2>How it works</h2>
          </div>
          <p>From ingredients to inspiration in four steps.</p>
        </div>

        <div className="steps-grid">
          {steps.map((step) => (
            <article className="step-card panel" key={step.number}>
              <span className="step-number">{step.number}</span>
              <div className="step-illustration" aria-hidden="true">
                {["✳", "◷", "✦", "✓"][Number(step.number) - 1]}
              </div>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="info-grid">
        <article className="panel info-panel">
          <span className="eyebrow">GETTING STARTED</span>
          <h2>Make it personal</h2>
          <ol>
            <li>Add your owned ingredients.</li>
            <li>Set your dietary preferences and allergies.</li>
            <li>Search for meals that suit your kitchen.</li>
            <li>Save recipes and organise your shopping.</li>
          </ol>
          <Link href="/account" className="text-link">
            Set up your profile →
          </Link>
        </article>

        <article className="panel info-panel tinted-panel">
          <span className="eyebrow">A LITTLE TIP</span>
          <h2>Start with what you have</h2>
          <p>
            Recipes can be ranked by how well your ingredients
            match. If you can't find the right meal, try
            generating a new idea.
          </p>
          <Link href="/search" className="text-link">
            Explore recipe search →
          </Link>
        </article>
      </section>
    </div>
  );
}
