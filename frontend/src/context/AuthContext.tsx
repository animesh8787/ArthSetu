import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { authApi } from "@/api/endpoints";
import { auth } from "@/lib/firebase";
import type { Role, User } from "@/types/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  can: (min: Role) => boolean;
  resetPassword: (email: string) => Promise<void>;
}

const RANK: Record<Role, number> = { viewer: 0, reviewer: 1, admin: 2 };

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetches the local ArthSetu profile for the currently signed-in Firebase
  // user. Throws (and clears `user`) if there isn't one — e.g. a Firebase
  // account that exists but was never provisioned by an admin.
  const syncProfile = useCallback(async () => {
    try {
      const profile = await authApi.me();
      setUser(profile);
      return profile;
    } catch (err) {
      setUser(null);
      throw err;
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      if (!fbUser) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        await syncProfile();
      } catch {
        // Verified Firebase session but no ArthSetu profile (or the backend
        // was unreachable) — sign out of Firebase too so state stays
        // consistent rather than "signed in" with no usable profile.
        await signOut(auth);
      } finally {
        setLoading(false);
      }
    });
    return unsubscribe;
  }, [syncProfile]);

  const login = useCallback(
    async (email: string, password: string) => {
      await signInWithEmailAndPassword(auth, email, password);
      try {
        await syncProfile();
      } catch (err) {
        await signOut(auth);
        throw err;
      }
    },
    [syncProfile],
  );

  const logout = useCallback(() => {
    signOut(auth);
    window.location.assign("/login");
  }, []);

  const refresh = useCallback(async () => {
    if (!auth.currentUser) return;
    try {
      await syncProfile();
    } catch {
      await signOut(auth);
    }
  }, [syncProfile]);

  const resetPassword = useCallback(
    (email: string) => sendPasswordResetEmail(auth, email),
    [],
  );

  const can = useCallback(
    (min: Role) => !!user && RANK[user.role] >= RANK[min],
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh, can, resetPassword }),
    [user, loading, login, logout, refresh, can, resetPassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
