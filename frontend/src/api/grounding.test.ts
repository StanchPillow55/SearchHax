import { describe, expect, it } from "vitest";
import { isGroundedObjective } from "./grounding";

// Same cases as exploration/tests/test_branch_context_regression.py (backend is authoritative).
describe("isGroundedObjective mirrors the backend rule", () => {
  it.each(["", "   ", "Is this true?", "is it true", "verify this", "Check that claim.", "Really?", "Challenge the amount"])("%j is not grounded", (t) => {
    expect(isGroundedObjective(t)).toBe(false);
  });
  it.each(["Look at energy costs", "NVIDIA CoreWeave $2 billion stake", "Investigate whether energy costs undermine the conclusion"])("%j is grounded", (t) => {
    expect(isGroundedObjective(t)).toBe(true);
  });
});
