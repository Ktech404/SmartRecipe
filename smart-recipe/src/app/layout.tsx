
import type { Metadata } from "next";
import "./globals.css";

import Header from "@/src/components/Header";
import Footer from "@/src/components/Footer";

export const metadata: Metadata = {
  title: {
    default: "SmartRecipe",
    template: "%s | SmartRecipe",
  },
  description:
    "Find recipes, make the most of your ingredients, and plan your meals with SmartRecipe.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main className="main-content">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
