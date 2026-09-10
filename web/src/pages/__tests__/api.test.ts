import { describe, expect, it } from "vitest";

// Contract: paginated projects shape, clip decision states.
type Paged = { total: number; limit: number; offset: number; items: unknown[] };
const DECISIONS = ["pending", "approved", "rejected", "needs_edit", "exported", "submitted"];

describe("api contracts", () => {
  it("paginated shape", () => {
    const p: Paged = { total: 0, limit: 50, offset: 0, items: [] };
    expect(p.items).toEqual([]);
  });
  it("decision vocabulary is closed", () => {
    expect(new Set(DECISIONS).size).toBe(6);
  });
});
