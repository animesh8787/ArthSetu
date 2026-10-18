import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { analyticsApi, businessApi } from "@/api/endpoints";
import type { ApiError } from "@/lib/api";
import { useUrlFilters } from "@/hooks/useUrlFilters";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatNumber } from "@/lib/format";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Table, Td, Th, Tr } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Pagination } from "@/components/ui/Pagination";

const PAGE_SIZE = 25;
const FILTER_KEYS = ["q", "status", "district", "inspection"] as const;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "dormant", label: "Dormant" },
  { value: "closed", label: "Closed" },
  { value: "unknown", label: "Unclassified" },
];

const INSPECTION_OPTIONS = [
  { value: "", label: "Any inspection history" },
  { value: "6", label: "No inspection in 6 months" },
  { value: "12", label: "No inspection in 12 months" },
  { value: "18", label: "No inspection in 18 months" },
  { value: "24", label: "No inspection in 24 months" },
];

export function BusinessSearchPage() {
  useDocumentTitle("Business Search");
  const navigate = useNavigate();
  const { values, offset, setFilter, setOffset, clear } =
    useUrlFilters(FILTER_KEYS);

  const [text, setText] = useState(values.q);
  const lastPushed = useRef(values.q);
  const debouncedText = useDebouncedValue(text, 350);

  // push debounced text into the URL
  useEffect(() => {
    if (debouncedText !== lastPushed.current) {
      lastPushed.current = debouncedText;
      setFilter({ q: debouncedText });
    }
  }, [debouncedText, setFilter]);

  // keep the box in sync when the URL changes elsewhere (e.g. global search)
  useEffect(() => {
    if (values.q !== lastPushed.current) {
      lastPushed.current = values.q;
      setText(values.q);
    }
  }, [values.q]);

  const districts = useQuery({
    queryKey: ["districts"],
    queryFn: analyticsApi.districts,
    staleTime: 5 * 60_000,
  });

  const params = {
    q: values.q || undefined,
    status: values.status || undefined,
    district: values.district || undefined,
    no_inspection_months: values.inspection ? Number(values.inspection) : undefined,
    limit: PAGE_SIZE,
    offset,
  };

  const { data, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ["business-search", params],
    queryFn: () => businessApi.search(params),
    placeholderData: keepPreviousData,
  });

  const hasFilters = Boolean(values.q || values.status || values.district || values.inspection);
  const districtOptions = [
    { value: "", label: "All districts" },
    ...(districts.data ?? [])
      .map((d) => ({ value: d.district, label: d.district }))
      .sort((a, b) => a.label.localeCompare(b.label)),
  ];

  return (
    <div>
      <PageHeader
        title="Business Search"
        description="Find businesses by UBID, name, PAN, GSTIN, status, district or overdue inspection."
      />

      {/* filter row — one line, above the results */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Search UBID, name, PAN, GSTIN or address…"
            className="pl-8"
            aria-label="Search businesses"
          />
        </div>
        <Select
          options={STATUS_OPTIONS}
          value={values.status}
          onChange={(e) => setFilter({ status: e.target.value })}
          aria-label="Filter by status"
          className="w-40"
        />
        <Select
          options={districtOptions}
          value={values.district}
          onChange={(e) => setFilter({ district: e.target.value })}
          aria-label="Filter by district"
          className="w-44"
        />
        <Select
          options={INSPECTION_OPTIONS}
          value={values.inspection}
          onChange={(e) => setFilter({ inspection: e.target.value })}
          aria-label="Filter by inspection history"
          className="w-56"
        />
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setText("");
              lastPushed.current = "";
              clear();
            }}
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </Button>
        )}
      </div>

      <Card>
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-[13px] text-ink-muted">
          <span>
            {isLoading
              ? "Searching…"
              : `${formatNumber(data?.total ?? 0)} ${
                  (data?.total ?? 0) === 1 ? "business" : "businesses"
                }${hasFilters ? " matched" : ""}`}
          </span>
          {isFetching && !isLoading && (
            <span className="text-ink-subtle">Updating…</span>
          )}
        </div>

        {isError ? (
          <ErrorState
            message={(error as unknown as ApiError)?.message}
            onRetry={() => refetch()}
          />
        ) : !isLoading && data && data.items.length === 0 ? (
          <EmptyState
            title="No matching businesses"
            description="Try a broader search term or clear the filters."
            action={
              hasFilters && (
                <Button variant="secondary" size="sm" onClick={clear}>
                  Clear filters
                </Button>
              )
            }
          />
        ) : (
          <div className={isFetching && !isLoading ? "opacity-60" : undefined}>
            <Table>
              <thead>
                <tr>
                  <Th>Business</Th>
                  <Th className="w-32">UBID</Th>
                  <Th className="w-36">District</Th>
                  <Th className="w-28">Status</Th>
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i}>
                        <Td><Skeleton className="h-4 w-48" /></Td>
                        <Td><Skeleton className="h-4 w-24" /></Td>
                        <Td><Skeleton className="h-4 w-20" /></Td>
                        <Td><Skeleton className="h-5 w-16 rounded-md" /></Td>
                      </tr>
                    ))
                  : data?.items.map((b) => (
                      <Tr
                        key={b.ubid}
                        interactive
                        onClick={() => navigate(`/businesses/${b.ubid}`)}
                      >
                        <Td>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/businesses/${b.ubid}`);
                            }}
                            className="block text-left font-medium hover:text-brand hover:underline"
                          >
                            {b.business_name}
                          </button>
                          <span className="font-mono text-[11px] text-ink-subtle">
                            {b.gstin || b.pan || "no strong ID"}
                          </span>
                        </Td>
                        <Td className="font-mono text-[12px] text-ink-muted">
                          {b.ubid}
                        </Td>
                        <Td className="text-ink-muted">{b.district || "—"}</Td>
                        <Td>
                          <StatusBadge status={b.status} />
                        </Td>
                      </Tr>
                    ))}
              </tbody>
            </Table>
          </div>
        )}

        {data && data.total > PAGE_SIZE && (
          <div className="border-t border-line px-3">
            <Pagination
              total={data.total}
              limit={PAGE_SIZE}
              offset={offset}
              onChange={setOffset}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
