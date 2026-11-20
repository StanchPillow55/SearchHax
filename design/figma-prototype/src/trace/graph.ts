import { statusAt } from "./builder";
import type { Trace, TraceNode } from "./types";

export const byIdMap = (trace: Trace) => new Map(trace.nodes.map((n) => [n.id, n]));

export function docsOf(trace: Trace, groupId: string) {
  return trace.nodes.filter((n) => n.parent === groupId);
}
export function passagesOf(trace: Trace, docId: string) {
  return trace.nodes.filter((n) => n.parent === docId);
}
export function queryOfGroup(trace: Trace, groupId: string) {
  const e = trace.edges.find((x) => x.to === groupId && x.kind === "retrieved");
  return e ? trace.nodes.find((n) => n.id === e.from) : undefined;
}
export function groupOfNode(trace: Trace, id: string): TraceNode | undefined {
  const node = trace.nodes.find((n) => n.id === id);
  if (!node) return undefined;
  if (node.kind === "group") return node;
  if (node.parent) return groupOfNode(trace, node.parent);
  return undefined;
}
export function docOf(trace: Trace, id: string) {
  const node = trace.nodes.find((n) => n.id === id);
  if (!node) return undefined;
  if (node.kind === "doc") return node;
  if (node.kind === "passage" && node.parent) return trace.nodes.find((n) => n.id === node.parent);
  return undefined;
}
export const incoming = (trace: Trace, id: string, kind?: string) =>
  trace.edges.filter((e) => e.to === id && (!kind || e.kind === kind));
export const outgoing = (trace: Trace, id: string, kind?: string) =>
  trace.edges.filter((e) => e.from === id && (!kind || e.kind === kind));

/** Ancestors needed to make a node visible: group/doc expansion + round. */
export function revealPath(trace: Trace, id: string) {
  const expand: string[] = [];
  let node = trace.nodes.find((n) => n.id === id);
  while (node?.parent) {
    expand.push(node.parent);
    node = trace.nodes.find((n) => n.id === node!.parent);
  }
  return { expand, round: trace.nodes.find((n) => n.id === id)?.round ?? 0 };
}

/** Nodes related to the selection — used for highlighted paths. Only recorded edges are followed. */
export function relatedSet(trace: Trace, id: string | null): Set<string> {
  const out = new Set<string>();
  if (!id) return out;
  const node = trace.nodes.find((n) => n.id === id);
  if (!node) return out;
  out.add(id);
  const back = (start: string, depth: number) => {
    const queue: [string, number][] = [[start, 0]];
    while (queue.length) {
      const [cur, d] = queue.shift()!;
      if (d >= depth) continue;
      const n = trace.nodes.find((x) => x.id === cur);
      if (n?.parent && !out.has(n.parent)) {
        out.add(n.parent);
        queue.push([n.parent, d + 1]);
      }
      for (const e of trace.edges) {
        if (e.to !== cur || out.has(e.from)) continue;
        if (e.kind === "order" && !["round"].includes(trace.nodes.find((x) => x.id === e.from)?.kind ?? "")) continue;
        if (e.kind === "considered") continue;
        out.add(e.from);
        queue.push([e.from, d + 1]);
      }
    }
  };
  if (node.kind === "round") {
    const r = node.round;
    for (const n of trace.nodes) {
      if (n.round === r && ["query", "group", "claim", "contradiction", "question", "decision", "relation"].includes(n.kind)) out.add(n.id);
    }
    for (const e of incoming(trace, id, "prompted")) {
      out.add(e.from);
      back(e.from, 2);
    }
  } else if (node.kind === "decision") {
    incoming(trace, id, "considered").forEach((e) => out.add(e.from));
    outgoing(trace, id).forEach((e) => out.add(e.to));
  } else if (node.kind === "checkpoint") {
    trace.nodes.filter((n) => n.round === node.round && n.revealAt <= node.revealAt && !n.parent).forEach((n) => out.add(n.id));
  } else {
    back(id, node.kind === "claim" || node.kind === "contradiction" ? 4 : 5);
    outgoing(trace, id).forEach((e) => e.kind !== "order" && out.add(e.to));
    if (node.kind === "group") docsOf(trace, id).forEach((d) => out.add(d.id));
  }
  return out;
}

export function claimSupport(trace: Trace, claimId: string, cursor: number) {
  const supports = incoming(trace, claimId, "supports").filter((e) => {
    const n = trace.nodes.find((x) => x.id === e.from);
    return n && n.revealAt <= cursor && trace.edges.indexOf(e) >= 0;
  });
  const contradictions = incoming(trace, claimId, "contradicts")
    .map((e) => trace.nodes.find((n) => n.id === e.from)!)
    .filter((n) => n.revealAt <= cursor);
  return { supports: supports.map((e) => trace.nodes.find((n) => n.id === e.from)!), contradictions };
}

export function nodeStatus(node: TraceNode, cursor: number) {
  return statusAt<string>(node, cursor);
}

export const CLAIM_TONE: Record<string, string> = {
  supported: "teal",
  qualified: "blue",
  mixed: "amber",
  contested: "red",
  regional: "amber",
  unverified: "gray",
  open: "amber",
  partial: "blue",
  resolved: "teal",
};

export const CLAIM_LABEL: Record<string, string> = {
  supported: "Supported",
  qualified: "Supported · qualified",
  mixed: "Mixed evidence",
  contested: "Contested",
  regional: "Supported regionally",
  unverified: "Unverified",
  open: "Open",
  partial: "Partially addressed",
  resolved: "Resolved",
};

export const OUTCOME: Record<string, { label: string; tone: string; icon: string }> = {
  continue: { label: "Continue searching", tone: "blue", icon: "arrow" },
  investigate: { label: "Investigate unresolved relationship", tone: "blue", icon: "arrow" },
  "stop-sufficient": { label: "Stop · evidence sufficient under policy", tone: "teal", icon: "pause" },
  "stop-budget": { label: "Stop · research budget exhausted", tone: "amber", icon: "pause" },
  "stop-uncertain": { label: "Stop · unresolved uncertainty", tone: "amber", icon: "pause" },
  awaiting: { label: "Awaiting direction", tone: "gray", icon: "pause" },
};

export const ORIGIN_LABEL: Record<string, string> = {
  primary: "Primary",
  secondary: "Secondary",
  derivative: "Derivative",
};
