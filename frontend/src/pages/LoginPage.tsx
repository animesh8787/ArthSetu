import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff, Network } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { friendlyAuthError } from "@/lib/auth";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Field";

export function LoginPage() {
  useDocumentTitle("Sign in");
  const { user, loading, login, resetPassword } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState(false);

  if (!loading && user) return <Navigate to={next} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await login(email.trim(), password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setBusy(false);
    }
  }

  async function forgotPassword() {
    const trimmed = email.trim();
    if (!trimmed) {
      setError("Enter your email address first, then click “Forgot password?” again.");
      return;
    }
    setResetting(true);
    setError(null);
    setInfo(null);
    try {
      await resetPassword(trimmed);
      setInfo(`Password reset email sent to ${trimmed} — check your inbox.`);
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-white">
            <Network className="h-5 w-5" />
          </div>
          <div>
            <div className="text-base font-semibold text-ink">ArthSetu</div>
            <div className="text-[12px] text-ink-subtle">
              Business Intelligence Console
            </div>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-lg border border-line bg-surface p-5 shadow-card"
        >
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="pr-9"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-ink-subtle hover:text-ink"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            <button
              type="button"
              onClick={forgotPassword}
              disabled={resetting}
              className="mt-1.5 text-[12px] font-medium text-brand hover:underline disabled:cursor-not-allowed disabled:opacity-50"
            >
              {resetting ? "Sending…" : "Forgot password?"}
            </button>
          </div>

          {error && (
            <p className="rounded-md bg-danger/10 px-3 py-2 text-[13px] text-danger">
              {error}
            </p>
          )}
          {info && (
            <p className="rounded-md bg-brand/10 px-3 py-2 text-[13px] text-brand">
              {info}
            </p>
          )}

          <Button type="submit" className="w-full" loading={busy}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
