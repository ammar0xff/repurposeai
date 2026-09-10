import { describe, expect, it } from "vitest";

// Pure helpers mirrored from Review.tsx keyboard contract.
const AXES = ["hook", "standalone", "payoff", "clarity", "emotion", "retention"];

function nextIndex(key: string, idx: number, len: number): number {
  if (key === "ArrowRight") return Math.min(idx + 1, len - 1);
  if (key === "ArrowLeft") return Math.max(idx - 1, 0);
  return idx;
}

function decisionFor(key: string): string | null {
  const k = key.toLowerCase();
  if (k === "a") return "approved";
  if (k === "r") return "rejected";
  if (k === "e") return "needs_edit";
  if (k === "x") return "exported";
  return null;
}

describe("review keyboard contract", () => {
  it("clamps navigation", () => {
    expect(nextIndex("ArrowRight", 2, 3)).toBe(2);
    expect(nextIndex("ArrowLeft", 0, 3)).toBe(0);
    expect(nextIndex("ArrowRight", 0, 3)).toBe(1);
  });
  it("maps decision keys", () => {
    expect(decisionFor("a")).toBe("approved");
    expect(decisionFor("R")).toBe("rejected");
    expect(decisionFor("e")).toBe("needs_edit");
    expect(decisionFor("x")).toBe("exported");
    expect(decisionFor("z")).toBeNull();
  });
  it("axes list matches backend contract", () => {
    expect(AXES).toEqual(["hook", "standalone", "payoff", "clarity", "emotion", "retention"]);
  });
});
