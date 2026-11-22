import type { TokenResponse } from "@/src/types/user";

const KEY = "smartrecipe.session";
export const SESSION_CHANGED = "smartrecipe-session-changed";
type Session = { token: string; expiresAt: number };

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const session = JSON.parse(sessionStorage.getItem(KEY) || "null");
    if (typeof session?.token !== "string" || !session.token ||
        !Number.isFinite(session.expiresAt) || session.expiresAt <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export function saveSession(response: TokenResponse) {
  if (!response.access_token || response.token_type.toLowerCase() !== "bearer" ||
      !Number.isFinite(response.expires_in) || response.expires_in <= 0) {
    throw new Error("The server returned an invalid login response.");
  }
  try {
    sessionStorage.setItem(KEY, JSON.stringify({
      token: response.access_token,
      expiresAt: Date.now() + response.expires_in * 1000,
    }));
  } catch {
    throw new Error("Allow session storage in your browser to sign in.");
  }
  window.dispatchEvent(new Event(SESSION_CHANGED));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  try { sessionStorage.removeItem(KEY); } catch { /* Storage may be disabled. */ }
  window.dispatchEvent(new Event(SESSION_CHANGED));
}

