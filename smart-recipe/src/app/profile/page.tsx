"use client";

import Link from "next/link";
import { useAuth } from "@/src/auth/AuthProvider";
import RequireAuth from "@/src/components/RequireAuth";
import { logoutUser } from "@/src/services/authService";

export default function ProfilePage() {
  const { user } = useAuth();
  return <RequireAuth>{user && <div className="page-container auth-page">
    <h1>Your profile</h1>
    <section className="panel form-panel">
      <dl>
        <dt>Username</dt><dd>{user.username}</dd>
        <dt>Email</dt><dd>{user.email}</dd>
      </dl>
      <Link className="button button-primary" href="/search">Find recipes</Link>
      {" "}<button className="button button-secondary" onClick={() => { void logoutUser(); }}>Log out</button>
    </section>
  </div>}</RequireAuth>;
}

