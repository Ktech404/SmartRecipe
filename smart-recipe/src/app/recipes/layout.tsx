import RequireAuth from "@/src/components/RequireAuth";
import type { ReactNode } from "react";

export default function RecipesLayout({ children }: { children: ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
