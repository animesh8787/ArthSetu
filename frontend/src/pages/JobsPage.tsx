import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { jobsApi } from "@/api/endpoints";
import { formatDateTime, titleCase } from "@/lib/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/States";
import type { Job, JobStatus } from "@/types/api";

const STATUS_TONE: Record<JobStatus, "ok" | "warn" | "danger" | "neutral"> = {
  pending: "neutral",
  running: "warn",
  succeeded: "ok",
  failed: "danger",
};

const TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "status_run_all", label: "Status recompute" },
  { value: "process_pending", label: "Process pending" },
  { value: "csv_match", label: "CSV matching" },
  { value: "sync_connectors", label: "Connector sync" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
];

function resultSummary(job: Job): string | null {
  if (!job.result || typeof job.result !== "object") return null;
  const r = job.result as Record<string, unknown>;
  const parts: string[] = [];
  for (const key of ["processed", "auto_link", "review", "new_entity", "active", "dormant", "closed", "failed"]) {
    if (typeof r[key] === "number" && r[key] !== 0) parts.push(`${key.replace("_", " ")}: ${r[key]}`);
  }
  return parts.length ? parts.join(" · ") : null;
}

export function JobsPage() {
  useDocumentTitle("Background Jobs");
  const [jobType, setJobType] = useState("");
  const [status, setStatus] = useState("");

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["jobs", jobType, status],
    queryFn: () =>
      jobsApi.list({
        job_type: jobType || undefined,
        status: status || undefined,
        limit: 50,
      }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const active = items.some((j) => j.status === "pending" || j.status === "running");
      return active ? 2500 : false;
    },
  });

  return (
    <div className="space-y-3">
      <PageHeader
        title="Background Jobs"
        description="Batch status recompute and bulk matching run off the request thread — track them here."
        actions={
          <Button variant="ghost" size="sm" loading={isFetching} onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Select
          options={TYPE_OPTIONS}
          value={jobType}
          onChange={(e) => setJobType(e.target.value)}
          className="h-8 w-48 text-[13px]"
        />
        <Select
          options={STATUS_OPTIONS}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-8 w-40 text-[13px]"
        />
      </div>

      <Card>
        {isLoading ? (
          <div className="p-4">
            <Skeleton className="h-40 w-full" />
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !data?.items.length ? (
          <EmptyState title="No jobs found" description="No jobs match these filters." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th className="w-24">Status</Th>
                <Th>Result</Th>
                <Th className="w-28">Queued by</Th>
                <Th className="w-40">Created</Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((job) => (
                <Tr key={job.id}>
                  <Td className="font-medium text-ink">{titleCase(job.job_type)}</Td>
                  <Td>
                    <Badge tone={STATUS_TONE[job.status]}>{titleCase(job.status)}</Badge>
                  </Td>
                  <Td className="text-[12px] text-ink-muted">
                    {job.status === "failed" ? (
                      <span className="text-danger">{job.error}</span>
                    ) : (
                      resultSummary(job) ?? "—"
                    )}
                  </Td>
                  <Td className="text-[12px] text-ink-muted">{job.created_by ?? "—"}</Td>
                  <Td className="text-[12px] text-ink-muted">{formatDateTime(job.created_at)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
