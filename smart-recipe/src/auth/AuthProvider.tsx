"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError } from "@/src/api/client";
import { getAuthenticatedProfile } from "@/src/services/authService";
import { clearSession, readSession, SESSION_CHANGED } from "./session";
import type { AuthProfile } from "@/src/types/user";

type AuthState = {
  user: AuthProfile | null;
  loading: boolean;
  error: string;
  retry: () => void;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<AuthState, "retry">>({
    user: null, loading: true, error: "",
  });

  useEffect(() => {
    let controller: AbortController | undefined;
    let expiryTimer: ReturnType<typeof setTimeout> | undefined;
    let inactivityTimer: ReturnType<typeof setTimeout> | undefined;

    function resetInactivity() {
      clearTimeout(inactivityTimer);
      if (readSession()) inactivityTimer = setTimeout(clearSession, 15 * 60 * 1000);
    }

    async function load() {
      controller?.abort();
      clearTimeout(expiryTimer);
      clearTimeout(inactivityTimer);
      const session = readSession();
      if (!session) {
        setState({ user: null, loading: false, error: "" });
        return;
      }
      controller = new AbortController();
      const signal = controller.signal;
      setState({ user: null, loading: true, error: "" });
      expiryTimer = setTimeout(clearSession, Math.min(session.expiresAt - Date.now(), 2147483647));
      resetInactivity();
      try {
        const user = await getAuthenticatedProfile(signal);
        if (!signal.aborted) setState({ user, loading: false, error: "" });
      } catch (error) {
        if (signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) {
          clearSession();
        } else {
          setState({ user: null, loading: false, error: "Could not load your profile. Check your connection and try again." });
        }
      }
    }

    function checkSession() {
      if (!readSession()) clearSession();
    }
    window.addEventListener(SESSION_CHANGED, load);
    window.addEventListener("focus", checkSession);
    window.addEventListener("pointerdown", resetInactivity);
    window.addEventListener("keydown", resetInactivity);
    load();
    return () => {
      controller?.abort();
      clearTimeout(expiryTimer);
      clearTimeout(inactivityTimer);
      window.removeEventListener(SESSION_CHANGED, load);
      window.removeEventListener("focus", checkSession);
      window.removeEventListener("pointerdown", resetInactivity);
      window.removeEventListener("keydown", resetInactivity);
    };
  }, []);

  function retry() {
    window.dispatchEvent(new Event(SESSION_CHANGED));
  }

  return <AuthContext.Provider value={{ ...state, retry }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}

