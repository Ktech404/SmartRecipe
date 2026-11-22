"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginUser, registerUser } from "@/src/services/authService";
import { saveSession } from "@/src/auth/session";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const register = mode === "register";
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username") || "").trim();
    const password = String(form.get("password") || "");
    setBusy(true);
    setError("");
    try {
      if (register) {
        await registerUser({ username, password, email: String(form.get("email") || "").trim() });
        setCreated(true);
      } else {
        saveSession(await loginUser({ username, password }));
        router.replace("/profile");
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (created) return <div className="page-container auth-page">
    <section className="panel form-panel" role="status">
      <h1>Account created</h1>
      <p>You can now sign in with your username and password.</p>
      <Link className="button button-primary" href="/login">Sign in</Link>
    </section>
  </div>;

  return <div className="page-container auth-page">
    <h1>{register ? "Create an account" : "Sign in"}</h1>
    <form className="panel form-panel" onSubmit={submit} aria-busy={busy}>
      <div className="field-group">
        <label htmlFor="username">Username</label>
        <input id="username" name="username" autoComplete="username" required
          minLength={register ? 3 : 1} maxLength={50}
          pattern={register ? "[A-Za-z0-9_]+" : undefined}
          aria-describedby={register ? "username-help" : undefined} disabled={busy} />
        {register && <p id="username-help" className="helper-text">3–50 letters, numbers, or underscores.</p>}
      </div>
      {register && <div className="field-group">
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="email" maxLength={254} required disabled={busy} />
      </div>}
      <div className="field-group">
        <label htmlFor="password">Password</label>
        <input id="password" name="password" type="password" required
          minLength={register ? 12 : 1} maxLength={register ? 128 : undefined}
          autoComplete={register ? "new-password" : "current-password"}
          aria-describedby={register ? "password-help" : undefined} disabled={busy} />
        {register && <p id="password-help" className="helper-text">Use 12–128 characters.</p>}
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button button-primary button-full" disabled={busy}>
        {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
      </button>
    </form>
    <p className="auth-switch">{register ? "Already have an account?" : "New to SmartRecipe?"}{" "}
      <Link className="text-link" href={register ? "/login" : "/register"}>
        {register ? "Sign in" : "Create an account"}
      </Link>
    </p>
  </div>;
}

