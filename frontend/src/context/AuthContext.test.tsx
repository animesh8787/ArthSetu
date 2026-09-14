import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { User } from "@/types/api";

const meMock = vi.fn();
const signInMock = vi.fn();
const signOutMock = vi.fn();
const resetPasswordMock = vi.fn();

vi.mock("@/api/endpoints", () => ({
  authApi: { me: () => meMock() },
}));

vi.mock("@/lib/firebase", () => ({ auth: {} }));

type AuthStateCallback = (user: { uid: string } | null) => void;
let authStateCallback: AuthStateCallback | null = null;

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: (_auth: unknown, cb: AuthStateCallback) => {
    authStateCallback = cb;
    return () => {};
  },
  signInWithEmailAndPassword: (...args: unknown[]) => signInMock(...args),
  signOut: (...args: unknown[]) => signOutMock(...args),
  sendPasswordResetEmail: (...args: unknown[]) => resetPasswordMock(...args),
}));

import { AuthProvider, useAuth } from "./AuthContext";

const reviewer: User = {
  id: "1",
  full_name: "Reviewer",
  email: "reviewer@test.local",
  role: "reviewer",
  is_active: true,
  is_bootstrap: false,
  created_at: null,
};

function Probe() {
  const { user, loading, login, can } = useAuth();
  if (loading) return <span>loading</span>;
  return (
    <div>
      <span data-testid="user">{user ? user.email : "anon"}</span>
      <span data-testid="can-viewer">{String(can("viewer"))}</span>
      <span data-testid="can-reviewer">{String(can("reviewer"))}</span>
      <span data-testid="can-admin">{String(can("admin"))}</span>
      <button onClick={() => login("reviewer@test.local", "pw")}>login</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    meMock.mockReset();
    signInMock.mockReset();
    signOutMock.mockReset();
    resetPasswordMock.mockReset();
    authStateCallback = null;
  });

  it("starts anonymous when Firebase reports no signed-in user", async () => {
    renderProbe();
    await waitFor(() => expect(authStateCallback).not.toBeNull());
    await act(async () => authStateCallback!(null));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("anon"));
    expect(meMock).not.toHaveBeenCalled();
  });

  it("loads the profile from /me when Firebase reports a signed-in user", async () => {
    meMock.mockResolvedValue(reviewer);
    renderProbe();
    await waitFor(() => expect(authStateCallback).not.toBeNull());
    await act(async () => authStateCallback!({ uid: "fb-uid-1" }));
    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("reviewer@test.local"),
    );
  });

  it("signs out of Firebase when a verified user has no local profile", async () => {
    meMock.mockRejectedValue({ status: 403, message: "no profile" });
    renderProbe();
    await waitFor(() => expect(authStateCallback).not.toBeNull());
    await act(async () => authStateCallback!({ uid: "fb-uid-1" }));
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("anon"));
    expect(signOutMock).toHaveBeenCalled();
  });

  it("login signs in via Firebase and loads the profile", async () => {
    signInMock.mockResolvedValue(undefined);
    meMock.mockResolvedValue(reviewer);
    renderProbe();
    await waitFor(() => expect(authStateCallback).not.toBeNull());
    await act(async () => authStateCallback!(null));
    await waitFor(() => screen.getByText("login"));

    await userEvent.click(screen.getByText("login"));
    expect(signInMock).toHaveBeenCalledWith({}, "reviewer@test.local", "pw");
    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("reviewer@test.local"),
    );
  });

  it("can() respects the role hierarchy", async () => {
    meMock.mockResolvedValue(reviewer);
    renderProbe();
    await waitFor(() => expect(authStateCallback).not.toBeNull());
    await act(async () => authStateCallback!({ uid: "fb-uid-1" }));
    await waitFor(() =>
      expect(screen.getByTestId("user")).toHaveTextContent("reviewer@test.local"),
    );
    expect(screen.getByTestId("can-viewer")).toHaveTextContent("true");
    expect(screen.getByTestId("can-reviewer")).toHaveTextContent("true");
    expect(screen.getByTestId("can-admin")).toHaveTextContent("false");
  });
});
