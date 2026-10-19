import { useMutation, useQuery } from "@tanstack/react-query";
import { correctionsApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import { relativeTime, titleCase } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";

export function CorrectionsPage() {
  useDocumentTitle("Corrections");
  const { notify } = useToast();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["corrections"],
    queryFn: () => correctionsApi.history({ limit: 50 }),
  });

  const undo = useMutation({
    mutationFn: correctionsApi.undo,
    onSuccess: (r) => {
      notify("success", r.message);
      queryClient.invalidateQueries();
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Undo failed"),
  });

  return (
    <div>
      <PageHeader
        title="Corrections"
        description="Reviewer edits to the identity graph; each one is reversible."
      />

      <Card>
        {isLoading ? (
          <div className="p-4">
            <Skeleton className="h-40 w-full" />
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="No corrections yet"
            description="Splits, status overrides and event reassignments show up here."
          />
        ) : (
          <ul className="divide-y divide-line">
            {data.items.map((c) => (
              <li
                key={c.audit_id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3"
              >
                <span className="text-[13px] text-ink">{c.summary}</span>
                {c.undone && <Badge tone="neutral">Undone</Badge>}
                {c.action === "CORRECTION_UNDONE" && (
                  <Badge tone="brand">Undo</Badge>
                )}
                {c.reason && (
                  <span className="text-[12px] italic text-ink-muted">
                    “{c.reason}”
                  </span>
                )}
                <span className="ml-auto text-[12px] text-ink-subtle">
                  {c.actor_id ? titleCase(c.actor_id) : "system"} ·{" "}
                  {relativeTime(c.created_at)}
                </span>
                {c.reversible && (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={undo.isPending && undo.variables === c.audit_id}
                    onClick={() => undo.mutate(c.audit_id)}
                  >
                    Undo
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
