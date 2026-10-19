import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  decisionMeta,
  formatNumber,
  formatPercent,
  parseApiDate,
  relativeTime,
  statusMeta,
  titleCase,
} from "./format";

describe("statusMeta", () => {
  it("maps known statuses to label + tone", () => {
    expect(statusMeta("active")).toEqual({ label: "Active", tone: "ok" });
    expect(statusMeta("DORMANT").tone).toBe("warn");
    expect(statusMeta("closed").tone).toBe("danger");
  });
  it("falls back to unknown", () => {
    expect(statusMeta("weird")).toEqual(statusMeta("unknown"));
  });
});

describe("decisionMeta", () => {
  it("labels each link decision", () => {
    expect(decisionMeta("auto_link").label).toBe("Auto-linked");
    expect(decisionMeta("manual").tone).toBe("ok");
    expect(decisionMeta("review").tone).toBe("warn");
    expect(decisionMeta("rejected").tone).toBe("danger");
    expect(decisionMeta(null).label).toBe("–");
  });
});

describe("titleCase", () => {
  it("splits on separators and capitalises", () => {
    expect(titleCase("power_usage")).toBe("Power Usage");
  });
  it("upper-cases known acronyms", () => {
    expect(titleCase("gst_filed")).toBe("GST Filed");
    expect(titleCase("pan match")).toBe("PAN Match");
  });
});

describe("number formatting", () => {
  it("formats numbers and handles nullish", () => {
    expect(formatNumber(1234)).toBe("1,234");
    expect(formatNumber(null)).toBe("–");
    expect(formatNumber(undefined)).toBe("–");
  });
  it("formats percentages", () => {
    expect(formatPercent(56.357)).toBe("56.4%");
    expect(formatPercent(null)).toBe("–");
  });
});

describe("parseApiDate", () => {
  it("treats a bare timestamp as UTC", () => {
    const d = parseApiDate("2026-09-04T12:00:00");
    expect(d?.toISOString()).toBe("2026-09-04T12:00:00.000Z");
  });
  it("respects an explicit offset", () => {
    const d = parseApiDate("2026-09-04T12:00:00+05:30");
    expect(d?.toISOString()).toBe("2026-09-04T06:30:00.000Z");
  });
  it("returns null for junk / nullish", () => {
    expect(parseApiDate(null)).toBeNull();
    expect(parseApiDate("not a date")).toBeNull();
  });
});

describe("relativeTime", () => {
  const FIXED = new Date("2026-09-04T12:00:00Z");
  beforeAll(() => vi.useFakeTimers({ now: FIXED }));
  afterAll(() => vi.useRealTimers());

  it("reports minutes and hours ago from a UTC timestamp", () => {
    expect(relativeTime("2026-09-04T11:58:00")).toMatch(/2 minutes ago/);
    expect(relativeTime("2026-09-04T09:00:00")).toMatch(/3 hours ago/);
  });
});
