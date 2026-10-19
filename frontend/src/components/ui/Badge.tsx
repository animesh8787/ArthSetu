import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { statusMeta } from "@/lib/format";

type Tone = "ok" | "warn" | "danger" | "neutral" | "brand";

const tones: Record<Tone, string> = {
  ok: "border-ok text-ok",
  warn: "border-warn text-warn",
  danger: "border-danger text-danger",
  neutral: "border-line text-ink-muted",
  brand: "border-brand text-brand",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium border",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta(status);
  return (
    <Badge tone={meta.tone}>
      <span
        className={cn("h-1.5 w-1.5 rounded-sm", {
          "bg-ok": meta.tone === "ok",
          "bg-warn": meta.tone === "warn",
          "bg-danger": meta.tone === "danger",
          "bg-ink-subtle": meta.tone === "neutral",
        })}
        aria-hidden
      />
      {meta.label}
    </Badge>
  );
}
