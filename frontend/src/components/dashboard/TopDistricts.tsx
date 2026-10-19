import { Link } from "react-router-dom";
import type { DistrictRow } from "@/types/api";
import { STATUS_COLOR } from "@/lib/chart";
import { formatNumber } from "@/lib/format";

export function TopDistricts({ rows }: { rows: DistrictRow[] }) {
  const top = [...rows].sort((a, b) => b.total - a.total).slice(0, 6);
  const max = top[0]?.total ?? 1;

  return (
    <ul className="space-y-2.5">
      {top.map((d) => (
        <li key={d.district}>
          <Link
            to={`/districts?district=${encodeURIComponent(d.district)}`}
            className="group block rounded-md px-1.5 py-1 transition-colors hover:bg-surface-muted"
          >
            <div className="flex items-baseline justify-between text-[13px]">
              <span className="font-medium text-ink group-hover:text-brand">
                {d.district}
              </span>
              <span className="tabular-nums text-ink-muted">
                {formatNumber(d.total)}
              </span>
            </div>
            <div className="mt-1 flex h-1.5 w-full gap-px overflow-hidden rounded-sm bg-surface-muted">
              {(["active", "dormant", "closed", "unknown"] as const).map((k) =>
                d[k] > 0 ? (
                  <span
                    key={k}
                    style={{
                      width: `${(d[k] / max) * 100}%`,
                      background: STATUS_COLOR[k],
                    }}
                  />
                ) : null,
              )}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
