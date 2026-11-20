import { describe, expect, it } from "vitest";
import { BranchList, ExplorationExport, InvestigationTrace } from "../api/schemas";
import { CHILD, EMPTY, MAIN, OTHER, raw } from "../test/fixtures";
import { adaptInvestigation } from "./adapter";
import { TRACES } from "../trace/data";

const load = (id: string) => {
  const exp = ExplorationExport.parse(raw(id, "export"));
  const tr = InvestigationTrace.parse(raw(id, "trace"));
  const br = BranchList.parse(raw(id, "branches"));
  return { exp, tr, br, adapted: adaptInvestigation(exp, tr, br) };
};

describe("adapter: graph nodes correspond to persisted records", () => {
  const { exp, tr, adapted } = load(MAIN);
  const { trace } = adapted;

  it("produces exactly one timeline event per recorded event, in recorded order", () => {
    expect(trace.events.map((e) => e.id)).toEqual([...tr.events].sort((a, b) => a.sequence - b.sequence).map((e) => e.id));
    expect(trace.events.map((e) => e.stage)).toEqual(tr.events.map((e) => e.stage));
  });

  it("marks the trace as persisted and carries the recorded question", () => {
    expect(trace.origin).toBe("persisted");
    expect(trace.question).toBe(exp.investigation.question);
    expect(adapted.lantern.status).toBe("stopped-budget");
  });

  it("uses backend ids for every non-derived node and resolves each to a real record", () => {
    const docIds = new Set(exp.documents.map((d) => d.id));
    const claimIds = new Set(exp.claims.map((c) => c.id));
    const cpIds = new Set(exp.checkpoints.map((c) => c.id));
    const evIds = new Set(tr.events.map((e) => e.id));
    const backendNodeIds = new Set(tr.nodes.map((n) => n.id));
    for (const n of trace.nodes) {
      if (n.derived) {
        expect(n.kind).toBe("round");
        continue;
      }
      switch (n.kind) {
        case "doc":
          expect(docIds.has(n.id)).toBe(true);
          expect(n.ref).toEqual({ table: "documents", id: n.id });
          break;
        case "claim":
          expect(claimIds.has(n.id)).toBe(true);
          break;
        case "checkpoint":
          expect(cpIds.has(n.id)).toBe(true);
          break;
        case "query":
        case "group":
        case "decision":
          expect(evIds.has(n.id)).toBe(true);
          break;
        case "passage":
          expect(backendNodeIds.has(n.id)).toBe(true); // `${event_id}:p${i}` from GET /trace
          break;
        case "intent":
          expect(n.ref).toEqual({ table: "investigations", id: exp.investigation.id });
          break;
      }
    }
  });

  it("resolves a passage to the correct source document and span", () => {
    const traceNode = tr.nodes.find((n) => n.type === "evidence")!;
    const passage = trace.nodes.find((n) => n.id === traceNode.id)!;
    const payload = traceNode.payload as { document_id: string; span_id: string; passage: string };
    expect(passage.parent).toBe(payload.document_id);
    expect(passage.text).toBe(payload.passage);
    expect(passage.ref).toMatchObject({ table: "evidence_spans", id: payload.span_id });
    const doc = trace.nodes.find((n) => n.id === passage.parent)!;
    expect(doc.provenance?.url).toBe(exp.documents.find((d) => d.id === payload.document_id)!.canonical_url);
  });

  it("places checkpoints exactly at their recorded checkpoint events", () => {
    expect(trace.checkpoints.map((c) => c.id)).toEqual(["cp_4c05d11bbb4c4856", "cp_c92da0e30bac4932"]);
    for (const cp of trace.checkpoints) {
      const ev = trace.events[cp.seq];
      expect(ev.stage).toBe("checkpoint");
      expect(ev.checkpointId).toBe(cp.id);
      expect(cp.detail?.hasEvent).toBe(true);
    }
  });

  it("checkpoint snapshot details come from state_json, not from the final export", () => {
    const first = trace.checkpoints[0];
    const rec = exp.checkpoints.find((c) => c.id === first.id)!;
    const snap = (rec.state_json as { snapshot: { documents: unknown[] } }).snapshot;
    expect(first.detail?.counts.documents).toBe(snap.documents.length);
    expect(first.detail?.counts.documents).toBeLessThan(exp.documents.length);
    expect(first.frontier).toEqual((tr.events.find((e) => e.checkpoint_id === first.id)!.payload as { open_questions: string[] }).open_questions);
  });

  it("uses only recorded policy coordinates, keyed by candidate id", () => {
    for (const cp of exp.checkpoints) {
      const recorded = (cp.state_json as { policy_space: { evidence_id: string }[] }).policy_space;
      expect(trace.policyByCheckpoint?.[cp.id]?.map((p) => p.evidenceId)).toEqual(recorded.map((p) => p.evidence_id));
    }
  });

  it("draws a prompted edge only where the approved query equals the next recorded search", () => {
    const prompted = trace.edges.filter((e) => e.kind === "prompted");
    for (const e of prompted) {
      const q = trace.nodes.find((n) => n.id === e.from)!;
      const search = trace.nodes.find((n) => n.id === e.to)!;
      expect(search.kind).toBe("query");
      expect(q.label.trim()).toBe(search.label.trim());
    }
  });

  it("does not invent independence counts, relations or contradictions", () => {
    expect(trace.nodes.filter((n) => n.kind === "claim").every((n) => n.independent === undefined)).toBe(true);
    expect(trace.nodes.some((n) => n.kind === "relation")).toBe(false);
    expect(trace.nodes.filter((n) => n.kind === "contradiction")).toHaveLength(0);
  });

  it("lists recorded children from branch records", () => {
    expect(adapted.related.map((l) => l.id)).toEqual(expect.arrayContaining([CHILD]));
    expect(adapted.related.find((l) => l.id === CHILD)?.fromCheckpoint).toBe("cp_c92da0e30bac4932");
  });
});

