import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "@/components/icons";
import { analyticsApi } from "@/api/endpoints";
import type { ApiError } from "@/lib/api";
import { STATUS_COLOR } from "@/lib/chart";
import { formatNumber, formatPercent, statusMeta } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { DistrictBars } from "@/components/charts/DistrictBars";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { cn } from "@/lib/cn";

type SortKey = "district" | "total" | "active" | "dormant" | "closed" | "unknown";

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "district", label: "District", numeric: false },
  { key: "total", label: "Total", numeric: true },
  { key: "active", label: "Active", numeric: true },
  { key: "dormant", label: "Dormant", numeric: true },
  { key: "closed", label: "Closed", numeric: true },
  { key: "unknown", label: "Unclassified", numeric: true },
];

export function DistrictAnalyticsPage() {
  useDocumentTitle("District Analytics");
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["districts"],
    queryFn: analyticsApi.districts,
  });

  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "total",
    dir: "desc",
  });

  const rows = useMemo(() => {
    const list = [...(data ?? [])];
    list.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      const cmp =
        typeof av === "string" && typeof bv === "string"
          ? av.localeCompare(bv)
          : (av as number) - (bv as number);
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [data, sort]);

  const totals = useMemo(() => {
    const t = { total: 0, active: 0, dormant: 0, closed: 0, unknown: 0 };
    for (const r of data ?? []) {
      t.total += r.total;
      t.active += r.active;
      t.dormant += r.dormant;
      t.closed += r.closed;
      t.unknown += r.unknown;
    }
    return t;
  }, [data]);

  function toggleSort(key: SortKey) {
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "district" ? "asc" : "desc" },
    );
  }

  const goto = (district: string, status?: string) =>
    navigate(
      `/businesses?district=${encodeURIComponent(district)}${
        status ? `&status=${status}` : ""
      }`,
    );

  if (isError) {
    return (
      <div>
        <PageHeader title="District Analytics" />
        <Card>
          <ErrorState
            message={(error as unknown as ApiError)?.message}
            onRetry={() => refetch()}
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="District Analytics"
        description="Business distribution and lifecycle mix across districts."
      />

      <div className="mb-3 grid grid-cols-1 gap-3 xs:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Districts" value={formatNumber(data?.length)} loading={isLoading} />
        <StatCard
          label="Total businesses"
          value={formatNumber(totals.total)}
          loading={isLoading}
        />
        <StatCard
          label="Active share"
          value={formatPercent(totals.total ? (totals.active / totals.total) * 100 : 0)}
          accent="ok"
          loading={isLoading}
        />
        <StatCard
          label="Closed share"
          value={formatPercent(totals.total ? (totals.closed / totals.total) * 100 : 0)}
          accent="danger"
          loading={isLoading}
        />
      </div>

      <Card className="mb-3">
        <CardHeader
          title="Businesses by district"
          description="Bar length is the district total; segments are the status mix. Click to drill in."
        />
        <CardBody>
          {isLoading ? (
            <Skeleton className="h-56 w-full" />
          ) : (
            <DistrictBars rows={data ?? []} />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="District table" description="Click a header to sort, a value to drill in" />
        {isLoading ? (
          <CardBody>
            <Skeleton className="h-40 w-full" />
          </CardBody>
        ) : (
          <Table>
            <thead>
              <tr>
                {COLUMNS.map((c) => {
                  const activeSort = sort.key === c.key;
                  return (
                    <Th
                      key={c.key}
                      className={cn(
                        "cursor-pointer select-none hover:text-ink",
                        c.numeric && "text-right",
                      )}
                    >
                      <button
                        onClick={() => toggleSort(c.key)}
                        className={cn(
                          "inline-flex items-center gap-1",
                          c.numeric && "flex-row-reverse",
                        )}
                      >
                        {c.label}
                        {activeSort &&
                          (sort.dir === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          ))}
                      </button>
                    </Th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <Tr key={d.district} interactive onClick={() => goto(d.district)}>
                  <Td className="font-medium text-ink">{d.district}</Td>
                  <Td className="text-right tabular-nums">{formatNumber(d.total)}</Td>
                  {(["active", "dormant", "closed", "unknown"] as const).map((k) => (
                    <Td key={k} className="text-right tabular-nums">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          goto(d.district, k);
                        }}
                        className="inline-flex items-center gap-1.5 hover:text-brand hover:underline"
                      >
                        <span
                          className="h-1.5 w-1.5 rounded-sm"
                          style={{ background: STATUS_COLOR[k] }}
                          aria-hidden
                        />
                        {formatNumber(d[k])}
                        {k === "active" && d.total > 0 && (
                          <span className="text-[11px] text-ink-subtle">
                            {Math.round((d.active / d.total) * 100)}%
                          </span>
                        )}
                      </button>
                    </Td>
                  ))}
                </Tr>
              ))}
              <tr className="border-t-2 border-line font-medium">
                <Td className="text-ink">All districts</Td>
                <Td className="text-right tabular-nums">{formatNumber(totals.total)}</Td>
                {(["active", "dormant", "closed", "unknown"] as const).map((k) => (
                  <Td key={k} className="text-right tabular-nums text-ink-muted">
                    {formatNumber(totals[k])}
                  </Td>
                ))}
              </tr>
            </tbody>
          </Table>
        )}
      </Card>

      <p className="mt-2 text-[12px] text-ink-subtle">
        {statusMeta("active").label} / {statusMeta("dormant").label} /{" "}
        {statusMeta("closed").label} reflect the latest status inference per business.
      </p>
    </div>
  );
}
