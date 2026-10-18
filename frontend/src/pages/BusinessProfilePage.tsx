import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Lock, RefreshCw, Scissors, MoveRight } from "lucide-react";
import { businessApi, correctionsApi, statusApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { BusinessProfile, LinkedRecord, StatusResult, TimelineEvent } from "@/types/api";
import {
  decisionMeta,
  formatDate,
  formatDateTime,
  statusMeta,
  titleCase,
} from "@/lib/format";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { Input, Label, Select } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Dialog";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { CopyButton } from "@/components/ui/CopyButton";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuditFeed } from "@/components/AuditFeed";

type ActiveDialog =
  | { kind: "split"; link: LinkedRecord }
  | { kind: "reassign"; event: TimelineEvent }
  | { kind: "override" }
  | null;

export function BusinessProfilePage() {
  const { ubid = "" } = useParams();
  const navigate = useNavigate();
  const { notify } = useToast();
  const { can } = useAuth();
  const canReview = can("reviewer");
  const [statusResult, setStatusResult] = useState<StatusResult | null>(null);
  const [dialog, setDialog] = useState<ActiveDialog>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["business", ubid],
    queryFn: () => businessApi.profile(ubid),
  });

  useDocumentTitle(data?.business_name ?? "Business");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["business", ubid] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["reviews"] });
    queryClient.invalidateQueries({ queryKey: ["corrections"] });
  };
  const onErr = (e: unknown) =>
    notify("error", (e as unknown as ApiError)?.message ?? "Action failed");

  const recompute = useMutation({
    mutationFn: () => statusApi.recompute(ubid),
    onSuccess: (res) => {
      setStatusResult(res);
      notify("success", `Status: ${titleCase(res.status)}${res.locked ? " (pinned)" : ""}`);
      invalidate();
    },
    onError: onErr,
  });

  const split = useMutation({
    mutationFn: (v: { linkId: string; reason: string; mode: "new_entity" | "reopen_review" }) =>
      correctionsApi.splitLink(v.linkId, v.reason, v.mode),
    onSuccess: (r) => {
      notify("success", r.message);
      setDialog(null);
      invalidate();
    },
    onError: onErr,
  });

  const override = useMutation({
    mutationFn: (v: { status: string; reason: string }) =>
      correctionsApi.overrideStatus(ubid, v.status, v.reason),
    onSuccess: (r) => {
      notify("success", r.message);
      setDialog(null);
      invalidate();
    },
    onError: onErr,
  });

  const clearOverride = useMutation({
    mutationFn: () => correctionsApi.clearOverride(ubid),
    onSuccess: (r) => {
      notify("success", r.message);
      invalidate();
    },
    onError: onErr,
  });

  const reassign = useMutation({
    mutationFn: (v: { eventId: string; target: string; reason: string }) =>
      correctionsApi.reassignEvent(v.eventId, v.target, v.reason),
    onSuccess: (r) => {
      notify("success", r.message);
      setDialog(null);
      invalidate();
    },
    onError: onErr,
  });

  if (isError) {
    const status = (error as unknown as ApiError)?.status;
    return (
      <Card>
        {status === 404 ? (
          <EmptyState
            title="Business not found"
            description={`No business matches "${ubid}".`}
            action={
              <Link to="/businesses">
                <Button variant="secondary" size="sm">
                  Back to search
                </Button>
              </Link>
            }
          />
        ) : (
          <ErrorState
            message={(error as unknown as ApiError)?.message}
            onRetry={() => refetch()}
          />
        )}
      </Card>
    );
  }

  return (
    <div>
      <div className="mb-5">
        <button
          onClick={() => navigate(-1)}
          className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-ink-muted hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              {isLoading ? (
                <Skeleton className="h-7 w-64" />
              ) : (
                <h1 className="text-xl font-semibold text-ink">
                  {data?.business_name}
                </h1>
              )}
              {data && <StatusBadge status={data.status} />}
              {data?.status_locked && (
                <Badge tone="brand">
                  <Lock className="h-3 w-3" /> Pinned
                </Badge>
              )}
            </div>
            <div className="mt-1 flex items-center gap-1 font-mono text-[13px] text-ink-muted">
              {isLoading ? <Skeleton className="h-4 w-28" /> : data?.ubid}
              {data && <CopyButton value={data.ubid} label="UBID" />}
            </div>
          </div>

          {canReview && (
            <Button
              variant="secondary"
              size="sm"
              loading={recompute.isPending}
              onClick={() => recompute.mutate()}
              disabled={isLoading}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Recompute status
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <IdentitySection data={data} loading={isLoading} />
          <LinkedRecordsSection
            data={data}
            loading={isLoading}
            canReview={canReview}
            onSplit={(link) => setDialog({ kind: "split", link })}
          />
          <TimelineSection
            data={data}
            loading={isLoading}
            canReview={canReview}
            onReassign={(event) => setDialog({ kind: "reassign", event })}
          />
        </div>

        <div className="space-y-3">
          <StatusSection
            data={data}
            loading={isLoading}
            result={statusResult}
            canReview={canReview}
            onOverride={() => setDialog({ kind: "override" })}
            onClearOverride={() => clearOverride.mutate()}
            clearing={clearOverride.isPending}
          />
          <EvidenceSection data={data} loading={isLoading} />
          {data && (
            <Card>
              <CardHeader title="Audit trail" description="Actions on this business" />
              <CardBody>
                <AuditFeed
                  params={{ business_id: data.id }}
                  limit={6}
                  emptyLabel="No recorded actions for this business."
                />
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      {dialog?.kind === "split" && (
        <SplitDialog
          record={dialog.link}
          pending={split.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={(reason, mode) =>
            split.mutate({ linkId: dialog.link.link_id, reason, mode })
          }
        />
      )}
      {dialog?.kind === "reassign" && (
        <ReassignDialog
          event={dialog.event}
          pending={reassign.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={(target, reason) =>
            reassign.mutate({ eventId: dialog.event.id, target, reason })
          }
        />
      )}
      {dialog?.kind === "override" && (
        <OverrideDialog
          current={data?.status ?? "unknown"}
          pending={override.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={(status, reason) => override.mutate({ status, reason })}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[12px] text-ink-muted">{label}</dt>
      <dd className={mono ? "mt-0.5 font-mono text-[13px] text-ink" : "mt-0.5 text-sm text-ink"}>
        {value || <span className="text-ink-subtle">—</span>}
      </dd>
    </div>
  );
}

function IdentitySection({ data, loading }: { data?: BusinessProfile; loading: boolean }) {
  return (
    <Card>
      <CardHeader title="Identity" description="Canonical record for this business" />
      <CardBody>
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <Field label="PAN" value={data?.pan} mono />
            <Field label="GSTIN" value={data?.gstin} mono />
            <Field label="PIN code" value={data?.pin_code} mono />
            <Field label="District" value={data?.district} />
            <Field label="Sector" value={data?.sector} />
            <Field
              label="Lifecycle status"
              value={data ? statusMeta(data.status).label : undefined}
            />
            <div className="col-span-2 sm:col-span-3">
              <Field label="Registered address" value={data?.address} />
            </div>
            <Field
              label="Linked records"
              value={data ? String(data.linked_records_count) : undefined}
            />
          </dl>
        )}
      </CardBody>
    </Card>
  );
}

function LinkedRecordsSection({
  data,
  loading,
  canReview,
  onSplit,
}: {
  data?: BusinessProfile;
  loading: boolean;
  canReview: boolean;
  onSplit: (link: LinkedRecord) => void;
}) {
  return (
    <Card>
      <CardHeader
        title="Linked source records"
        description="Departmental records resolved to this identity"
      />
      {loading ? (
        <CardBody>
          <Skeleton className="h-24 w-full" />
        </CardBody>
      ) : !data || data.linked_records.length === 0 ? (
        <EmptyState title="No linked records" />
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Source system</Th>
              <Th>Record name</Th>
              <Th className="w-24">Confidence</Th>
              <Th className="w-32">Link</Th>
              {canReview && <Th className="w-px" />}
            </tr>
          </thead>
          <tbody>
            {data.linked_records.map((r) => {
              const dec = decisionMeta(r.decision);
              return (
                <Tr key={r.link_id}>
                  <Td>
                    <div className="text-ink">{r.source_system ?? "—"}</div>
                    <div className="text-[12px] text-ink-subtle">
                      {r.department ?? ""}
                    </div>
                  </Td>
                  <Td>
                    <div>
                      <span className="text-ink">{r.extracted_name ?? "—"}</span>
                      {r.external_id && (
                        <span className="ml-1.5 font-mono text-[11px] text-ink-subtle">
                          #{r.external_id}
                        </span>
                      )}
                    </div>
                    {(r.extracted_address || r.extracted_pin) && (
                      <div className="text-[12px] text-ink-subtle">
                        {[r.extracted_address, r.extracted_pin]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                    )}
                  </Td>
                  <Td className="tabular-nums text-ink-muted">
                    {r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "—"}
                  </Td>
                  <Td>
                    <Badge tone={dec.tone}>{dec.label}</Badge>
                  </Td>
                  {canReview && (
                    <Td className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => onSplit(r)}>
                        <Scissors className="h-3.5 w-3.5" />
                        Split
                      </Button>
                    </Td>
                  )}
                </Tr>
              );
            })}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function TimelineSection({
  data,
  loading,
  canReview,
  onReassign,
}: {
  data?: BusinessProfile;
  loading: boolean;
  canReview: boolean;
  onReassign: (event: TimelineEvent) => void;
}) {
  return (
    <Card>
      <CardHeader
        title="Activity timeline"
        description="Operational signals across departments"
      />
      <CardBody>
        {loading ? (
          <Skeleton className="h-32 w-full" />
        ) : !data || data.timeline.length === 0 ? (
          <EmptyState title="No activity recorded" />
        ) : (
          <ol className="relative space-y-3 border-l border-line pl-4">
            {data.timeline.map((e) => {
              const positive = (e.score ?? 0) >= 0;
              return (
                <li key={e.id} className="group relative">
                  <span
                    className="absolute -left-[21px] top-1 h-2 w-2 rounded-full ring-2 ring-surface"
                    style={{ background: positive ? "#15803d" : "#b91c1c" }}
                    aria-hidden
                  />
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[13px] font-medium text-ink">
                      {titleCase(e.event)}
                    </span>
                    <span className="flex items-center gap-2 text-[12px] text-ink-subtle">
                      {formatDate(e.date)}
                      {canReview && (
                        <button
                          onClick={() => onReassign(e)}
                          className="opacity-0 transition-opacity hover:text-brand focus:opacity-100 group-hover:opacity-100"
                          title="Reassign to another business"
                        >
                          <MoveRight className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </span>
                  </div>
                  {e.score != null && (
                    <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-muted">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(Math.abs(e.score) * 100, 100)}%`,
                          background: positive ? "#15803d" : "#b91c1c",
                        }}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </CardBody>
    </Card>
  );
}

function StatusSection({
  data,
  loading,
  result,
  canReview,
  onOverride,
  onClearOverride,
  clearing,
}: {
  data?: BusinessProfile;
  loading: boolean;
  result: StatusResult | null;
  canReview: boolean;
  onOverride: () => void;
  onClearOverride: () => void;
  clearing: boolean;
}) {
  return (
    <Card>
      <CardHeader title="Status inference" description="Explainable lifecycle state" />
      <CardBody>
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {data && <StatusBadge status={data.status} />}
              {data?.status_locked && (
                <Badge tone="brand">
                  <Lock className="h-3 w-3" /> Reviewer-pinned
                </Badge>
              )}
            </div>

            {data?.status_locked && data.status_override_reason && (
              <p className="mt-2 rounded-md bg-brand-soft/40 px-2.5 py-1.5 text-[12px] text-ink-muted">
                “{data.status_override_reason}”
                {result?.engine_status && (
                  <span className="block text-ink-subtle">
                    engine currently says {titleCase(result.engine_status)}
                  </span>
                )}
              </p>
            )}

            {result && (
              <div className="mt-3 rounded-md border border-line bg-surface-muted p-3">
                <div className="text-[12px] font-medium text-ink-muted">
                  Why — confidence {result.confidence.toFixed(2)}
                </div>
                <ul className="mt-1.5 space-y-1 text-[12px] text-ink-muted">
                  {result.reasons.slice(0, 6).map((r, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="text-ink-subtle">·</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data && data.status_history.length > 1 && (
              <div className="mt-3">
                <div className="mb-1.5 text-[12px] text-ink-muted">History</div>
                <ul className="space-y-1">
                  {data.status_history
                    .slice()
                    .reverse()
                    .slice(0, 5)
                    .map((h, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between text-[12px]"
                      >
                        <span className="text-ink">{statusMeta(h.status).label}</span>
                        <span className="text-ink-subtle">
                          {h.confidence != null && `${h.confidence.toFixed(2)} · `}
                          {formatDateTime(h.date)}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            )}

            {canReview && (
              <div className="mt-3 border-t border-line pt-3">
                {data?.status_locked ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={clearing}
                    onClick={onClearOverride}
                  >
                    Clear override &amp; recompute
                  </Button>
                ) : (
                  <Button variant="ghost" size="sm" onClick={onOverride}>
                    <Lock className="h-3.5 w-3.5" />
                    Override status
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function EvidenceSection({ data, loading }: { data?: BusinessProfile; loading: boolean }) {
  return (
    <Card>
      <CardHeader title="Matching evidence" description="Signals behind the identity" />
      <CardBody>
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : !data || data.matching_evidence.length === 0 ? (
          <p className="text-[13px] text-ink-subtle">
            No matching signals recorded.
          </p>
        ) : (
          <ul className="space-y-2">
            {data.matching_evidence.map((e, i) => (
              <li key={i} className="flex items-start justify-between gap-3 text-[13px]">
                <span className="text-ink-muted">{e.signal}</span>
                <span className="text-right font-medium text-ink">{e.value}</span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

/* ---------------------------- dialogs ----------------------------- */

function SplitDialog({
  record,
  pending,
  onCancel,
  onConfirm,
}: {
  record: LinkedRecord;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (reason: string, mode: "new_entity" | "reopen_review") => void;
}) {
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"new_entity" | "reopen_review">("reopen_review");
  return (
    <Dialog
      open
      onClose={onCancel}
      title="Split this record from the business"
      description={`${record.extracted_name ?? "Record"} · ${record.source_system ?? ""}`}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            size="sm"
            variant="danger"
            loading={pending}
            disabled={!reason.trim()}
            onClick={() => onConfirm(reason.trim(), mode)}
          >
            Split
          </Button>
        </>
      }
    >
      <div>
        <Label>What happens to the record</Label>
        <Select
          value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
          options={[
            { value: "reopen_review", label: "Send back to the review queue" },
            { value: "new_entity", label: "Make it its own business identity" },
          ]}
        />
      </div>
      <div>
        <Label htmlFor="split-reason">Reason</Label>
        <Input
          id="split-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. different firm at a shared address"
          autoFocus
        />
      </div>
    </Dialog>
  );
}

function ReassignDialog({
  event,
  pending,
  onCancel,
  onConfirm,
}: {
  event: TimelineEvent;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (target: string, reason: string) => void;
}) {
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  return (
    <Dialog
      open
      onClose={onCancel}
      title="Reassign activity event"
      description={`${titleCase(event.event)} · ${formatDate(event.date)}`}
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            size="sm"
            loading={pending}
            disabled={!target.trim() || !reason.trim()}
            onClick={() => onConfirm(target.trim().toUpperCase(), reason.trim())}
          >
            Reassign
          </Button>
        </>
      }
    >
      <div>
        <Label htmlFor="reassign-ubid">Target business UBID</Label>
        <Input
          id="reassign-ubid"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="UBID000123"
          className="font-mono"
          autoFocus
        />
      </div>
      <div>
        <Label htmlFor="reassign-reason">Reason</Label>
        <Input
          id="reassign-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. filed under the wrong UBID by the department"
        />
      </div>
    </Dialog>
  );
}

function OverrideDialog({
  current,
  pending,
  onCancel,
  onConfirm,
}: {
  current: string;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (status: string, reason: string) => void;
}) {
  const [status, setStatus] = useState(
    ["active", "dormant", "closed"].includes(current.toLowerCase())
      ? current.toLowerCase()
      : "active",
  );
  const [reason, setReason] = useState("");
  return (
    <Dialog
      open
      onClose={onCancel}
      title="Override lifecycle status"
      description="Pins the status until a reviewer clears it. The engine keeps recording its own opinion."
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            size="sm"
            loading={pending}
            disabled={!reason.trim()}
            onClick={() => onConfirm(status, reason.trim())}
          >
            Pin status
          </Button>
        </>
      }
    >
      <div>
        <Label htmlFor="override-status">Status</Label>
        <Select
          id="override-status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: "active", label: "Active" },
            { value: "dormant", label: "Dormant" },
            { value: "closed", label: "Closed" },
          ]}
        />
      </div>
      <div>
        <Label htmlFor="override-reason">Reason</Label>
        <Input
          id="override-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. field officer confirmed premises shut"
          autoFocus
        />
      </div>
    </Dialog>
  );
}
