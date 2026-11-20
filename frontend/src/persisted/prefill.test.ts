import { describe, expect, it } from "vitest";
import { decodePrefill, encodePrefill } from "./prefill";

describe("New Investigation prefill (M8)", () => {
  it("round-trips a frontier question with the investigation whose profile to copy", () => {
    const p = { question: "advanced packaging", profileFrom: { investigationId: "inv_1", profileId: "profile_a" } };
    expect(decodePrefill(encodePrefill(p))).toEqual(p);
  });

  it("reads a legacy bare question as a question without a profile", () => {
    expect(decodePrefill("advanced packaging")).toEqual({ question: "advanced packaging", profileFrom: null });
    expect(decodePrefill(null)).toEqual({ question: "", profileFrom: null });
  });

  it("drops an incomplete profile reference instead of guessing one", () => {
    const raw = JSON.stringify({ v: 1, question: "q", profileFrom: { investigationId: "inv_1" } });
    expect(decodePrefill(raw)).toEqual({ question: "q", profileFrom: null });
  });
});
