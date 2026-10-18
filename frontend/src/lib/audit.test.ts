import { describe, expect, it } from "vitest";
import { describeAudit } from "./audit";
import type { AuditEntry } from "@/types/api";

function entry(partial: Partial<AuditEntry>): AuditEntry {
  return {
    id: "1",
    actor_type: "system",
    actor_id: null,
    entity_type: "business_entity",
    entity_id: "x",
    action: null,
    before_state: null,
    after_state: null,
    created_at: null,
    ...partial,
  };
}

describe("describeAudit", () => {
  it("summarises a status update with confidence", () => {
    const v = describeAudit(
      entry({ action: "STATUS_UPDATED", after_state: { status: "active", confidence: 0.72 } }),
    );
    expect(v.title).toBe("Status set to Active");
    expect(v.detail).toContain("0.72");
    expect(v.tone).toBe("brand");
  });

  it("handles review approvals and rejections", () => {
    expect(describeAudit(entry({ action: "REVIEW_APPROVED", after_state: { link_id: "l1" } })).title)
      .toBe("Review approved");
    expect(describeAudit(entry({ action: "REVIEW_REJECTED" })).tone).toBe("danger");
  });

  it("describes new entity creation", () => {
    const v = describeAudit(
      entry({ action: "NEW_ENTITY_CREATED", after_state: { ubid_code: "UBID-ABC123" } }),
    );
    expect(v.title).toMatch(/new business identity/i);
    expect(v.detail).toBe("UBID-ABC123");
  });

  it("falls back to a title-cased action for unknown actions", () => {
    expect(describeAudit(entry({ action: "SOMETHING_ELSE" })).title).toBe("Something Else");
  });

  it("describes corrections made by reviewers", () => {
    expect(describeAudit(entry({ action: "LINK_SPLIT", after_state: { reason: "different firm" } })).title).toBe(
      "Record split from this business",
    );
    expect(describeAudit(entry({ action: "STATUS_OVERRIDDEN", after_state: { status: "closed" } })).title).toBe(
      "Status pinned to Closed",
    );
    expect(describeAudit(entry({ action: "CORRECTION_UNDONE", after_state: { note: "Split undone" } })).detail).toBe(
      "Split undone",
    );
  });

  it("says when a rejection gave the record its own identity", () => {
    const v = describeAudit(entry({ action: "REVIEW_REJECTED", after_state: { new_entity_id: "abc" } }));
    expect(v.detail).toContain("own business identity");
  });
});
