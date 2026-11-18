"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/src/auth/AuthProvider";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading, error, retry } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user && !error) router.replace("/login");
  }, [loading, user, error, router]);
  if (loading) return <div className="page-container" role="status">Checking your session…</div>;
  if (error) return <div className="page-container">
    <p role="alert">{error}</p>
    <button className="button button-primary" onClick={retry}>Try again</button>
  </div>;
  if (!user) return <div className="page-container">
    <h1>Sign in to continue</h1>
    <p>Your session may have ended. Sign in to access your account.</p>
    <Link className="button button-primary" href="/login">Sign in</Link>
    {" "}<Link className="text-link" href="/register">Create an account</Link>
  </div>;
  return children;
}

