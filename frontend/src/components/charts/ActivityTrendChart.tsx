import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrendPoint } from "@/types/api";
import { CHART, shortMonth } from "@/lib/chart";
import { formatNumber } from "@/lib/format";

interface Row {
  label: string;
  month: string;
  events: number;
}

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border border-ink-subtle bg-surface px-3 py-2">
      <div className="text-sm font-semibold tabular-nums text-ink">
        {formatNumber(row.events)}
        <span className="ml-1 font-normal text-ink-muted">events</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-[12px] text-ink-muted">
        <span className="h-0.5 w-3 rounded-sm bg-brand" aria-hidden />
        {row.label}
      </div>
    </div>
  );
}

export default function ActivityTrendChart({
  data,
  months = 12,
}: {
  data: TrendPoint[];
  months?: number;
}) {
  const currentMonth = new Date().toISOString().slice(0, 7);
  const complete = data.filter((d) => d.month < currentMonth);
  const rows: Row[] = complete.slice(-months).map((d) => ({
    label: shortMonth(d.month),
    month: d.month,
    events: d.events,
  }));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid
            stroke={CHART.grid}
            strokeWidth={1}
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: CHART.axis, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            interval="preserveStartEnd"
            minTickGap={20}
          />
          <YAxis
            width={40}
            tick={{ fill: CHART.axis, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatNumber(v)}
            allowDecimals={false}
          />
          <Tooltip
            content={<TrendTooltip />}
            cursor={{ stroke: CHART.axis, strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="events"
            stroke={CHART.series}
            strokeWidth={2}
            fill="rgb(var(--c-brand) / 0.1)"
            activeDot={{ r: 4, strokeWidth: 2, stroke: CHART.surface }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
