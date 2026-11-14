
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <Link href="/" className="footer-brand">
          SmartRecipe
        </Link>

        <p>
          Cook smarter, not harder.
        </p>

        <nav aria-label="Footer navigation">
          <Link href="/">Home</Link>
          <Link href="/search">Find recipes</Link>
          <Link href="/my-recipes">My recipes</Link>
          <Link href="/account">Account</Link>
        </nav>

        <p className="copyright">
          © 2026 SmartRecipe
        </p>
      </div>
    </footer>
  );
}
