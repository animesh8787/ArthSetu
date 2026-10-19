import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Menu } from "@/components/icons";
import { healthApi } from "@/api/endpoints";
import { useAuth } from "@/context/AuthContext";
import { GlobalSearch } from "@/components/GlobalSearch";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/cn";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.get,
    refetchInterval: 30_000,
  });
  const online = !isError && data?.status === "ok";

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 sm:px-5">
      <button
        onClick={onMenuClick}
        className="rounded-md p-1.5 text-ink-muted hover:text-ink lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <GlobalSearch />

      <div className="ml-auto flex items-center gap-3 text-[12px]">
        <span className="flex items-center gap-1.5 text-ink-muted">
          <span
            className={cn("h-2 w-2 rounded-sm", online ? "bg-ok" : "bg-danger")}
            aria-hidden
          />
          <span className="hidden sm:inline">
            {online ? "API online" : "API offline"}
          </span>
        </span>

        {user && (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-muted"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-md border border-line bg-surface-muted text-[11px] font-semibold text-ink" aria-hidden>
                {user.full_name
                  .split(" ")
                  .map((w) => w[0])
                  .slice(0, 2)
                  .join("")
                  .toUpperCase()}
              </span>
              <span className="hidden text-left sm:block">
                <span className="block text-[13px] font-medium leading-none text-ink">
                  {user.full_name}
                </span>
                <span className="block text-[11px] leading-none text-ink-subtle">
                  {titleCase(user.role)}
                </span>
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-ink-subtle" />
            </button>

            {menuOpen && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setMenuOpen(false)}
                  aria-hidden
                />
                <div className="absolute right-0 z-40 mt-1.5 w-52 rounded-md border border-ink-subtle bg-surface py-1">
                  <div className="border-b border-line px-3 py-2">
                    <div className="text-[13px] font-medium text-ink">
                      {user.full_name}
                    </div>
                    <div className="text-[12px] text-ink-subtle">
                      {user.email} · {titleCase(user.role)}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-[13px] text-ink-muted hover:bg-surface-muted hover:text-ink"
                  >
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
