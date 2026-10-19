import { useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, X } from "@/components/icons";
import { reviewApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { ReviewCaseItem } from "@/types/api";
import { useAuth } from "@/context/AuthContext";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { formatNumber, relativeTime } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/Toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 15;
const FILTER_KEYS = ["status"] as const;

const TABS = [
  { value: "open", label: "Open" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

function confidenceTone(c: number | null): "ok" | "warn" | "danger" {
  if (c == null) return "danger";
  if (c >= 0.8) return "ok";
  if (c >= 0.68) return "warn";
  return "danger";
}

export function ReviewQueuePage() {
  useDocumentTitle("Review Queue");
  const { notify } = useToast();
  const { can } = useAuth();
  const canReview = can("reviewer");
  const { values, offset, setFilter, setOffset } = useUrlFilters(FILTER_KEYS);
  const tab = values.status || "open"; // "open" | "approved" | "rejected" | "all"
  const apiStatus = tab === "all" ? undefined : tab;

  const openCount = useQuery({
    queryKey: ["reviews", "count", "open"],
    queryFn: () => reviewApi.list({ status: "open", limit: 1 }),
    select: (d) => d.total,
  });

  const params = {
    status: apiStatus,
    limit: PAGE_SIZE,
    offset,
  };
  const { data, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ["reviews", params],
    queryFn: () => reviewApi.list(params),
    placeholderData: keepPreviousData,
  });

  const [pending, setPending] = useState<Record<string, "approve" | "reject">>({});

  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      action === "approve" ? reviewApi.approve(id) : reviewApi.reject(id),
    onMutate: ({ id, action }) => setPending((p) => ({ ...p, [id]: action })),
    onSuccess: (_res, { action }) => {
      notify(
        "success",
        action === "approve"
          ? "Review approved: link confirmed"
          : "Review rejected: record given its own identity",
      );
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Action failed"),
    onSettled: (_r, _e, { id }) =>
      setPending((p) => {
        const next = { ...p };
        delete next[id];
        return next;
      }),
  });

  return (
    <div>
      <PageHeader
        title="Review Queue"
        description="Human-in-the-loop review of uncertain record links."
        actions={
          !canReview ? (
            <span className="flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-[12px] text-ink-muted">
              Read-only: reviewer role required to act
            </span>
          ) : undefined
        }
      />

      <div className="mb-3 flex flex-wrap gap-1 rounded-md border border-line bg-surface p-1 sm:inline-flex">
        {TABS.map((t) => {
          const isActive = t.value === tab;
          return (
            <button
              key={t.value}
              onClick={() => setFilter({ status: t.value })}
              className={cn(
                "flex items-center gap-1.5 rounded px-3 py-1.5 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-brand-soft text-brand"
                  : "text-ink-muted hover:bg-surface-muted hover:text-ink",
              )}
              aria-pressed={isActive}
            >
              {t.label}
              {t.value === "open" && openCount.data != null && (
                <Badge tone={isActive ? "brand" : "neutral"}>
                  {formatNumber(openCount.data)}
                </Badge>
              )}
            </button>
          );
        })}
      </div>

      {isError ? (
        <Card>
          <ErrorState
            message={(error as unknown as ApiError)?.message}
            onRetry={() => refetch()}
          />
        </Card>
      ) : isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardBody>
                <Skeleton className="h-24 w-full" />
              </CardBody>
            </Card>
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            title={tab === "open" ? "Queue is clear" : "Nothing here"}
            description={
              tab === "open"
                ? "Every uncertain link has been reviewed."
                : "No review cases match this filter."
            }
          />
        </Card>
      ) : (
        <div className={cn("space-y-3", isFetching && "opacity-60")}>
          {data.items.map((c) => (
            <ReviewCard
              key={c.review_id}
              c={c}
              canReview={canReview}
              pending={pending[c.review_id]}
              onApprove={() =>
                decide.mutate({ id: c.review_id, action: "approve" })
              }
              onReject={() =>
                decide.mutate({ id: c.review_id, action: "reject" })
              }
            />
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="mt-3">
          <Pagination
            total={data.total}
            limit={PAGE_SIZE}
            offset={offset}
            onChange={setOffset}
          />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ReviewCard({
  c,
  canReview,
  pending,
  onApprove,
  onReject,
}: {
  c: ReviewCaseItem;
  canReview: boolean;
  pending?: "approve" | "reject";
  onApprove: () => void;
  onReject: () => void;
}) {
  const reasons = c.evidence?.reasons ?? [];
  const isOpen = c.status === "open";

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={confidenceTone(c.confidence)}>
            {c.confidence != null ? `${Math.round(c.confidence * 100)}% match` : "no score"}
          </Badge>
          {!isOpen && (
            <Badge tone={c.status === "approved" ? "ok" : "danger"}>
              {c.status === "approved" ? "Approved" : "Rejected"}
            </Badge>
          )}
          <span className="ml-auto text-[12px] text-ink-subtle">
            raised {relativeTime(c.created_at)}
          </span>
        </div>

        <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-[1fr_auto_1fr]">
          <div className="rounded-md border border-line bg-surface-muted px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-subtle">
              Source record
            </div>
            <div className="mt-0.5 text-sm font-medium text-ink">
              {c.extracted_name || "–"}
            </div>
            <div className="text-[12px] text-ink-muted">
              {c.source_system || "Unknown system"}
            </div>
          </div>

          <ArrowRight className="mx-auto hidden h-4 w-4 text-ink-subtle sm:block" />

          <div className="rounded-md border border-brand/30 bg-brand-soft/40 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-ink-subtle">
              Proposed identity
            </div>
            <div className="mt-0.5 text-sm font-medium text-ink">
              {c.candidate_ubid ? (
                <Link
                  to={`/businesses/${c.candidate_ubid}`}
                  className="hover:text-brand hover:underline"
                >
                  {c.candidate_name || c.candidate_ubid}
                </Link>
              ) : (
                c.candidate_name || "–"
              )}
            </div>
            <div className="font-mono text-[12px] text-ink-muted">
              {c.candidate_ubid || "–"}
            </div>
          </div>
        </div>

        {reasons.length > 0 && (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-muted">
            {reasons.map((r, i) => (
              <li key={i} className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-sm bg-ink-subtle" aria-hidden />
                {r}
              </li>
            ))}
          </ul>
        )}

        {isOpen && canReview ? (
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              onClick={onApprove}
              loading={pending === "approve"}
              disabled={!!pending}
            >
              <Check className="h-3.5 w-3.5" />
              Approve &amp; link
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={onReject}
              loading={pending === "reject"}
              disabled={!!pending}
            >
              <X className="h-3.5 w-3.5" />
              Reject
            </Button>
          </div>
        ) : isOpen ? (
          <p className="text-[12px] text-ink-subtle">Awaiting reviewer decision.</p>
        ) : (
          <p className="text-[12px] text-ink-subtle">
            {c.status === "approved" ? "Approved" : "Rejected"}
            {c.reviewer_id && ` by ${c.reviewer_id}`}
            {c.decided_at && ` · ${relativeTime(c.decided_at)}`}
          </p>
        )}
      </CardBody>
    </Card>
  );
}
