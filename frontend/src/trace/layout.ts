import type { NodeKind, Trace, TraceNode } from "./types";

/*
 * Deterministic "lantern" layout.
 * Chronology runs top → bottom. Each round EXPANDS (queries fan out, source groups widen as
 * they are opened) and then CONVERGES (evidence groups narrow toward a single recorded
 * decision and checkpoint). No force simulation: position always encodes order and provenance.
 */

export type Box = { x: number; y: number; w: number; h: number };
export type Phase = "intent" | "explore" | "evaluate" | "checkpoint" | "decide";
export interface Band {
  round: number;
  phase: Phase;
  y0: number;
  y1: number;
}
export interface SummaryNode {
  id: string;
  round: number;
}
export interface ForkStub {
  id: string;
  label: string;
  checkpointNode: string;
  status: string;
}
export interface Layout {
  pos: Record<string, Box>;
  bands: Band[];
  silhouettes: { round: number; d: string }[];
  summaries: SummaryNode[];
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
  anchorOf: (id: string) => string | null;
}

export const SIZE: Record<NodeKind | "summary", [number, number]> = {
  intent: [320, 66],
  inherited: [300, 54],
  round: [290, 54],
  query: [224, 60],
  group: [224, 68],
  doc: [212, 52],
  passage: [196, 46],
  claim: [226, 70],
  contradiction: [220, 62],
  relation: [250, 54],
  question: [236, 60],
  decision: [300, 70],
  checkpoint: [230, 54],
  fork: [210, 58],
  pending: [230, 48],
  summary: [470, 74],
};

const COL = 262;
const ROW_GAP = 44;
const ROUND_GAP = 30;

type Row = { key: number; phase: Phase; ids: string[]; kind: "center" | "columns" | "spread" | "groups" };

