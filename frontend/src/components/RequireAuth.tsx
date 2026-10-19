import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/types/api";
import { Spinner } from "@/components/icons";
import { Button } from "@/components/ui/Button";

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <Spinner className="h-6 w-6 animate-spin text-ink-subtle" />
    </div>
  );
}

export function RequireAuth({
  children,
  role,
}: {
  children: ReactNode;
  role?: Role;
}) {
  const { user, loading, can } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageSpinner />;

  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (role && !can(role)) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <p className="text-lg font-semibold text-ink">Access restricted</p>
        <p className="text-[13px] text-ink-muted">
          This area requires the <span className="font-medium">{role}</span> role.
          You're signed in as <span className="font-medium">{user.role}</span>.
        </p>
        <Button variant="secondary" size="sm" onClick={() => history.back()}>
          Go back
        </Button>
      </div>
    );
  }

  return <>{children}</>;
}
