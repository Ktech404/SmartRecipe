import RequireAuth from "@/src/components/RequireAuth";
import type { ReactNode } from "react";

// Searching needs a signed-in user: the backend applies their allergies and blacklist.
export default function SearchLayout({ children }: { children: ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