describe("adapter: missing data is not fabricated", () => {
  it("an investigation with no events produces no timeline and no checkpoints", () => {
    const { adapted } = load(EMPTY);
    expect(adapted.trace.events).toHaveLength(0);
    expect(adapted.trace.checkpoints).toHaveLength(0);
    expect(adapted.trace.nodes.filter((n) => n.kind !== "intent")).toHaveLength(0);
    expect(adapted.trace.notes?.join(" ")).toMatch(/No investigation events were recorded/);
  });

  it("a checkpoint event without a persisted record is view-only and flagged", () => {
    const exp = ExplorationExport.parse(raw(MAIN, "export"));
    const tr = InvestigationTrace.parse(raw(MAIN, "trace"));
    const withoutSnapshots = { ...exp, checkpoints: [] };
    const { trace } = adaptInvestigation(withoutSnapshots, tr, []);
    expect(trace.checkpoints.every((c) => !c.resumable && !c.forkable && !c.detail)).toBe(true);
    expect(trace.notes?.some((n) => /no persisted checkpoint record/.test(n))).toBe(true);
    expect(Object.keys(trace.policyByCheckpoint ?? {})).toHaveLength(0);
  });

  it("a persisted checkpoint with no event is listed but never placed on the timeline", () => {
    const exp = ExplorationExport.parse(raw(MAIN, "export"));
    const tr = InvestigationTrace.parse(raw(MAIN, "trace"));
    const noCpEvents = { ...tr, events: tr.events.filter((e) => e.stage !== "checkpoint") };
    const { trace } = adaptInvestigation(exp, noCpEvents, []);
    expect(trace.checkpoints).toHaveLength(0);
    expect(trace.unplacedCheckpoints?.map((c) => c.id)).toEqual(exp.checkpoints.map((c) => c.id));
    expect(trace.unplacedCheckpoints?.every((c) => c.seq === -1)).toBe(true);
  });

  it("invalid policy coordinates are dropped and reported, not repaired", () => {
    const exp = ExplorationExport.parse(raw(MAIN, "export"));
    const tr = InvestigationTrace.parse(raw(MAIN, "trace"));
    const cp = exp.checkpoints[0];
    const broken = { ...cp, state_json: { ...cp.state_json, policy_space: [{ evidence_id: "x", intent_alignment: 3, novelty: 0.1, unresolved_alignment: 0.1, action: "consider" }] } };
    const { trace } = adaptInvestigation({ ...exp, checkpoints: [broken, exp.checkpoints[1]] }, tr, []);
    expect(trace.policyByCheckpoint?.[cp.id]).toHaveLength(0);
    expect(trace.notes?.some((n) => /failed validation/.test(n))).toBe(true);
  });

  it("refuses to combine a trace with a different investigation's export", () => {
    const exp = ExplorationExport.parse(raw(MAIN, "export"));
    const other = InvestigationTrace.parse(raw(OTHER, "trace"));
    expect(() => adaptInvestigation(exp, other, [])).toThrow(/does not belong/);
  });
});

describe("adapter: child investigation", () => {
  it("records the parent link and inherited checkpoint from the trace", () => {
    const { adapted } = load(CHILD);
    expect(adapted.lantern.parentId).toBe(MAIN);
    expect(adapted.lantern.fromCheckpoint).toBe("cp_c92da0e30bac4932");
    expect(adapted.trace.nodes.some((n) => n.kind === "inherited")).toBe(true);
  });
});

describe("demo data never appears as backend evidence", () => {
  it.each([MAIN, CHILD, OTHER])("persisted trace %s contains no simulated records", (id) => {
    const { adapted } = load(id);
    const demoIds = new Set(Object.values(TRACES).flatMap((t) => [...t.nodes.map((n) => n.id), ...t.checkpoints.map((c) => c.id)]));
    for (const n of adapted.trace.nodes) {
      expect(demoIds.has(n.id)).toBe(false);
      expect(Boolean(n.ref) || n.derived === true).toBe(true);
    }
    for (const c of adapted.trace.checkpoints) expect(demoIds.has(c.id)).toBe(false);
    expect(adapted.trace.origin).toBe("persisted");
  });

  it("demo traces are never marked persisted and carry no backend refs", () => {
    for (const t of Object.values(TRACES)) {
      expect(t.origin).not.toBe("persisted");
      expect(t.nodes.some((n) => n.ref)).toBe(false);
    }
  });
});
