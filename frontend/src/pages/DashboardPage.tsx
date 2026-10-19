import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Refresh } from "@/components/icons";
import { analyticsApi, dashboardApi, statusApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { EntityStatus } from "@/lib/format";
import { formatNumber, formatPercent } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { isJobTerminal, useJobPolling } from "@/hooks/useJobPolling";
import { StatusBreakdown } from "@/components/dashboard/StatusBreakdown";
import { TopDistricts } from "@/components/dashboard/TopDistricts";
import { AuditFeed } from "@/components/AuditFeed";

const ActivityTrendChart = lazy(
  () => import("@/components/charts/ActivityTrendChart"),
);

export function DashboardPage() {
  useDocumentTitle("Dashboard");
  const { notify } = useToast();
  const { can } = useAuth();

  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const trends = useQuery({ queryKey: ["trends"], queryFn: analyticsApi.trends });
  const districts = useQuery({
    queryKey: ["districts"],
    queryFn: analyticsApi.districts,
  });

  // Recompute-all runs as a background job (see status_run_all in
  // Docs/API_CONTRACT.md) so it doesn't block the request — the button
  // queues it, then this page polls for completion.
  const [recomputeJobId, setRecomputeJobId] = useState<string | null>(null);
  const recomputeJob = useJobPolling(recomputeJobId);

  const recompute = useMutation({
    mutationFn: statusApi.runAll,
    onSuccess: (job) => {
      setRecomputeJobId(job.id);
      notify("success", "Status recompute queued");
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Recompute failed"),
  });

  useEffect(() => {
    const job = recomputeJob.data;
    if (!job || !isJobTerminal(job.status)) return;
    if (job.status === "succeeded") {
      const processed = (job.result as { processed?: number } | null)?.processed;
      notify("success", `Recomputed status for ${processed ?? "all"} businesses`);
      queryClient.invalidateQueries();
    } else {
      notify("error", job.error ?? "Status recompute failed");
    }
    setRecomputeJobId(null);
  }, [recomputeJob.data, notify]);

  const recomputeRunning =
    recompute.isPending || (!!recomputeJobId && !isJobTerminal(recomputeJob.data?.status ?? "pending"));

  const d = dashboard.data;
  const counts: Record<EntityStatus, number> = {
    active: d?.active ?? 0,
    dormant: d?.dormant ?? 0,
    closed: d?.closed ?? 0,
    unknown: d?.unknown ?? 0,
  };

  return (
    <div>
      <PageHeader
        title="Executive Dashboard"
        description="System-wide view of business identity and activity intelligence."
        actions={
          can("admin") ? (
            <Button
              variant="secondary"
              size="sm"
              loading={recomputeRunning}
              disabled={recomputeRunning}
              onClick={() => recompute.mutate()}
            >
              <Refresh className="h-3.5 w-3.5" />
              Recompute statuses
            </Button>
          ) : undefined
        }
      />

      {dashboard.isError ? (
        <Card>
          <ErrorState
            message={(dashboard.error as unknown as ApiError)?.message}
            onRetry={() => dashboard.refetch()}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total businesses" value={formatNumber(d?.total_businesses)} to="/businesses" accent="brand" loading={dashboard.isLoading} />
            <StatCard label="Active" value={formatNumber(d?.active)} to="/businesses?status=active" accent="ok" loading={dashboard.isLoading} />
            <StatCard label="Dormant" value={formatNumber(d?.dormant)} to="/businesses?status=dormant" accent="warn" loading={dashboard.isLoading} />
            <StatCard label="Closed" value={formatNumber(d?.closed)} to="/businesses?status=closed" accent="danger" loading={dashboard.isLoading} />
          </div>

          <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Pending reviews" value={formatNumber(d?.pending_reviews)} to="/reviews" loading={dashboard.isLoading} />
            <StatCard label="Record links" value={formatNumber(d?.total_links)} loading={dashboard.isLoading} />
            <StatCard label="Auto-match rate" value={formatPercent(d?.auto_match_rate)} hint="Resolved without human review" loading={dashboard.isLoading} />
            <StatCard label="Unclassified" value={formatNumber(d?.unknown)} hint="Awaiting status inference" loading={dashboard.isLoading} />
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Activity trend"
                description="Operational signals ingested per month"
              />
              <CardBody>
                {trends.isLoading ? (
                  <Skeleton className="h-56 w-full" />
                ) : trends.isError ? (
                  <ErrorState onRetry={() => trends.refetch()} />
                ) : (
                  <Suspense fallback={<Skeleton className="h-56 w-full" />}>
                    <ActivityTrendChart data={trends.data ?? []} />
                  </Suspense>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Status breakdown" description="Share of business lifecycle states" />
              <CardBody>
                {dashboard.isLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-7 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </div>
                ) : (
                  <StatusBreakdown counts={counts} />
                )}
              </CardBody>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <Card>
              <CardHeader
                title="Top districts"
                description="By registered businesses"
              />
              <CardBody>
                {districts.isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-8 w-full" />
                    ))}
                  </div>
                ) : districts.isError ? (
                  <ErrorState onRetry={() => districts.refetch()} />
                ) : (
                  <TopDistricts rows={districts.data ?? []} />
                )}
              </CardBody>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader
                title="Recent operations"
                description="Live audit trail: every automated and reviewer action"
              />
              <CardBody>
                <AuditFeed limit={9} />
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
