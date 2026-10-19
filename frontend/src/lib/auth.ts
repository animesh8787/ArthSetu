import { FirebaseError } from "firebase/app";
import { auth } from "./firebase";

// Firebase persists its own session (IndexedDB) — nothing to store manually.
// getIdToken() returns null when signed out, and transparently refreshes an
// expiring token when signed in.
export function getIdToken(): Promise<string | null> {
  return auth.currentUser ? auth.currentUser.getIdToken() : Promise.resolve(null);
}

const FIREBASE_ERROR_MESSAGES: Record<string, string> = {
  "auth/invalid-email": "That doesn't look like a valid email address.",
  "auth/user-disabled": "This account has been disabled.",
  "auth/user-not-found": "Incorrect email or password.",
  "auth/wrong-password": "Incorrect email or password.",
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/too-many-requests": "Too many attempts. Try again in a few minutes.",
  "auth/network-request-failed": "Network error. Check your connection and try again.",
};

// Login/reset-password can fail with either a Firebase SDK error (sign-in
// itself) or an already-normalized ApiError from lib/api.ts (e.g. /auth/me
// 403ing for a verified account with no local profile) — this covers both.
export function friendlyAuthError(err: unknown): string {
  if (err instanceof FirebaseError) {
    return FIREBASE_ERROR_MESSAGES[err.code] ?? "Sign in failed.";
  }
  if (err && typeof err === "object" && "message" in err) {
    const message = (err as { message: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  return "Sign in failed.";
}
