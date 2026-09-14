import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Role, User } from "@/types/api";

const authState: {
  user: User | null;
  loading: boolean;
} = { user: null, loading: false };

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    ...authState,
    can: (min: Role) => {
      const rank = { viewer: 0, reviewer: 1, admin: 2 };
      return !!authState.user && rank[authState.user.role] >= rank[min];
    },
  }),
}));

import { RequireAuth } from "./RequireAuth";

const viewer: User = {
  id: "1", full_name: "V", email: "v@test.local",
  role: "viewer", is_active: true, is_bootstrap: false, created_at: null,
};

function renderAt(path: string, role?: Role) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>login page</div>} />
        <Route
          path="/secret"
          element={
            <RequireAuth role={role}>
              <div>secret content</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  it("shows a spinner while auth is loading", () => {
    authState.user = null;
    authState.loading = true;
    renderAt("/secret");
    expect(screen.queryByText("secret content")).toBeNull();
    expect(screen.queryByText("login page")).toBeNull();
  });

  it("redirects anonymous users to /login", () => {
    authState.user = null;
    authState.loading = false;
    renderAt("/secret");
    expect(screen.getByText("login page")).toBeInTheDocument();
  });

  it("renders children for an authenticated user", () => {
    authState.user = viewer;
    authState.loading = false;
    renderAt("/secret");
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("blocks a viewer from an admin-only area", () => {
    authState.user = viewer;
    authState.loading = false;
    renderAt("/secret", "admin");
    expect(screen.queryByText("secret content")).toBeNull();
    expect(screen.getByText(/access restricted/i)).toBeInTheDocument();
  });
});
