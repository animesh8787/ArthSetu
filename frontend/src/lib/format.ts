export type EntityStatus = "active" | "dormant" | "closed" | "unknown";

export const STATUS_META: Record<
  EntityStatus,
  { label: string; tone: "ok" | "warn" | "danger" | "neutral" }
> = {
  active: { label: "Active", tone: "ok" },
  dormant: { label: "Dormant", tone: "warn" },
  closed: { label: "Closed", tone: "danger" },
  unknown: { label: "Unknown", tone: "neutral" },
};

export function statusMeta(status: string) {
  const key = status.toLowerCase() as EntityStatus;
  return STATUS_META[key] ?? STATUS_META.unknown;
}

export function decisionMeta(decision: string | null | undefined): {
  label: string;
  tone: "ok" | "warn" | "danger" | "brand" | "neutral";
} {
  switch ((decision ?? "").toLowerCase()) {
    case "auto_link":
      return { label: "Auto-linked", tone: "brand" };
    case "manual":
      return { label: "Reviewer confirmed", tone: "ok" };
    case "review":
      return { label: "In review", tone: "warn" };
    case "rejected":
      return { label: "Rejected", tone: "danger" };
    default:
      return { label: decision ? titleCase(decision) : "–", tone: "neutral" };
  }
}

const ACRONYMS = new Set(["gst", "pan", "gstin", "ubid", "id", "kw"]);

export function titleCase(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .split(" ")
    .map((word) =>
      ACRONYMS.has(word)
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

/**
 * Parse an API timestamp. The backend emits UTC without a timezone suffix
 * (SQLite has no tz type); treat a bare timestamp as UTC rather than local.
 */
export function parseApiDate(input: string | null | undefined): Date | null {
  if (!input) return null;
  const hasTz = /[zZ]|[+-]\d\d:?\d\d$/.test(input);
  const d = new Date(hasTz ? input : `${input}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

const numberFmt = new Intl.NumberFormat("en-IN");
export function formatNumber(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "–";
  return numberFmt.format(value);
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return "–";
  return `${value.toFixed(digits)}%`;
}

export function formatDate(input: string | null | undefined) {
  const d = parseApiDate(input);
  if (!d) return "–";
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(input: string | null | undefined) {
  const d = parseApiDate(input);
  if (!d) return "–";
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(input: string | null | undefined) {
  const parsed = parseApiDate(input);
  if (!parsed) return "–";
  const d = parsed.getTime();
  const diff = d - Date.now();
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000000],
    ["month", 2592000000],
    ["day", 86400000],
    ["hour", 3600000],
    ["minute", 60000],
  ];
  for (const [unit, ms] of units) {
    if (abs >= ms || unit === "minute") {
      return rtf.format(Math.round(diff / ms), unit);
    }
  }
  return "just now";
}
