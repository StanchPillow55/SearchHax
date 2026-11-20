import { describe, expect, it } from "vitest";
import { ExplorationExport } from "../api/schemas";
import { CHILD, MAIN, OTHER, raw } from "../test/fixtures";
import { buildFindings } from "./findingsModel";

const exp = (id: string) => ExplorationExport.parse(raw(id, "export"));

describe("findings are built only from persisted records", () => {
  for (const id of [MAIN, OTHER, CHILD]) {
    const e = exp(id);
    const m = buildFindings(e);

    it(`${id}: every stored claim appears exactly once, grouped only with identical text and status`, () => {
      expect(m.findings.flatMap((f) => f.claimIds).sort()).toEqual(e.claims.map((c) => c.id).sort());
      for (const f of m.findings)
        for (const cid of f.claimIds) {
          const c = e.claims.find((x) => x.id === cid)!;
          expect(c.text.toLowerCase().replace(/\s+/g, " ").trim()).toBe(f.text.toLowerCase().replace(/\s+/g, " ").trim());
          expect(c.status).toBe(f.status);
        }
      const total = Object.values(m.counts).reduce((a, b) => a + b, 0);
      expect(total).toBe(e.claims.length);
    });

    it(`${id}: every evidence row is a stored evidence link with its stored quote`, () => {
      const links = new Map(e.evidence_links.map((l) => [l.id, l]));
      const spans = new Map(e.evidence_spans.map((s) => [s.id, s]));
      for (const f of m.findings)
        for (const r of [...f.supporting, ...f.contradicting, ...f.other]) {
          const l = links.get(r.linkId)!;
          expect(f.claimIds).toContain(l.claim_id);
          expect(r.quoteValid).toBe(l.quote_valid);
          expect(r.quote).toBe(spans.get(l.evidence_span_id)?.text ?? "");
        }
    });

    it(`${id}: unknown-origin sources are never counted as independent`, () => {
      for (const f of m.findings) {
        expect(f.independentOrigins + f.unknownOriginSources).toBeLessThanOrEqual(f.supportingSources);
        const known = new Set(f.supporting.filter((r) => r.originKey).map((r) => r.originKey));
        expect(f.independentOrigins).toBe(known.size);
        expect(f.exactQuoteSupport + f.semanticOnlySupport).toBe(f.supporting.length);
      }
    });
  }

  it("a budget-exhausted run is reported as partial, not verified", () => {
    const m = buildFindings(exp(MAIN));
    expect(exp(MAIN).investigation.stop_reason).toBe("budget_exhausted");
    expect(m.outcome.verified).toBe(false);
    expect(m.outcome.partial).toBe(true);
    expect(m.outcome.headline).toMatch(/Partial result/);
  });

  it("repetition is not corroboration: two derivative copies of one origin count once", () => {
    const e = exp(MAIN);
    const claim = e.claims[0];
    const span = e.evidence_spans[0];
    const d1 = { ...e.documents[0], id: "doc_a" };
    const d2 = { ...e.documents[0], id: "doc_b" };
    const d3 = { ...e.documents[0], id: "doc_c" };
    const synthetic = ExplorationExport.parse({
      ...e,
      documents: [d1, d2, d3],
      evidence_spans: ["a", "b", "c"].map((k) => ({ ...span, id: `sp_${k}`, document_id: `doc_${k}` })),
      evidence_links: ["a", "b", "c"].map((k) => ({ id: `l_${k}`, claim_id: claim.id, evidence_span_id: `sp_${k}`, stance: "supports", quote_valid: true, semantic_status: "supported" })),
      provenance: [
        { id: "p_a", document_id: "doc_a", origin_kind: "derivative", shared_origin_group: "wire-1" },
        { id: "p_b", document_id: "doc_b", origin_kind: "derivative", shared_origin_group: "wire-1" },
        { id: "p_c", document_id: "doc_c", origin_kind: "unknown" },
      ],
      claims: [claim],
    });
    const f = buildFindings(synthetic).findings[0];
    expect(f.supportingSources).toBe(3);
    expect(f.independentOrigins).toBe(1);
    expect(f.unknownOriginSources).toBe(1);
    expect(f.derivativeSources).toBe(2);
  });

  it("a stored cited answer is parsed separately and an invalid one is not shown", () => {
    const e = exp(MAIN);
    const ok = buildFindings({ ...e, answer: { investigation_id: e.investigation.id, question: e.investigation.question, markdown: "A [S1].", citations: [{ marker: "S1", title: "t" }] } } as never);
    expect(ok.answer?.markdown).toBe("A [S1].");
    const bad = buildFindings({ ...e, answer: { nope: true } } as never);
    expect(bad.answer).toBeNull();
    expect(bad.answerInvalid).toBe(true);
  });
});
