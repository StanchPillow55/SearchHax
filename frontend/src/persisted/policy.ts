import type { EvidencePoint } from "../shared";
import type { Checkpoint, PolicyPointView, Trace } from "../trace/types";

/** Recorded Focus coordinates → the 3D plot's point shape. Values are copied, never rescaled. */
export function toEvidencePoint(p: PolicyPointView): EvidencePoint {
  let source = p.url;
  try {
    source = new URL(p.url).host.replace(/^www\./, "");
  } catch {
    /* keep raw */
  }
  return {
    id: p.evidenceId,
    relevance: p.intent,
    novelty: p.novelty,
    graphGap: p.unresolved,
    action: p.action,
    title: p.title || p.evidenceId,
    source,
    summary: p.passage,
  };
}

/**
 * The checkpoint whose recorded policy space should be shown at `cursor`: the latest placed
 * checkpoint at or before the cursor that recorded coordinates. Returns null when none did —
 * coordinates are never borrowed from a later checkpoint.
 */
export function policyCheckpointAt(trace: Trace, cursor: number): Checkpoint | null {
  const candidates = trace.checkpoints.filter((c) => c.seq <= cursor && (trace.policyByCheckpoint?.[c.id]?.length ?? 0) > 0);
  return candidates[candidates.length - 1] ?? null;
}

/** Passage-level point for a stored evidence span at the cursor's checkpoint, if one was recorded. */
export function policyForSpan(trace: Trace, cursor: number, spanId: string) {
  const cps = trace.checkpoints.filter((c) => c.seq <= cursor && (trace.passagePolicyByCheckpoint?.[c.id]?.length ?? 0) > 0);
  const cp = cps[cps.length - 1] ?? null;
  if (!cp) return { checkpoint: null, points: [] as PolicyPointView[], point: null as PolicyPointView | null };
  const points = trace.passagePolicyByCheckpoint?.[cp.id] ?? [];
  return { checkpoint: cp, points, point: points.find((p) => p.spanId === spanId) ?? null };
}

export function policyForDocument(trace: Trace, cursor: number, documentId: string) {
  const cp = policyCheckpointAt(trace, cursor);
  if (!cp) return { checkpoint: null, points: [] as PolicyPointView[], point: null as PolicyPointView | null };
  const points = trace.policyByCheckpoint?.[cp.id] ?? [];
  return { checkpoint: cp, points, point: points.find((p) => p.documentId === documentId) ?? null };
}
