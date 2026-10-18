import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Save, SlidersHorizontal } from "lucide-react";
import { matchingApi } from "@/api/endpoints";
import { queryClient } from "@/lib/queryClient";
import type { ApiError } from "@/lib/api";
import type { MatchingWeights } from "@/types/api";
import { Badge } from "@/components/ui/Badge";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";

type EditableField = keyof Omit<MatchingWeights, "updated_by" | "updated_at">;

const IDENTIFIER_FIELDS: { key: EditableField; label: string; hint: string }[] = [
  { key: "gstin_weight", label: "GSTIN exact match", hint: "Unique government id — the strongest signal" },
  { key: "pan_weight", label: "PAN exact match", hint: "Same legal entity / proprietor" },
];

const CORROBORATING_FIELDS: { key: EditableField; label: string; hint: string }[] = [
  { key: "name_weight", label: "Name similarity", hint: "Multiplied by the fuzzy name score" },
  { key: "address_weight", label: "Address similarity", hint: "Multiplied by the fuzzy address score" },
  { key: "contact_weight", label: "Contact match (phone / email)", hint: "Counted only beside a related name, so a shared agency number cannot link strangers" },
  { key: "pin_weight", label: "PIN code match", hint: "Only counted once names are at least loosely related" },
  { key: "pin_requires_name_sim", label: "PIN requires name similarity ≥", hint: "Guards against a bare PIN covering thousands of businesses" },
];

const THRESHOLD_FIELDS: { key: EditableField; label: string; hint: string }[] = [
  { key: "review_threshold", label: "Review threshold", hint: "Score at or above this goes to the review queue" },
  { key: "auto_link_threshold", label: "Auto-link threshold", hint: "Score at or above this links automatically" },
];

function WeightInput({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <input
        type="number"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="field"
      />
      <p className="mt-1 text-[11px] text-ink-subtle">{hint}</p>
    </div>
  );
}

