import { useQuery } from "@tanstack/react-query";
import { auditApi, type AuditParams } from "@/api/endpoints";
import { describeAudit } from "@/lib/audit";
import { relativeTime, titleCase } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";

const toneDot: Record<string, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  danger: "bg-danger",
  brand: "bg-brand",
  neutral: "bg-ink-subtle",
};

export function AuditFeed({
  params = {},
  limit = 8,
  emptyLabel = "No operations recorded yet.",
}: {
  params?: AuditParams;
  limit?: number;
  emptyLabel?: string;
}) {
  const query = { ...params, limit };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["audit", query],
    queryFn: () => auditApi.list(query),
    refetchInterval: 15_000, // live feed: new actions appear without a reload
  });

  if (isLoading) {
    return (
      <ul className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <li key={i} className="flex gap-3">
            <Skeleton className="mt-1.5 h-2 w-2 shrink-0" />
            <div className="flex-1 space-y-1.5 py-0.5">
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="h-2.5 w-1/3" />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!data || data.items.length === 0) {
    return <EmptyState title="Nothing here yet" description={emptyLabel} />;
  }

  return (
    <ul className="divide-y divide-line">
      {data.items.map((entry) => {
        const view = describeAudit(entry);
        const actor =
          entry.actor_id ?? titleCase(entry.actor_type ?? "system");
        return (
          <li key={entry.id} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
            <span className={cn("mt-1.5 h-2 w-2 shrink-0", toneDot[view.tone])} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] text-ink">
                {view.title}
                {view.detail && (
                  <span className="text-ink-muted"> · {view.detail}</span>
                )}
              </p>
              <p className="mt-0.5 text-[12px] text-ink-subtle">
                {actor} · {relativeTime(entry.created_at)}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
