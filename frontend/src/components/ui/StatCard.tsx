import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";
import { Skeleton } from "./Skeleton";

export function StatCard({
  label,
  value,
  hint,
  to,
  accent = "neutral",
  loading,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  to?: string;
  accent?: "neutral" | "ok" | "warn" | "danger" | "brand";
  loading?: boolean;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-ink-muted">{label}</span>
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <div
          className={cn("mt-1.5 text-2xl font-semibold tabular-nums", {
            "text-ink": accent === "neutral" || accent === "brand",
            "text-ok": accent === "ok",
            "text-warn": accent === "warn",
            "text-danger": accent === "danger",
          })}
        >
          {value}
        </div>
      )}
      {hint && <div className="mt-1 text-[12px] text-ink-subtle">{hint}</div>}
    </>
  );

  const className = cn(
    "group block rounded-md border border-line bg-surface p-4",
    to && "hover:border-ink-subtle",
    accent === "brand" && "border-brand",
  );

  return to ? (
    <Link to={to} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}