export function MatchingConfigPage() {
  useDocumentTitle("Matching Tuning");
  const { notify } = useToast();

  const weightsQuery = useQuery({ queryKey: ["matching-weights"], queryFn: matchingApi.getWeights });
  const calibrationQuery = useQuery({ queryKey: ["matching-calibration"], queryFn: matchingApi.calibration });

  const suggestionQuery = useQuery({
    queryKey: ["matching-suggestion"],
    queryFn: matchingApi.suggestion,
  });
  const apply = useMutation({
    mutationFn: matchingApi.applySuggestion,
    onSuccess: (w) => {
      notify("success", "Learned weights applied");
      queryClient.setQueryData(["matching-weights"], w);
      const { updated_by: _u, updated_at: _a, ...editable } = w;
      setDraft(editable);
      queryClient.invalidateQueries({ queryKey: ["matching-suggestion"] });
      queryClient.invalidateQueries({ queryKey: ["matching-calibration"] });
    },
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Could not apply"),
  });

  const [draft, setDraft] = useState<Record<EditableField, number> | null>(null);

  useEffect(() => {
    if (weightsQuery.data && !draft) {
      const { updated_by: _u, updated_at: _a, ...editable } = weightsQuery.data;
      setDraft(editable);
    }
  }, [weightsQuery.data, draft]);

  const save = useMutation({
    mutationFn: () => matchingApi.updateWeights(draft as Record<EditableField, number>),
    onSuccess: (w) => {
      notify("success", "Matching weights updated");
      queryClient.setQueryData(["matching-weights"], w);
      queryClient.invalidateQueries({ queryKey: ["matching-calibration"] });
    },
    onError: (e) => notify("error", (e as unknown as ApiError)?.message ?? "Update failed"),
  });

  const reset = () => {
    if (!weightsQuery.data) return;
    const { updated_by: _u, updated_at: _a, ...editable } = weightsQuery.data;
    setDraft(editable);
  };

  const dirty =
    !!draft &&
    !!weightsQuery.data &&
    Object.keys(draft).some(
      (k) => draft[k as EditableField] !== weightsQuery.data![k as EditableField],
    );

  return (
    <div className="space-y-3">
      <PageHeader
        title="Matching Tuning"
        description="Calibrate the entity-resolution engine's weights and thresholds from reviewer feedback."
      />

      <Card>
        <CardHeader
          title="Weights"
          description="Started as fixed constants — now live-editable. Changes apply to every match run from this point on."
        />
        <CardBody className="space-y-5">
          {weightsQuery.isLoading || !draft ? (
            <Skeleton className="h-48 w-full" />
          ) : weightsQuery.isError ? (
            <ErrorState onRetry={() => weightsQuery.refetch()} />
          ) : (
            <>
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-subtle">
                  Strong identifiers
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {IDENTIFIER_FIELDS.map((f) => (
                    <WeightInput
                      key={f.key}
                      label={f.label}
                      hint={f.hint}
                      value={draft[f.key]}
                      onChange={(v) => setDraft({ ...draft, [f.key]: v })}
                    />
                  ))}
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-subtle">
                  Corroborating signals
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {CORROBORATING_FIELDS.map((f) => (
                    <WeightInput
                      key={f.key}
                      label={f.label}
                      hint={f.hint}
                      value={draft[f.key]}
                      onChange={(v) => setDraft({ ...draft, [f.key]: v })}
                    />
                  ))}
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-subtle">
                  Decision thresholds
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  {THRESHOLD_FIELDS.map((f) => (
                    <WeightInput
                      key={f.key}
                      label={f.label}
                      hint={f.hint}
                      value={draft[f.key]}
                      onChange={(v) => setDraft({ ...draft, [f.key]: v })}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-line pt-3">
                <p className="text-[12px] text-ink-subtle">
                  {weightsQuery.data?.updated_by
                    ? `Last changed by ${weightsQuery.data?.updated_by} · ${formatDateTime(weightsQuery.data?.updated_at)}`
                    : "Never changed from the defaults"}
                </p>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" disabled={!dirty} onClick={reset}>
                    Reset
                  </Button>
                  <Button
                    size="sm"
                    loading={save.isPending}
                    disabled={!dirty}
                    onClick={() => save.mutate()}
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save weights
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Learned from reviewer decisions"
          description="A small logistic regression over approved and rejected cases suggests weights. It never scores a record itself: matching stays the weighted sum above, and nothing changes until you apply."
          action={
            suggestionQuery.data?.ready ? (
              <Button size="sm" loading={apply.isPending} onClick={() => apply.mutate()}>
                Apply suggestion
              </Button>
            ) : undefined
          }
        />
        <CardBody>
          {suggestionQuery.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : suggestionQuery.isError ? (
            <ErrorState onRetry={() => suggestionQuery.refetch()} />
          ) : !suggestionQuery.data?.ready ? (
            <p className="py-4 text-center text-[13px] text-ink-muted">
              {suggestionQuery.data?.message}
            </p>
          ) : (
            <div className="space-y-3">
              <p className="text-[12px] text-ink-subtle">
                Trained on {formatNumber(suggestionQuery.data.decided)} decisions (
                {formatNumber(suggestionQuery.data.approved)} approved,{" "}
                {formatNumber(suggestionQuery.data.rejected)} rejected); the fit reproduces{" "}
                {Math.round((suggestionQuery.data.accuracy ?? 0) * 100)}% of them. Suggestions stay within
                0.25x-2.5x of today's weight.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-ink-subtle">
                      <th className="py-1 pr-3 font-semibold">Signal</th>
                      <th className="py-1 pr-3 text-right font-semibold">Approved avg</th>
                      <th className="py-1 pr-3 text-right font-semibold">Rejected avg</th>
                      <th className="py-1 pr-3 text-right font-semibold">Pull toward approval</th>
                      <th className="py-1 pr-3 text-right font-semibold">Weight now</th>
                      <th className="py-1 text-right font-semibold">Suggested</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestionQuery.data.signals.map((s) => (
                      <tr key={s.field} className="border-t border-line">
                        <td className="py-1.5 pr-3 text-ink">
                          {s.label}
                          {!s.learned && (
                            <Badge tone="neutral" className="ml-2">
                              no variation, kept
                            </Badge>
                          )}
                        </td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{s.approved_avg.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{s.rejected_avg.toFixed(2)}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">
                          {s.learned ? s.coefficient.toFixed(2) : "–"}
                        </td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{s.current_weight.toFixed(2)}</td>
                        <td className="py-1.5 text-right font-medium tabular-nums text-ink">
                          {s.suggested_weight.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Reviewer-feedback calibration"
          description="How review-case confidence lines up with what reviewers actually decide — use this to judge whether the thresholds above are set well."
        />
        <CardBody>
          {calibrationQuery.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : calibrationQuery.isError ? (
            <ErrorState onRetry={() => calibrationQuery.refetch()} />
          ) : !calibrationQuery.data?.sample_size ? (
            <p className="py-6 text-center text-[13px] text-ink-muted">
              No review cases yet — calibration data appears once reviewers start approving or rejecting.
            </p>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center gap-1.5 text-[12px] text-ink-subtle">
                <SlidersHorizontal className="h-3.5 w-3.5" />
                {formatNumber(calibrationQuery.data.sample_size)} review case
                {calibrationQuery.data.sample_size === 1 ? "" : "s"} sampled
              </div>

              <div className="space-y-3">
                {calibrationQuery.data.buckets.map((b) => {
                  const total = b.total || 1;
                  return (
                    <div key={b.label}>
                      <div className="mb-1 flex items-center justify-between text-[12px]">
                        <span className="font-medium text-ink">{b.label}</span>
                        <span className="text-ink-muted">
                          {b.approve_rate != null
                            ? `${(b.approve_rate * 100).toFixed(0)}% approved`
                            : "no decisions yet"}{" "}
                          · {formatNumber(b.total)} case{b.total === 1 ? "" : "s"}
                        </span>
                      </div>
                      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-md bg-surface-muted">
                        {b.approved > 0 && (
                          <div
                            className="bg-ok"
                            style={{ width: `${(b.approved / total) * 100}%` }}
                            title={`Approved: ${b.approved}`}
                          />
                        )}
                        {b.rejected > 0 && (
                          <div
                            className="bg-danger"
                            style={{ width: `${(b.rejected / total) * 100}%` }}
                            title={`Rejected: ${b.rejected}`}
                          />
                        )}
                        {b.pending > 0 && (
                          <div
                            className="bg-ink-subtle/40"
                            style={{ width: `${(b.pending / total) * 100}%` }}
                            title={`Pending: ${b.pending}`}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex flex-wrap gap-4 text-[12px] text-ink-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-ok" /> Approved
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-danger" /> Rejected
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-ink-subtle/40" /> Pending
                </span>
              </div>

              {calibrationQuery.data.signals.length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-subtle">
                    Signals in decided cases
                  </h3>
                  <ul className="space-y-1.5">
                    {calibrationQuery.data.signals.map((s) => {
                      const total = s.approved + s.rejected || 1;
                      return (
                        <li key={s.signal} className="flex items-center gap-2 text-[12px]">
                          <span className="w-40 shrink-0 truncate text-ink-muted">{s.signal}</span>
                          <div className="flex h-2 flex-1 gap-[2px] overflow-hidden rounded bg-surface-muted">
                            <div className="bg-ok" style={{ width: `${(s.approved / total) * 100}%` }} />
                            <div className="bg-danger" style={{ width: `${(s.rejected / total) * 100}%` }} />
                          </div>
                          <span className="w-16 shrink-0 text-right text-ink-subtle">
                            {s.approved}/{s.rejected}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
