import type { AuditEntry } from "@/types/api";
import { titleCase } from "./format";

interface AuditView {
  tone: "ok" | "warn" | "danger" | "brand" | "neutral";
  title: string;
  detail?: string;
}

function stateStr(state: unknown, key: string): string | undefined {
  if (state && typeof state === "object" && key in state) {
    const v = (state as Record<string, unknown>)[key];
    return v == null ? undefined : String(v);
  }
  return undefined;
}

export function describeAudit(entry: AuditEntry): AuditView {
  const action = entry.action ?? "";
  const after = entry.after_state;

  switch (action) {
    case "STATUS_UPDATED": {
      const status = stateStr(after, "status");
      const conf = stateStr(after, "confidence");
      return {
        tone: "brand",
        title: status ? `Status set to ${titleCase(status)}` : "Status recomputed",
        detail: conf ? `confidence ${Number(conf).toFixed(2)}` : undefined,
      };
    }
    case "REVIEW_APPROVED":
      return {
        tone: "ok",
        title: "Review approved",
        detail: stateStr(after, "link_id") ? "link confirmed" : undefined,
      };
    case "REVIEW_REJECTED":
      return {
        tone: "danger",
        title: "Review rejected",
        detail: stateStr(after, "new_entity_id") ? "record given its own business identity" : undefined,
      };
    case "REVIEW_CREATED":
      return { tone: "warn", title: "Sent to review queue" };
    case "AUTO_LINK": {
      const conf = stateStr(after, "confidence");
      const decision = stateStr(after, "decision");
      return {
        tone: "neutral",
        title: decision ? `Link ${titleCase(decision)}` : "Record auto-linked",
        detail: conf ? `confidence ${Number(conf).toFixed(2)}` : undefined,
      };
    }
    case "NEW_ENTITY_CREATED":
      return {
        tone: "brand",
        title: "New business identity created",
        detail: stateStr(after, "ubid_code"),
      };
    case "LINK_SPLIT":
      return {
        tone: "warn",
        title: "Record split from this business",
        detail: stateStr(after, "reason"),
      };
    case "STATUS_OVERRIDDEN":
      return {
        tone: "warn",
        title: `Status pinned to ${titleCase(stateStr(after, "status") ?? "a value")}`,
        detail: stateStr(after, "reason"),
      };
    case "STATUS_OVERRIDE_CLEARED":
      return { tone: "brand", title: "Status pin cleared" };
    case "EVENT_REASSIGNED":
      return { tone: "warn", title: "Activity event reassigned", detail: stateStr(after, "reason") };
    case "CORRECTION_UNDONE":
      return { tone: "neutral", title: "Correction undone", detail: stateStr(after, "note") };
    default:
      return { tone: "neutral", title: titleCase(action || "Event") };
  }
}
