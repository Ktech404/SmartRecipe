
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <Link href="/" className="footer-brand">
          SmartRecipe
        </Link>

        <p>
          Make the most of what's in your kitchen.
        </p>

        <nav aria-label="Footer navigation">
          <Link href="/">Home</Link>
          <Link href="/search">Find recipes</Link>
          <Link href="/my-recipes">My recipes</Link>
          <Link href="/account">Account</Link>
        </nav>

        <p className="copyright">
          {/*need to fix the handling for how we fetch the date here. */}
          © {new Date().getFullYear()} SmartRecipe
        </p>
      </div>
    </footer>
  );
}
