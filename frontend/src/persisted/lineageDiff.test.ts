import { describe, expect, it } from "vitest";
import { ExplorationExport } from "../api/schemas";
import { CHILD, MAIN, raw } from "../test/fixtures";
import { diffLineage } from "./lineageDiff";

const exp = (id: string) => ExplorationExport.parse(raw(id, "export"));

describe("parent ↔ child diff uses only stored records", () => {
  it("an investigation compared with itself has no differences", () => {
    const d = diffLineage(exp(MAIN), exp(MAIN));
    expect(d.claims.added).toEqual([]);
    expect(d.claims.changed).toEqual([]);
    expect(d.claims.onlyInParent).toEqual([]);
    expect(d.sources.added).toEqual([]);
    expect(d.questions.added).toEqual([]);
    expect(d.questions.notOpenInChild).toEqual([]);
  });

  it("an unstarted child shows zero searches and nothing new beyond its inherited checkpoint", () => {
    const parent = exp(MAIN);
    const child = exp(CHILD);
    const d = diffLineage(parent, child);
    expect(d.child.searches).toBe(0);
    const parentUrls = new Set(parent.documents.map((x) => x.canonical_url));
    expect(d.sources.added.every((s) => !parentUrls.has(s.url))).toBe(true);
    expect(d.sources.shared + d.sources.added.length).toBe(new Set(child.documents.map((x) => x.canonical_url)).size);
  });

  it("detects a status change, a new claim, a new source and a new question", () => {
    const parent = exp(MAIN);
    const base = exp(MAIN);
    const c0 = base.claims[0];
    const child = ExplorationExport.parse({
      ...base,
      claims: [{ ...c0, status: c0.status === "supported" ? "contradicted" : "supported" }, { ...c0, id: "clm_new", text: "A brand new claim" }, ...base.claims.slice(1)],
      documents: [...base.documents, { ...base.documents[0], id: "doc_new", canonical_url: "https://new.example/x", title: "New" }],
      unresolved_questions: [...base.unresolved_questions, { id: "uq_new", text: "A new open question", kind: "gap" }],
    });
    const d = diffLineage(parent, child);
    expect(d.claims.changed.map((c) => c.text)).toContain(c0.text);
    expect(d.claims.added.map((c) => c.text)).toEqual(["A brand new claim"]);
    expect(d.sources.added.map((s) => s.url)).toEqual(["https://new.example/x"]);
    expect(d.questions.added).toEqual(["A new open question"]);
  });
});