export function computeLayout(
  trace: Trace,
  expanded: Set<string>,
  collapsedRounds: Set<number>,
  forks: ForkStub[] = [],
): Layout {
  const byId = new Map(trace.nodes.map((n) => [n.id, n]));
  const pos: Record<string, Box> = {};
  const bands: Band[] = [];
  const silhouettes: { round: number; d: string }[] = [];
  const summaries: SummaryNode[] = [];
  const childrenOf = (id: string) => trace.nodes.filter((n) => n.parent === id);
  const groupOfQuery = (q: string) =>
    trace.edges.find((e) => e.from === q && e.kind === "retrieved")?.to;

  let y = 0;
  const place = (id: string, cx: number, top: number, kind: NodeKind | "summary") => {
    const [w, h] = SIZE[kind];
    pos[id] = { x: cx - w / 2, y: top, w, h };
    return h;
  };

  const roundNums = [0, ...trace.rounds.map((r) => r.n)];
  for (const r of roundNums) {
    const inRound = trace.nodes.filter((n) => n.round === r && !n.parent);
    if (!inRound.length) continue;
    const rows: Row[] = [];
    const minReveal = (ids: string[]) => Math.min(...ids.map((id) => byId.get(id)!.revealAt));
    const pushRow = (ids: string[], phase: Phase, kind: Row["kind"]) => {
      if (ids.length) rows.push({ key: minReveal(ids), phase, ids, kind });
    };
    const of = (...kinds: NodeKind[]) => inRound.filter((n) => kinds.includes(n.kind)).map((n) => n.id);

    if (r === 0) {
      for (const n of inRound) pushRow([n.id], n.kind === "claim" ? "evaluate" : "intent", "center");
    } else {
      pushRow(of("round"), "explore", "center");
      const collapsed = collapsedRounds.has(r);
      if (collapsed) {
        const inner = of("query", "group", "claim", "contradiction", "relation", "question");
        const id = `sum-r${r}`;
        summaries.push({ id, round: r });
        if (inner.length) rows.push({ key: minReveal(inner), phase: "explore", ids: [id], kind: "center" });
      } else {
        pushRow(of("query"), "explore", "columns");
        pushRow(of("group"), "explore", "groups");
        // evidence row: contradictions sit beside the claim they challenge
        const claims = of("claim");
        const contras = of("contradiction");
        const ordered: string[] = [];
        for (const c of claims) {
          ordered.push(c);
          for (const x of contras) {
            if (trace.edges.some((e) => e.from === x && e.to === c && e.kind === "contradicts") && !ordered.includes(x))
              ordered.push(x);
          }
        }
        contras.forEach((x) => !ordered.includes(x) && ordered.push(x));
        pushRow(ordered, "evaluate", "spread");
        pushRow(of("relation"), "evaluate", "spread");
        pushRow(of("question"), "evaluate", "spread");
      }
      for (const n of inRound.filter((n) => ["checkpoint", "decision", "pending"].includes(n.kind)))
        rows.push({
          key: n.revealAt,
          phase: n.kind === "decision" ? "decide" : "checkpoint",
          ids: [n.id],
          kind: "center",
        });
    }
    rows.sort((a, b) => a.key - b.key);

    const roundTop = y;
    const outline: { y: number; half: number }[] = [];
    for (const row of rows) {
      const top = y;
      let height = 0;
      let half = 0;
      if (row.kind === "center") {
        const id = row.ids[0];
        const kind = id.startsWith("sum-") ? "summary" : byId.get(id)!.kind;
        height = place(id, 0, top, kind);
        half = SIZE[kind][0] / 2;
      } else if (row.kind === "columns" || row.kind === "groups") {
        const queries = inRound.filter((n) => n.kind === "query").map((n) => n.id);
        const ids = row.kind === "columns" ? row.ids : queries.map((q) => groupOfQuery(q)).filter(Boolean) as string[];
        const n = ids.length;
        ids.forEach((id, i) => {
          const cx = (i - (n - 1) / 2) * COL;
          const node = byId.get(id)!;
          let h = place(id, cx, top, node.kind);
          if (node.kind === "group" && expanded.has(id)) {
            let cy = top + h + 14;
            for (const doc of childrenOf(id)) {
              cy += place(doc.id, cx + 6, cy, "doc") + 8;
              if (expanded.has(doc.id)) {
                for (const p of childrenOf(doc.id)) cy += place(p.id, cx + 14, cy, "passage") + 6;
                cy += 4;
              }
            }
            h = cy - top;
          }
          height = Math.max(height, h);
        });
        half = (n / 2) * COL;
      } else {
        const widths = row.ids.map((id) => SIZE[byId.get(id)!.kind][0]);
        const gap = 26;
        const total = widths.reduce((a, b) => a + b, 0) + gap * (widths.length - 1);
        let x = -total / 2;
        row.ids.forEach((id, i) => {
          height = Math.max(height, place(id, x + widths[i] / 2, top, byId.get(id)!.kind));
          x += widths[i] + gap;
        });
        half = total / 2 + 14;
      }
      outline.push({ y: top + height / 2, half });
      const last = bands[bands.length - 1];
      if (last && last.round === r && last.phase === row.phase) last.y1 = top + height + 18;
      else bands.push({ round: r, phase: row.phase, y0: top - 18, y1: top + height + 18 });
      y = top + height + ROW_GAP;
    }
    if (r > 0 && outline.length > 1) {
      // Lantern silhouette: narrow at the round opening, wide during exploration, narrow at the decision.
      const pts = outline.map((p, i) => ({
        y: p.y,
        half: i === 0 || i === outline.length - 1 ? 36 : p.half + 24,
      }));
      const side = (sign: number) =>
        pts.map((p) => `${(sign * p.half).toFixed(1)},${p.y.toFixed(1)}`);
      const left = side(-1);
      const right = side(1).reverse();
      silhouettes.push({ round: r, d: smoothClosed([...left, ...right]) });
    }
    y += ROUND_GAP;
    void roundTop;
  }

  // Child-Lantern stubs emerge to the right of the checkpoint they were forked from.
  const perCp: Record<string, number> = {};
  for (const f of forks) {
    const cp = pos[f.checkpointNode];
    if (!cp) continue;
    const i = (perCp[f.checkpointNode] = (perCp[f.checkpointNode] ?? -1) + 1);
    const [w, h] = SIZE.fork;
    pos[f.id] = { x: cp.x + cp.w + 90 + i * (w + 22), y: cp.y + cp.h / 2 - h / 2, w, h };
  }

  const boxes = Object.values(pos);
  const bounds = {
    minX: Math.min(...boxes.map((b) => b.x)),
    minY: Math.min(...boxes.map((b) => b.y)),
    maxX: Math.max(...boxes.map((b) => b.x + b.w)),
    maxY: Math.max(...boxes.map((b) => b.y + b.h)),
  };

  const anchorOf = (id: string): string | null => {
    if (pos[id]) return id;
    const node = byId.get(id);
    if (!node) return null;
    if (node.parent) return anchorOf(node.parent);
    if (collapsedRounds.has(node.round)) return pos[`sum-r${node.round}`] ? `sum-r${node.round}` : null;
    return null;
  };

  return { pos, bands, silhouettes, summaries, bounds, anchorOf };
}

function smoothClosed(points: string[]) {
  const p = points.map((s) => s.split(",").map(Number));
  let d = `M${p[0][0]},${p[0][1]}`;
  for (let i = 0; i < p.length; i++) {
    const a = p[i];
    const b = p[(i + 1) % p.length];
    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    d += ` Q${a[0]},${a[1]} ${mx},${my}`;
  }
  return d + "Z";
}

export function edgePath(a: Box, b: Box) {
  const ax = a.x + a.w / 2;
  const bx = b.x + b.w / 2;
  // same row → side-to-side curve
  if (Math.abs(a.y - b.y) < 30) {
    const left = ax < bx;
    const sx = left ? a.x + a.w : a.x;
    const ex = left ? b.x : b.x + b.w;
    const sy = a.y + a.h / 2;
    const ey = b.y + b.h / 2;
    const bend = Math.min(60, Math.abs(ex - sx) / 2);
    return `M${sx},${sy} C${sx + (left ? bend : -bend)},${sy - 22} ${ex + (left ? -bend : bend)},${ey - 22} ${ex},${ey}`;
  }
  const down = b.y > a.y;
  const sy = down ? a.y + a.h : a.y;
  const ey = down ? b.y : b.y + b.h;
  const k = Math.max(30, Math.abs(ey - sy) * 0.45);
  return `M${ax},${sy} C${ax},${sy + (down ? k : -k)} ${bx},${ey + (down ? -k : k)} ${bx},${ey}`;
}

export function nodesInRound(trace: Trace, r: number): TraceNode[] {
  return trace.nodes.filter((n) => n.round === r);
}
