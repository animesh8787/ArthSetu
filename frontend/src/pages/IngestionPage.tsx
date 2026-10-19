import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Refresh, Upload } from "@/components/icons";
import { ingestApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { EventsReport, IngestionReport, MatchingTally, SourceSystem } from "@/types/api";
import { useAuth } from "@/context/AuthContext";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { isJobTerminal, useJobPolling } from "@/hooks/useJobPolling";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input, Select } from "@/components/ui/Field";
import { Table, Td, Th } from "@/components/ui/Table";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";

function TallyRow({ tally }: { tally: { auto_link: number; review: number; new_entity: number; failed: number } }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Badge tone="brand">{formatNumber(tally.auto_link)} auto-linked</Badge>
      <Badge tone="warn">{formatNumber(tally.review)} to review</Badge>
      <Badge tone="neutral">{formatNumber(tally.new_entity)} new identities</Badge>
      {tally.failed > 0 && (
        <Badge tone="danger">{formatNumber(tally.failed)} failed</Badge>
      )}
    </div>
  );
}

function ConnectorRow({ system, onChanged }: { system: SourceSystem; onChanged: () => void }) {
  const { notify } = useToast();
  const [url, setUrl] = useState(system.pull_url ?? "");
  const [kind, setKind] = useState<"records" | "events">(system.pull_kind ?? "records");
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobPolling(jobId);

  const save = useMutation({
    mutationFn: (next: string | null) => ingestApi.setConnector(system.code, next, kind),
    onSuccess: (_s, next) => {
      notify("success", next ? "Connector saved" : "Connector removed");
      if (!next) setUrl("");
      onChanged();
    },
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Could not save"),
  });
  const sync = useMutation({
    mutationFn: () => ingestApi.syncConnector(system.code),
    onSuccess: (j) => {
      setJobId(j.id);
      notify("success", "Sync started");
    },
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Could not start sync"),
  });

  useEffect(() => {
    if (job.data && isJobTerminal(job.data.status)) {
      setJobId(null);
      onChanged();
    }
  }, [job.data]);

  const running = sync.isPending || (!!jobId && !isJobTerminal(job.data?.status ?? "pending"));
  const dirty = url !== (system.pull_url ?? "") || kind !== (system.pull_kind ?? "records");

  return (
    <div className="space-y-2 border-t border-line px-4 py-3 first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[12px] text-ink">{system.code}</span>
        <span className="text-[13px] text-ink-muted">{system.department}</span>
        {system.last_pull_status && (
          <span className="ml-auto text-[12px] text-ink-subtle">
            {formatDateTime(system.last_pull_at)} · {system.last_pull_status}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://department.example/export.csv (CSV or JSON, public https only)"
          aria-label={`Connector URL for ${system.code}`}
          className="min-w-[260px] flex-1"
        />
        <Select
          options={[
            { value: "records", label: "Business records" },
            { value: "events", label: "Activity events" },
          ]}
          value={kind}
          onChange={(e) => setKind(e.target.value as "records" | "events")}
          aria-label={`Feed type for ${system.code}`}
          className="w-44"
        />
        <Button size="sm" variant="secondary" loading={save.isPending} disabled={!dirty || !url} onClick={() => save.mutate(url)}>
          Save
        </Button>
        <Button size="sm" variant="ghost" disabled={!system.pull_url || save.isPending} onClick={() => save.mutate(null)}>
          Remove
        </Button>
        <Button size="sm" loading={running} disabled={!system.pull_url || dirty} onClick={() => sync.mutate()}>
          <Refresh className="h-3.5 w-3.5" />
          Sync now
        </Button>
      </div>
    </div>
  );
}

export function IngestionPage() {
  useDocumentTitle("Data Ingestion");
  const { notify } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);

  const { can } = useAuth();
  const isAdmin = can("admin");
  const eventsInput = useRef<HTMLInputElement>(null);
  const [eventsSystem, setEventsSystem] = useState("");
  const [eventsReport, setEventsReport] = useState<EventsReport | null>(null);

  const [system, setSystem] = useState("");
  const [runMatching, setRunMatching] = useState(true);
  const [report, setReport] = useState<IngestionReport | null>(null);
  const [pendingResult, setPendingResult] = useState<MatchingTally & { processed: number } | null>(null);

  // Matching runs off the request thread as a background job (see
  // Docs/API_CONTRACT.md#ingestion) — both flows below queue a job and
  // poll it here instead of blocking on the response.
  const [matchJobId, setMatchJobId] = useState<string | null>(null);
  const matchJob = useJobPolling(matchJobId);
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const pendingJob = useJobPolling(pendingJobId);

  const systems = useQuery({
    queryKey: ["source-systems"],
    queryFn: ingestApi.sourceSystems,
  });
  const pending = useQuery({
    queryKey: ["ingest-pending"],
    queryFn: ingestApi.pending,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["source-systems"] });
    queryClient.invalidateQueries({ queryKey: ["ingest-pending"] });
    queryClient.invalidateQueries({ queryKey: ["reviews"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const upload = useMutation({
    mutationFn: () => {
      const file = fileInput.current?.files?.[0];
      if (!file) throw Object.assign(new Error("Choose a CSV file first"), { status: 400 });
      if (!system) throw Object.assign(new Error("Pick a source system"), { status: 400 });
      return ingestApi.uploadCsv(file, system, runMatching);
    },
    onSuccess: (r) => {
      setReport(r);
      notify("success", `${r.created} record${r.created === 1 ? "" : "s"} imported`);
      if (fileInput.current) fileInput.current.value = "";
      if (r.job_id && !r.matching) setMatchJobId(r.job_id);
      refreshAll();
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Import failed"),
  });

  const uploadEvents = useMutation({
    mutationFn: () => {
      const file = eventsInput.current?.files?.[0];
      if (!file) throw Object.assign(new Error("Choose a CSV file first"), { status: 400 });
      return ingestApi.uploadEventsCsv(file, eventsSystem || undefined);
    },
    onSuccess: (r) => {
      setEventsReport(r);
      notify("success", `${r.created} event${r.created === 1 ? "" : "s"} added`);
      if (eventsInput.current) eventsInput.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["business-search"] });
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Event import failed"),
  });

  useEffect(() => {
    const job = matchJob.data;
    if (!job || !isJobTerminal(job.status)) return;
    if (job.status === "succeeded" && job.result) {
      const tally = job.result as MatchingTally;
      setReport((prev) => (prev ? { ...prev, matching: tally } : prev));
      notify("success", "Matching finished for the imported batch");
    } else {
      notify("error", job.error ?? "Matching failed");
    }
    setMatchJobId(null);
    refreshAll();
  }, [matchJob.data, notify]);

  const processPending = useMutation({
    mutationFn: ingestApi.processPending,
    onSuccess: (job) => {
      setPendingJobId(job.id);
      notify("success", "Matching queued for pending records");
    },
    onError: (e) =>
      notify("error", (e as unknown as ApiError)?.message ?? "Processing failed"),
  });

  useEffect(() => {
    const job = pendingJob.data;
    if (!job || !isJobTerminal(job.status)) return;
    if (job.status === "succeeded" && job.result) {
      const result = job.result as MatchingTally & { processed: number };
      setPendingResult(result);
      notify(
        "success",
        `Processed ${result.processed} pending record${result.processed === 1 ? "" : "s"}`,
      );
    } else {
      notify("error", job.error ?? "Processing failed");
    }
    setPendingJobId(null);
    refreshAll();
  }, [pendingJob.data, notify]);

  const matchRunning = !!matchJobId && !isJobTerminal(matchJob.data?.status ?? "pending");
  const pendingRunning =
    processPending.isPending || (!!pendingJobId && !isJobTerminal(pendingJob.data?.status ?? "pending"));

  const systemOptions = [
    { value: "", label: "Select a source system…" },
    ...(systems.data ?? []).map((s) => ({
      value: s.code,
      label: `${s.name} (${s.department})`,
    })),
  ];

  return (
    <div className="space-y-3">
      <PageHeader
        title="Data Ingestion"
        description="Import departmental records and resolve them to business identities."
      />

      {/* Pending */}
      <Card>
        <CardHeader
          title="Unresolved records"
          description="Records not yet linked or in the review queue"
        />
        <CardBody className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-2xl font-semibold tabular-nums text-ink">
            {pending.isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              formatNumber(pending.data ?? 0)
            )}
          </div>
          <Button
            variant="secondary"
            size="sm"
            loading={pendingRunning}
            disabled={!pending.data || pendingRunning}
            onClick={() => processPending.mutate()}
          >
            <Refresh className="h-3.5 w-3.5" />
            {pendingRunning ? "Matching…" : "Run matching on pending"}
          </Button>
        </CardBody>
        {pendingResult && (
          <div className="border-t border-line px-4 py-3">
            <TallyRow tally={pendingResult} />
          </div>
        )}
      </Card>

      {/* CSV import */}
      <Card>
        <CardHeader
          title="Import CSV"
          description="One department's export. Headers are matched loosely (name / firm_name / trade_name, pan, gstin, address, pin…)."
          action={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => ingestApi.downloadTemplate()}
            >
              <Download className="h-3.5 w-3.5" />
              Template
            </Button>
          }
        />
        <CardBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">
                Source system
              </label>
              <Select
                options={systemOptions}
                value={system}
                onChange={(e) => setSystem(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">
                CSV file
              </label>
              <input
                ref={fileInput}
                type="file"
                accept=".csv,text/csv"
                className="block w-full text-[13px] text-ink-muted file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand-soft file:px-3 file:py-1.5 file:text-[13px] file:font-medium file:text-brand hover:file:bg-brand-soft/70"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-[13px] text-ink-muted">
            <input
              type="checkbox"
              checked={runMatching}
              onChange={(e) => setRunMatching(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-line text-brand"
            />
            Resolve imported records through the matching engine now
          </label>

          <Button loading={upload.isPending} onClick={() => upload.mutate()}>
            <Upload className="h-3.5 w-3.5" />
            Import
          </Button>

          {report && (
            <div className="rounded-md border border-line bg-surface-muted p-3">
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
                <span className="text-ink-muted">
                  Rows read <b className="text-ink">{formatNumber(report.rows_read)}</b>
                </span>
                <span className="text-ink-muted">
                  Created <b className="text-ok">{formatNumber(report.created)}</b>
                </span>
                <span className="text-ink-muted">
                  Duplicates skipped{" "}
                  <b className="text-ink">{formatNumber(report.skipped_duplicates)}</b>
                </span>
                {report.errors.length > 0 && (
                  <span className="text-ink-muted">
                    Errors <b className="text-danger">{report.errors.length}</b>
                  </span>
                )}
              </div>
              {report.matching ? (
                <div className="mt-2">
                  <TallyRow tally={report.matching} />
                </div>
              ) : report.job_id && matchRunning ? (
                <div className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-muted">
                  <Refresh className="h-3 w-3 animate-spin" />
                  Matching in progress…
                </div>
              ) : null}
              {report.errors.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-[12px] text-danger">
                  {report.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>
                      Row {e.row}: {e.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Activity events */}
      <Card>
        <CardHeader
          title="Import activity events"
          description="Filings, renewals, inspections and power-usage readings. Each row names the business by UBID, GSTIN, PAN or the department's own record id; statuses refresh straight away. Re-sending a file is harmless."
          action={
            <Button variant="ghost" size="sm" onClick={() => ingestApi.downloadEventsTemplate()}>
              <Download className="h-3.5 w-3.5" />
              Template
            </Button>
          }
        />
        <CardBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">
                Source system (needed only for department record ids)
              </label>
              <Select
                options={[{ value: "", label: "Not specified" }, ...systemOptions.slice(1)]}
                value={eventsSystem}
                onChange={(e) => setEventsSystem(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">CSV file</label>
              <input
                ref={eventsInput}
                type="file"
                accept=".csv,text/csv"
                className="block w-full text-[13px] text-ink-muted file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-brand-soft file:px-3 file:py-1.5 file:text-[13px] file:font-medium file:text-brand hover:file:bg-brand-soft/70"
              />
            </div>
          </div>
          <Button loading={uploadEvents.isPending} onClick={() => uploadEvents.mutate()}>
            <Upload className="h-3.5 w-3.5" />
            Import events
          </Button>
          {eventsReport && (
            <div className="rounded-md border border-line bg-surface-muted p-3 text-[13px]">
              <div className="flex flex-wrap gap-x-5 gap-y-1">
                <span className="text-ink-muted">Rows <b className="text-ink">{formatNumber(eventsReport.rows_read)}</b></span>
                <span className="text-ink-muted">Added <b className="text-ok">{formatNumber(eventsReport.created)}</b></span>
                <span className="text-ink-muted">Already known <b className="text-ink">{formatNumber(eventsReport.skipped_duplicates)}</b></span>
                <span className="text-ink-muted">Unmatched <b className="text-warn">{formatNumber(eventsReport.unresolved)}</b></span>
                <span className="text-ink-muted">Statuses refreshed <b className="text-ink">{formatNumber(eventsReport.recomputed)}</b></span>
              </div>
              {eventsReport.errors.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-[12px] text-danger">
                  {eventsReport.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>Row {e.row}: {e.error}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      {isAdmin && (
        <Card>
          <CardHeader
            title="Scheduled connectors"
            description="Read-only pulls: point a system at the CSV or JSON export it already publishes. The scheduler (or Sync now) fetches it, matches new records and refreshes statuses. Nothing is ever written back to the department."
          />
          {(systems.data ?? []).map((s) => (
            <ConnectorRow
              key={`${s.code}-${s.pull_url}-${s.pull_kind}`}
              system={s}
              onChanged={refreshAll}
            />
          ))}
        </Card>
      )}

      {/* Source systems */}
      <Card>
        <CardHeader title="Source systems" description="Connected departmental registries" />
        {systems.isLoading ? (
          <CardBody>
            <Skeleton className="h-24 w-full" />
          </CardBody>
        ) : systems.isError ? (
          <ErrorState onRetry={() => systems.refetch()} />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Code</Th>
                <Th>Registry</Th>
                <Th>Department</Th>
                <Th className="text-right">Records</Th>
                <Th>Feed</Th>
              </tr>
            </thead>
            <tbody>
              {systems.data?.map((s) => (
                <tr key={s.code}>
                  <Td className="font-mono text-[12px]">{s.code}</Td>
                  <Td>{s.name}</Td>
                  <Td className="text-ink-muted">{s.department}</Td>
                  <Td className="text-right tabular-nums">
                    {formatNumber(s.record_count)}
                  </Td>
                  <Td className="text-[12px] text-ink-muted">
                    {s.pull_kind
                      ? `${s.pull_kind} · ${s.last_pull_at ? formatDateTime(s.last_pull_at) : "never synced"}`
                      : "manual import"}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
