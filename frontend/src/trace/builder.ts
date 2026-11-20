import type {
  Checkpoint,
  ClaimStatus,
  EdgeKind,
  EventKind,
  QuestionStatus,
  Trace,
  TraceEdge,
  TraceEvent,
  TraceNode,
} from "./types";

/**
 * Small imperative builder: every `ev()` records one investigation event and every node
 * added afterwards is revealed by that event. This keeps playback honest — a node can only
 * appear when the event that produced it was recorded.
 */
export class TraceBuilder {
  nodes: TraceNode[] = [];
  edges: TraceEdge[] = [];
  events: TraceEvent[] = [];
  checkpoints: Checkpoint[] = [];
  rounds: Trace["rounds"] = [];
  round = 0;
  constructor(public lanternId: string) {}

  get seq() {
    return this.events.length - 1;
  }

  ev(kind: EventKind, label: string, detail: string, focus?: string) {
    this.events.push({ seq: this.events.length, kind, round: this.round, label, detail, focus });
    return this;
  }

  startRound(title: string, phase: string) {
    this.round += 1;
    this.rounds.push({ n: this.round, title, phase });
    return this.round;
  }

  n(node: Omit<TraceNode, "round" | "revealAt"> & { round?: number }) {
    const full: TraceNode = { round: this.round, revealAt: this.seq, ...node };
    this.nodes.push(full);
    const last = this.events[this.events.length - 1];
    if (last && !last.focus) last.focus = full.id;
    return full.id;
  }

  e(from: string, to: string, kind: EdgeKind, label?: string) {
    this.edges.push({ id: `${from}>${to}:${kind}`, from, to, kind, label });
    return this;
  }

  status(id: string, status: ClaimStatus | QuestionStatus, note: string) {
    const node = this.nodes.find((n) => n.id === id);
    if (!node) throw new Error(`unknown node ${id}`);
    node.history = [...(node.history ?? []), { at: this.seq, status, note }];
    return this;
  }

  checkpoint(cp: Omit<Checkpoint, "seq" | "nodeId" | "persisted">) {
    this.ev("checkpoint", `Checkpoint recorded · ${cp.short}`, cp.summary);
    const nodeId = `cp-${cp.id}`;
    this.n({ id: nodeId, kind: "checkpoint", label: cp.label, sub: cp.short, checkpointId: cp.id });
    this.checkpoints.push({ ...cp, seq: this.seq, nodeId, persisted: true });
    return nodeId;
  }

  build(): Trace {
    return {
      lanternId: this.lanternId,
      nodes: this.nodes,
      edges: this.edges,
      events: this.events,
      checkpoints: this.checkpoints,
      rounds: this.rounds,
    };
  }
}

export function statusAt<T extends string>(node: { history?: { at: number; status: string; note: string }[] }, cursor: number) {
  const entries = (node.history ?? []).filter((h) => h.at <= cursor);
  return (entries[entries.length - 1] ?? null) as { at: number; status: T; note: string } | null;
}
