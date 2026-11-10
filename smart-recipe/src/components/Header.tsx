
import Link from "next/link";

const navigation = [
  { label: "Search / Generate Recipes", href: "/search" },
  { label: "My Recipes", href: "/my-recipes" },
  { label: "Shopping List", href: "/shopping-list" },
];

export default function Header() {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Link href="/" className="brand">
          <span className="brand-mark">S</span>
          <span>SmartRecipe</span>
        </Link>

        <nav className="main-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>

        <Link href="/account" className="account-link">
          <span aria-hidden="true">◉</span>
          <span>Account</span>
        </Link>
      </div>
    </header>
  );
}
