import { useEffect, useMemo, useRef, useState } from "react";
import { Icon, Tag } from "../shared";
import { QUESTION, STATUS_META, summarize } from "./data";
import { computeLayout, edgePath, type Box, type ForkStub } from "./layout";
import {
  CLAIM_LABEL,
  CLAIM_TONE,
  OUTCOME,
  docsOf,
  nodeStatus,
  passagesOf,
  relatedSet,
  revealPath,
} from "./graph";
import { TraceInspector, type BranchingState } from "./Inspector";
import { Timeline } from "./Timeline";
import type { ComposerDraft, EdgeKind, Lantern, Trace, TraceNode, ViewState } from "./types";

export const defaultView = (): ViewState => ({
  cursor: -1,
  snapshot: null,
  selected: null,
  expanded: [],
  collapsedRounds: [],
  zoom: 0.78,
  pan: { x: 0, y: 0 },
  fitted: false,
  granularity: "event",
  composer: null,
  focusNonce: 0,
  focusIds: [],
});

export type ViewPatch = Partial<ViewState> | ((v: ViewState) => Partial<ViewState>);

export interface InteriorProps {
  lantern: Lantern;
  lanterns: Lantern[];
  trace: Trace;
  latest: number;
  view: ViewState;
  setView: (patch: ViewPatch) => void;
  onBack: () => void;
  onOpenLantern: (id: string) => void;
  onCompare: (a: string, b: string) => void;
  /** Live mode: open the Findings view built from recorded claims and evidence. */
  onFindings?: () => void;
  /** Live mode, child investigations only: compare recorded findings with the parent. */
  onCompareParent?: () => void;
  /** Live mode: open the personal knowledge view for this investigation's profile. */
  onKnowledge?: () => void;
  onOpen3D: (evId: string | null) => void;
  onCreateFork: (draft: ComposerDraft, mode: "saved" | "investigate") => void;
  onStartResearch: () => void;
  onDemo: () => void;
  /** Label of the screen "back" returns to (Constellation in demo, Investigations in live mode). */
  backLabel?: string;
  /** Live mode: branching state. Without it, a persisted investigation is read-only. */
  branching?: BranchingState;
  /** Live mode: open the Lantern family Constellation. */
  onConstellation?: () => void;
}

const EDGE_LEGEND: { kind: EdgeKind; label: string }[] = [
  { kind: "order", label: "Recorded event order" },
  { kind: "retrieved", label: "Retrieved by same query" },
  { kind: "supports", label: "Supports" },
  { kind: "contradicts", label: "Contradicts" },
  { kind: "sharedOrigin", label: "Shared origin" },
  { kind: "prompted", label: "Prompted follow-up" },
  { kind: "considered", label: "Considered in decision" },
  { kind: "raised", label: "Raised question" },
  { kind: "mentions", label: "Mentions only" },
];

export const zoomLevel = (z: number) => (z < 0.5 ? "journey" : z < 1.02 ? "rounds" : "detail");

export function Interior(props: InteriorProps) {
  const { lantern, lanterns, trace, latest, view, setView } = props;
  const cursor = view.cursor < 0 ? latest : Math.min(view.cursor, latest);
  const persisted = trace.origin === "persisted";
  const question = trace.question ?? QUESTION;
  const isLatest = cursor >= latest;
  const snapshot = view.snapshot ? trace.checkpoints.find((c) => c.id === view.snapshot) ?? null : null;
  const [playing, setPlaying] = useState(false);
  const [follow, setFollow] = useState(true);
  const [minimap, setMinimap] = useState(true);
  const [hiddenEdges, setHiddenEdges] = useState<Set<EdgeKind>>(new Set());
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [instant, setInstant] = useState(false);
  const [size, setSize] = useState({ w: 900, h: 560 });
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number; moved: boolean } | null>(null);
  const instantTimer = useRef<number | undefined>(undefined);

  const expanded = useMemo(() => new Set(view.expanded), [view.expanded]);
  const collapsed = useMemo(() => new Set(view.collapsedRounds), [view.collapsedRounds]);
  const children = lanterns.filter((l) => l.parentId === lantern.id && l.fromCheckpoint);
  const forks: ForkStub[] = children
    .map((l) => {
      const cp = trace.checkpoints.find((c) => c.id === l.fromCheckpoint);
      return cp ? { id: `fork:${l.id}`, label: l.title, checkpointNode: cp.nodeId, status: l.status } : null;
    })
    .filter(Boolean) as ForkStub[];
  const layout = useMemo(
    () => computeLayout(trace, expanded, collapsed, forks),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [trace, expanded, collapsed, forks.map((f) => f.id).join()],
  );
  const byId = useMemo(() => new Map(trace.nodes.map((n) => [n.id, n])), [trace]);
  const related = useMemo(() => relatedSet(trace, view.selected?.startsWith("fork:") ? null : view.selected), [trace, view.selected]);
  const level = zoomLevel(view.zoom);
  const stats = summarize(trace, cursor);
  const event = trace.events[cursor];

  // ── size tracking ──
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const flashInstant = () => {
    setInstant(true);
    window.clearTimeout(instantTimer.current);
    instantTimer.current = window.setTimeout(() => setInstant(false), 180);
  };

  const fitBoxes = (boxes: Box[], opts: { min?: number; max?: number } = {}) => {
    if (!boxes.length || !size.w) return;
    const minX = Math.min(...boxes.map((b) => b.x));
    const minY = Math.min(...boxes.map((b) => b.y));
    const maxX = Math.max(...boxes.map((b) => b.x + b.w));
    const maxY = Math.max(...boxes.map((b) => b.y + b.h));
    const pad = 70;
    let zoom = Math.min((size.w - pad * 2) / (maxX - minX || 1), (size.h - pad * 2) / (maxY - minY || 1));
    zoom = Math.max(opts.min ?? 0.16, Math.min(opts.max ?? 1.25, zoom));
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    setView({ zoom, pan: { x: size.w / 2 - cx * zoom, y: size.h / 2 - cy * zoom }, fitted: true });
  };

  const visibleIds = () => Object.keys(layout.pos).filter((id) => isVisible(id));
  const isVisible = (id: string) => {
    if (id.startsWith("fork:")) {
      const f = forks.find((x) => x.id === id);
      const cpNode = f && byId.get(f.checkpointNode);
      return !!cpNode && cpNode.revealAt <= cursor;
    }
    if (id.startsWith("sum-")) {
      const r = Number(id.slice(5));
      return trace.nodes.some((n) => n.round === r && n.kind === "query" && n.revealAt <= cursor);
    }
    const n = byId.get(id);
    return !!n && n.revealAt <= cursor;
  };

  // initial placement: centre on the current frontier
  useEffect(() => {
    if (view.fitted || !size.w || size.w < 50) return;
    const frontier = trace.nodes.filter((n) => n.revealAt <= cursor && layout.pos[n.id]).slice(-4);
    const target = view.selected && layout.pos[view.selected] ? [layout.pos[view.selected]] : frontier.map((n) => layout.pos[n.id]);
    flashInstant();
    fitBoxes(target, { min: 0.78, max: 0.82 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.w, view.fitted]);

  // focus requests (from inspector, search, demo)
  useEffect(() => {
    if (!view.focusNonce) return;
    const boxes = view.focusIds.map((id) => layout.pos[layout.anchorOf(id) ?? ""]).filter(Boolean);
    if (boxes.length) fitBoxes(boxes, { min: Math.min(0.55, view.zoom), max: 1.08 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.focusNonce, layout]);

  // playback timer
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => step(1), 1150);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, cursor, view.granularity, latest]);

  // follow playback: keep newly revealed nodes in view
  const prevCursor = useRef(cursor);
  useEffect(() => {
    const prev = prevCursor.current;
    prevCursor.current = cursor;
    if (!follow || cursor <= prev) return;
    const fresh = trace.nodes.filter((n) => n.revealAt > prev && n.revealAt <= cursor);
    const boxes = fresh.map((n) => layout.pos[layout.anchorOf(n.id) ?? ""]).filter(Boolean);
    if (!boxes.length) return;
    const z = view.zoom;
    const inView = boxes.every(
      (b) =>
        b.x * z + view.pan.x > 20 &&
        (b.x + b.w) * z + view.pan.x < size.w - 20 &&
        b.y * z + view.pan.y > 20 &&
        (b.y + b.h) * z + view.pan.y < size.h - 20,
    );
    if (inView) return;
    const cx = boxes.reduce((a, b) => a + b.x + b.w / 2, 0) / boxes.length;
    const cy = boxes.reduce((a, b) => a + b.y + b.h / 2, 0) / boxes.length;
    setView({ pan: { x: size.w / 2 - cx * z, y: size.h * 0.55 - cy * z } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursor]);

  // wheel zoom (non-passive so the page does not scroll)
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      setView((v) => {
        if (!e.ctrlKey && Math.abs(e.deltaX) > Math.abs(e.deltaY) * 1.2) {
          return { pan: { x: v.pan.x - e.deltaX, y: v.pan.y } };
        }
        const z = Math.max(0.16, Math.min(1.8, v.zoom * Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0016))));
        const wx = (mx - v.pan.x) / v.zoom;
        const wy = (my - v.pan.y) / v.zoom;
        return { zoom: z, pan: { x: mx - wx * z, y: my - wy * z } };
      });
      flashInstant();
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const zoomTo = (z: number) => {
    const cx = (size.w / 2 - view.pan.x) / view.zoom;
    const cy = (size.h / 2 - view.pan.y) / view.zoom;
    setView({ zoom: z, pan: { x: size.w / 2 - cx * z, y: size.h / 2 - cy * z } });
  };

  // ── playback ──
  const milestones = trace.events
    .filter((e) => ["intent", "inherit", "plan", "evaluate", "decide", "checkpoint", "pending"].includes(e.kind))
    .map((e) => e.seq);
  const seek = (seq: number, keepSnapshot = false) => {
    const s = Math.max(0, Math.min(latest, seq));
    setView((v) => ({
      cursor: s >= latest ? -1 : s,
      snapshot: keepSnapshot ? v.snapshot : null,
    }));
  };
  function step(dir: 1 | -1) {
    let next: number;
    if (view.granularity === "event") next = cursor + dir;
    else {
      const list = dir > 0 ? milestones.filter((m) => m > cursor) : milestones.filter((m) => m < cursor).reverse();
      next = list[0] ?? (dir > 0 ? latest : 0);
    }
    if (next > latest || next < 0) {
      setPlaying(false);
      return;
    }
    if (next >= latest) setPlaying(false);
    seek(next);
    const ev = trace.events[next];
    if (ev?.focus && dir > 0) setView({ selected: ev.focus });
  }

  // ── selection helpers ──
  const select = (id: string | null) => setView({ selected: id, composer: null });
  const focusOn = (ids: string[]) =>
    setView((v) => ({ focusIds: ids, focusNonce: v.focusNonce + 1 }));
  const reveal = (id: string) => {
    const node = byId.get(id);
    if (!node) return;
    const { expand, round } = revealPath(trace, id);
    setView((v) => ({
      expanded: Array.from(new Set([...v.expanded, ...expand])),
      collapsedRounds: v.collapsedRounds.filter((r) => r !== round),
      selected: id,
      composer: null,
      cursor: node.revealAt > cursor ? (node.revealAt >= latest ? -1 : node.revealAt) : v.cursor,
      snapshot: node.revealAt > cursor ? null : v.snapshot,
      focusIds: [id],
      focusNonce: v.focusNonce + 1,
    }));
  };
  const toggleExpand = (id: string) =>
    setView((v) => ({
      expanded: v.expanded.includes(id) ? v.expanded.filter((x) => x !== id) : [...v.expanded, id],
    }));
  const toggleRound = (r: number) =>
    setView((v) => ({
      collapsedRounds: v.collapsedRounds.includes(r)
        ? v.collapsedRounds.filter((x) => x !== r)
        : [...v.collapsedRounds, r],
    }));

  // ── search ──
  const q = search.trim().toLowerCase();
  const matches = q
    ? trace.nodes
        .filter((n) => n.revealAt <= latest)
        .filter((n) =>
          [n.label, n.sub, n.text, n.publisher, n.body].some((s) => s?.toLowerCase().includes(q)),
        )
        .slice(0, 12)
    : [];
  const matchSet = new Set(matches.map((m) => layout.anchorOf(m.id)));

  // ── edges ──
  const edges = useMemo(() => {
    const seen = new Map<string, { a: string; b: string; kind: EdgeKind; label?: string; count: number; hl: boolean }>();
    for (const e of trace.edges) {
      if (hiddenEdges.has(e.kind)) continue;
      const fn = byId.get(e.from);
      const tn = byId.get(e.to);
      if (!fn || !tn || fn.revealAt > cursor || tn.revealAt > cursor) continue;
      const a = layout.anchorOf(e.from);
      const b = layout.anchorOf(e.to);
      if (!a || !b || a === b) continue;
      const key = `${a}>${b}:${e.kind}`;
      const hl = related.has(e.from) && related.has(e.to);
      const prev = seen.get(key);
      if (prev) {
        prev.count++;
        prev.hl = prev.hl || hl;
      } else seen.set(key, { a, b, kind: e.kind, label: e.label, count: 1, hl });
    }
    for (const f of forks) {
      if (!hiddenEdges.has("fork") && isVisible(f.id))
        seen.set(f.id, { a: f.checkpointNode, b: f.id, kind: "fork", count: 1, hl: view.selected === f.id });
    }
    return [...seen.values()];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trace, layout, cursor, hiddenEdges, related, forks.length, view.selected]);

  const selectedNode = view.selected ? byId.get(view.selected) ?? null : null;
  const researchStages = new Set(["search", "retrieval", "ranking", "extraction", "convergence", "ingest"]);
  const notStarted =
    lantern.status === "not-started" ||
    (persisted && !!lantern.parentId && ["created", "running"].includes(lantern.status) && !trace.events.some((e) => researchStages.has(e.stage ?? "")));
  const parent = lanterns.find((l) => l.id === lantern.parentId);
  const mode: "live" | "history" | "snapshot" = snapshot ? "snapshot" : isLatest ? "live" : "history";

  // ── node renderer ──
  const renderNode = (id: string) => {
    const box = layout.pos[id];
    if (!box || !isVisible(id)) return null;
    const style = { left: box.x, top: box.y, width: box.w, height: box.h };
    const isSel = view.selected === id;
    const dim = (view.selected && related.size > 0 && !related.has(id) && !isSel && !id.startsWith("fork:")) || (q && !matchSet.has(id));
    const fresh = !isLatest || playing ? byId.get(id)?.revealAt === cursor : false;
    const cls = `ix-node ${isSel ? "selected" : ""} ${dim ? "dim" : ""} ${fresh ? "fresh" : ""} ${q && matchSet.has(id) ? "match" : ""}`;

    if (id.startsWith("fork:")) {
      const f = forks.find((x) => x.id === id)!;
      const meta = STATUS_META[f.status];
      return (
        <button key={id} className={`${cls} ix-fork`} style={style} onClick={() => select(id)} onDoubleClick={() => props.onOpenLantern(id.slice(5))}>
          <span className="ix-fork-glyph" />
          <div>
            <small>Child Lantern · {meta.label}</small>
            <b>{f.label}</b>
          </div>
        </button>
      );
    }
    if (id.startsWith("sum-")) {
      const r = Number(id.slice(5));
      const inR = trace.nodes.filter((n) => n.round === r && n.revealAt <= cursor);
      const c = (k: string) => inR.filter((n) => n.kind === k).length;
      return (
        <button key={id} className={`${cls} ix-summary`} style={style} onClick={() => toggleRound(r)}>
          <span className="ix-summary-bars"><i /><i /><i /></span>
          <div>
            <small>Round {r} collapsed · select to expand</small>
            <b>
              {c("query")} queries · {c("doc")} sources · {c("claim")} claims · {c("question")} questions
            </b>
          </div>
          <Icon name="expand" size={16} />
        </button>
      );
    }
    const n = byId.get(id)!;
    const st = nodeStatus(n, cursor);
    const onClick = () => select(id);
    switch (n.kind) {
      case "intent":
        return (
          <button key={id} className={`${cls} ix-intent`} style={style} onClick={onClick}>
            <small>{n.sub}</small>
            <b>{n.label}</b>
          </button>
        );
      case "inherited":
        return (
          <button key={id} className={`${cls} ix-inherited`} style={style} onClick={onClick}>
            <Icon name="lantern" size={15} />
            <div>
              <small>Inherited context · read-only</small>
              <b>{n.label}</b>
            </div>
          </button>
        );
      case "round": {
        const isCollapsed = collapsed.has(n.round);
        return (
          <div key={id} className={`${cls} ix-round`} style={style}>
            <button className="ix-round-main" onClick={onClick}>
              <span>{String(n.round).padStart(2, "0")}</span>
              <div>
                <small>{n.sub}</small>
                <b>{n.label}</b>
              </div>
            </button>
            <button className="ix-round-toggle" title={isCollapsed ? "Expand round" : "Collapse round"} onClick={() => toggleRound(n.round)}>
              <Icon name={isCollapsed ? "expand" : "collapse"} size={14} />
            </button>
          </div>
        );
      }
      case "query":
        return (
          <button key={id} className={`${cls} ix-query`} style={style} onClick={onClick}>
            <small>
              <Icon name="search" size={11} /> {n.sub}
            </small>
            <b>“{n.label}”</b>
          </button>
        );
      case "group": {
        const docs = docsOf(trace, id).filter((d) => d.revealAt <= cursor);
        const passages = docs.flatMap((d) => passagesOf(trace, d.id)).filter((p) => p.revealAt <= cursor);
        const open = expanded.has(id);
        const shared = trace.edges.some((e) => e.kind === "sharedOrigin" && docs.some((d) => d.id === e.from));
        return (
          <button
            key={id}
            className={`${cls} ix-group ${open ? "open" : ""}`}
            style={{ ...style, height: layout.pos[id].h }}
            onClick={() => {
              select(id);
              toggleExpand(id);
            }}
          >
            <span className="cluster-stack"><i /><i /><i /></span>
            <div>
              <small>Source group</small>
              <b>{n.label}</b>
              <em>
                {docs.length} documents · {passages.length} passages
              </em>
              <span className="ix-origin-dots">
                {docs.map((d) => (
                  <i key={d.id} className={`o-${d.origin}`} title={d.origin} />
                ))}
                {shared && <span className="ix-shared-badge">shared origin</span>}
              </span>
            </div>
            <span className={`ix-chev ${open ? "open" : ""}`}>
              <Icon name="chevron" size={14} />
            </span>
          </button>
        );
      }
      case "doc": {
        const ps = passagesOf(trace, id).filter((p) => p.revealAt <= cursor);
        const open = expanded.has(id);
        return (
          <button key={id} className={`${cls} ix-doc o-${n.origin}`} style={style} onClick={onClick}>
            <span className={`ix-origin o-${n.origin}`}>{n.origin?.[0].toUpperCase()}</span>
            <div>
              <b>{n.label}</b>
              <small>{level === "detail" ? n.publisher : n.docType}</small>
            </div>
            {ps.length > 0 && (
              <span
                className={`ix-doc-toggle ${open ? "open" : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleExpand(id);
                }}
                title={open ? "Hide passages" : "Show passages"}
              >
                {ps.length}
                <Icon name="chevron" size={11} />
              </span>
            )}
          </button>
        );
      }
      case "passage":
        return (
          <button key={id} className={`${cls} ix-passage ${n.policy ?? "unscored"}`} style={style} onClick={onClick}>
            <i />
            <span>{level === "detail" ? n.text : n.label}</span>
            {n.evId && <em title="Has recorded 3D coordinates">3D</em>}
          </button>
        );
      case "claim": {
        const tone = st ? CLAIM_TONE[st.status] : "gray";
        const sup = trace.edges.filter((e) => e.to === id && e.kind === "supports" && (byId.get(e.from)?.revealAt ?? 99) <= cursor).length;
        return (
          <button key={id} className={`${cls} ix-claim tone-${tone}`} style={style} onClick={onClick}>
            <small>
              <Icon name="check" size={11} /> {st ? CLAIM_LABEL[st.status] : "Claim"}
            </small>
            <b>{n.label}</b>
            <em>
              {sup} supporting · {n.independent === undefined ? "independence not recorded" : `${n.independent} independent`}
            </em>
          </button>
        );
      }
      case "contradiction":
        return (
          <button key={id} className={`${cls} ix-contra`} style={style} onClick={onClick}>
            <small>
              <Icon name="alert" size={11} /> Contradicting evidence
            </small>
            <b>{n.label}</b>
          </button>
        );
      case "relation":
        return (
          <button key={id} className={`${cls} ix-relation`} style={style} onClick={onClick}>
            <small>Relationship between claims</small>
            <b>{n.label}</b>
          </button>
        );
      case "question":
        return (
          <button key={id} className={`${cls} ix-question status-${st?.status ?? "open"}`} style={style} onClick={onClick}>
            <Icon name="alert" size={15} />
            <div>
              <small>Open question · {st ? CLAIM_LABEL[st.status] : "Open"}</small>
              <b>{n.label}</b>
            </div>
          </button>
        );
      case "decision": {
        const o = OUTCOME[n.outcome ?? "continue"];
        const stop = n.outcome?.startsWith("stop") || n.outcome === "awaiting";
        return (
          <button key={id} className={`${cls} ix-decision ${stop ? "stop" : "go"}`} style={style} onClick={onClick}>
            <span className="ix-decision-glyph">
              <Icon name={o.icon} size={15} />
            </span>
            <div>
              <small>Convergence decision</small>
              <b>{n.label}</b>
            </div>
            {level === "journey" && <span className="ix-far-label">{n.label}</span>}
          </button>
        );
      }
      case "checkpoint": {
        const cp = trace.checkpoints.find((c) => c.id === n.checkpointId)!;
        return (
          <button
            key={id}
            className={`${cls} ix-checkpoint ${cp.resumable ? "resumable" : "viewonly"} ${snapshot?.id === cp.id ? "loaded" : ""}`}
            style={style}
            onClick={onClick}
          >
            <span className="checkpoint-gem" />
            <div>
              <small>
                {cp.short} · Recorded checkpoint
              </small>
              <b>{cp.label}</b>
              <em>{cp.resumable ? "Persisted · resumable" : "Persisted · view only"}</em>
            </div>
            {level === "journey" && (
              <span className="ix-far-label gold">
                {cp.short} · {cp.label}
              </span>
            )}
          </button>
        );
      }
      case "pending":
        return (
          <div key={id} className={`${cls} ix-pending`} style={style}>
            <span className="pulse" />
            <b>{n.label}</b>
          </div>
        );
    }
    return null;
  };

  const roundTitle = (r: number) => trace.rounds.find((x) => x.n === r);
  const transform = `translate(${view.pan.x}px, ${view.pan.y}px) scale(${view.zoom})`;
  const ids = Object.keys(layout.pos);

  return (
    <main className="app-main ix-screen">
      <header className="ix-top">
        <div className="ix-crumbs">
          <button className="ix-crumb-back" onClick={props.onBack} title={`Return to ${props.backLabel ?? "Constellation"}`}>
            <Icon name="back" size={15} />
          </button>
          <button onClick={props.onBack}>{props.backLabel ?? "Constellation"}</button>
          {parent && (
            <>
              <Icon name="chevron" size={11} />
              <button onClick={() => props.onOpenLantern(parent.id)}>{parent.title}</button>
            </>
          )}
          <Icon name="chevron" size={11} />
          <b>{lantern.title}</b>
          {persisted ? (
            <span className="ix-sim-badge persisted" data-testid="data-origin">
              <Icon name="source" size={11} /> Persisted · loaded from the exploration API
            </span>
          ) : (
            <span className="ix-sim-badge" data-testid="data-origin">
              <Icon name="spark" size={11} /> Simulated trace · illustrative events, not backend output
            </span>
          )}
        </div>
        <div className={`ix-title ${lantern.parentId ? "child" : ""}`}>
          <span className={`ix-lantern-icon ${lantern.parentId ? "child" : ""}`}>
            <Icon name="lantern" />
          </span>
          <div>
            <small>Original research question</small>
            <h1 data-testid="research-question">{question}</h1>
            {lantern.parentId && (
              <p>
                <Tag tone="violet">Branch objective</Tag> <span title={lantern.objective}>{lantern.objective}</span>
              </p>
            )}
          </div>
        </div>
        <div className="ix-top-actions">
          <span data-testid="investigation-status">
            <Tag tone={STATUS_META[lantern.status].tone}>{STATUS_META[lantern.status].label}</Tag>
          </span>
          {persisted && lantern.status === "running" && !notStarted && (
            // Continue a researching investigation: one more step through the same billable gate,
            // confirmation, idempotency key and stored budget as the first step.
            <button
              className="outline-button gold"
              data-testid="continue-research"
              onClick={props.onStartResearch}
              disabled={!props.branching?.allowInvestigate || props.branching.pending}
              title={!props.branching?.allowInvestigate ? props.branching?.investigateDisabledReason : "Runs one billable research step within the stored budget"}
            >
              <Icon name="play" size={13} /> {props.branching?.pending ? "Running research…" : "Continue research (billable)"}
            </button>
          )}
          {!persisted && (
            <button className="outline-button" onClick={props.onDemo} title="Simulated 12-step walkthrough">
              <Icon name="play" size={13} /> Guided demo
            </button>
          )}
          {props.onCompareParent && (
            <button className="outline-button" onClick={props.onCompareParent} data-testid="compare-parent">
              <Icon name="compare" size={14} /> Compare with parent
            </button>
          )}
          {props.onKnowledge && (
            <button className="outline-button" onClick={props.onKnowledge} data-testid="open-knowledge">
              <Icon name="knowledge" size={14} /> Knowledge
            </button>
          )}
          {props.onFindings && (
            <button className="outline-button" onClick={props.onFindings} data-testid="open-findings">
              <Icon name="check" size={14} /> Findings
            </button>
          )}
          <button className="outline-button" onClick={() => props.onOpen3D(null)}>
            <Icon name="cube" size={15} /> 3D evidence
          </button>
          <button
            className="outline-button"
            disabled={trace.checkpoints.length < 2}
            onClick={() => {
              const cps = trace.checkpoints;
              props.onCompare(cps[Math.max(0, cps.length - 3)]?.id ?? cps[0].id, cps[cps.length - 1].id);
            }}
          >
            <Icon name="compare" size={15} /> Compare checkpoints
          </button>
          {props.onConstellation && (
            <button className="outline-button" onClick={props.onConstellation} data-testid="open-constellation">
              <Icon name="lantern" size={14} /> Constellation
            </button>
          )}
          {parent ? (
            <button className="outline-button" onClick={() => props.onOpenLantern(parent.id)}>
              <Icon name="back" size={15} /> Parent investigation
            </button>
          ) : null}
          <button className="outline-button gold" onClick={props.onBack}>
            Return to {props.backLabel ?? "Constellation"}
          </button>
        </div>
      </header>

      <div className="ix-workspace">
        <section className="ix-canvas">
          <div className="ix-toolbar">
            <div className="ix-search">
              <Icon name="search" size={14} />
              <input
                value={search}
                placeholder="Find in investigation — queries, sources, claims…"
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSearchOpen(true);
                }}
                onFocus={() => setSearchOpen(true)}
              />
              {search && (
                <button onClick={() => setSearch("")} title="Clear">
                  <Icon name="close" size={12} />
                </button>
              )}
              {searchOpen && q && (
                <div className="ix-search-results">
                  {matches.length === 0 && <p>No recorded items match.</p>}
                  {matches.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        reveal(m.id);
                        setSearchOpen(false);
                      }}
                    >
                      <span className={`ix-kind-dot k-${m.kind}`} />
                      <span>
                        <b>{m.label}</b>
                        <small>
                          {m.kind} · {m.round ? `round ${m.round}` : "intent"}
                          {m.revealAt > cursor ? ` · appears later (event ${m.revealAt + 1})` : ""}
                        </small>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <span className="ix-stats">
              {stats.rounds} rounds · {stats.queries} searches · {stats.sources} sources · {stats.claims} claims ·{" "}
              {stats.openQuestions} open questions · {stats.checkpoints} checkpoints
            </span>
            <div className="ix-zoom">
              <div className="ix-levels" role="group" aria-label="Semantic zoom">
                {(
                  [
                    ["journey", "Journey", 0.3],
                    ["rounds", "Rounds", 0.78],
                    ["detail", "Detail", 1.2],
                  ] as const
                ).map(([k, label, z]) => (
                  <button key={k} className={level === k ? "active" : ""} onClick={() => (k === "journey" ? fitBoxes(visibleIds().map((i) => layout.pos[i]), { max: 0.45 }) : zoomTo(z))}>
                    {label}
                  </button>
                ))}
              </div>
              <button onClick={() => zoomTo(Math.max(0.16, view.zoom / 1.2))} title="Zoom out">
                <Icon name="minus" size={14} />
              </button>
              <span className="ix-zoom-pct">{Math.round(view.zoom * 100)}%</span>
              <button onClick={() => zoomTo(Math.min(1.8, view.zoom * 1.2))} title="Zoom in">
                <Icon name="plus" size={14} />
              </button>
              <button onClick={() => fitBoxes(visibleIds().map((i) => layout.pos[i]))} title="Fit entire investigation">
                <Icon name="fit" size={14} /> Fit
              </button>
              <button
                disabled={!view.selected}
                onClick={() => view.selected && fitBoxes([...related].concat(view.selected).map((i) => layout.pos[layout.anchorOf(i) ?? ""]).filter(Boolean), { min: 0.4, max: 1.1 })}
                title="Fit to selection and related evidence"
              >
                <Icon name="target" size={14} /> Selection
              </button>
              <button className={minimap ? "active" : ""} onClick={() => setMinimap(!minimap)} title="Toggle minimap">
                <Icon name="map" size={14} />
              </button>
            </div>
          </div>

          <div className={`ix-mode ix-mode-${mode}`}>
            {mode === "live" && (
              <>
                <span className="ix-mode-dot" />
                <b>Latest recorded state</b>
                <span>{lantern.status === "researching" ? "Live — new events appear as they are recorded." : `Event ${cursor + 1} of ${latest + 1}`}</span>
              </>
            )}
            {mode === "history" && (
              <>
                <Icon name="history" size={14} />
                <b>Historical playback</b>
                <span>
                  Showing recorded history up to event {cursor + 1} of {latest + 1}: “{event?.label}”. Event views are read-only —
                  research cannot resume from here unless a checkpoint was saved.
                </span>
                <button onClick={() => seek(latest)}>Return to latest</button>
              </>
            )}
            {mode === "snapshot" && snapshot && (
              <>
                <span className="tiny-gem" />
                <b>Checkpoint snapshot loaded · {snapshot.short}</b>
                <span>
                  Persisted state “{snapshot.label}”. {persisted
                    ? props.branching
                      ? "Recorded snapshot from the backend — you can save a child Lantern from it."
                      : "Recorded snapshot from the backend — read-only."
                    : snapshot.resumable
                      ? "Resumable — you can fork or continue from here."
                      : "View only — this snapshot cannot be resumed."}
                </span>
                <button onClick={() => seek(latest)}>Return to latest</button>
              </>
            )}
          </div>

          {notStarted && (
            <div className="ix-not-started">
              <Icon name="lantern" size={22} />
              <div>
                <b>This Lantern has not started researching</b>
                <p>
                  {lantern.parentId ? "It was saved with its branch objective and inherited context." : "Its question and budget are saved."} No searches have been recorded
                  {persisted ? " for it yet" : ", so there is nothing to play back yet"}.
                  {persisted && !props.branching?.allowInvestigate && props.branching?.investigateDisabledReason ? ` ${props.branching.investigateDisabledReason}` : ""}
                </p>
              </div>
              <button
                className="primary"
                data-testid="start-research"
                onClick={props.onStartResearch}
                disabled={persisted && (!props.branching?.allowInvestigate || props.branching.pending)}
                title={persisted && !props.branching?.allowInvestigate ? props.branching?.investigateDisabledReason : undefined}
              >
                <Icon name="branch" size={14} /> {persisted ? (props.branching?.pending ? "Running research…" : "Run research step (billable)") : "Start research"}
              </button>
            </div>
          )}

          <div
            ref={stageRef}
            className={`ix-stage level-${level} ${drag.current ? "dragging" : ""}`}
            tabIndex={0}
            role="region"
            aria-label="Investigation map. Arrow keys pan, plus and minus zoom, 0 fits everything, Tab moves between items, Escape clears the selection."
            onKeyDown={(e) => {
              // Keyboard navigation of the map itself (items inside are buttons and handle their own keys).
              if (e.target !== e.currentTarget) {
                if (e.key === "Escape") setView({ selected: null });
                return;
              }
              const step = e.shiftKey ? 240 : 80;
              const pan = { ...view.pan };
              if (e.key === "ArrowLeft") pan.x += step;
              else if (e.key === "ArrowRight") pan.x -= step;
              else if (e.key === "ArrowUp") pan.y += step;
              else if (e.key === "ArrowDown") pan.y -= step;
              else if (e.key === "+" || e.key === "=") return (e.preventDefault(), zoomTo(Math.min(1.8, view.zoom * 1.2)));
              else if (e.key === "-" || e.key === "_") return (e.preventDefault(), zoomTo(Math.max(0.16, view.zoom / 1.2)));
              else if (e.key === "0") return (e.preventDefault(), fitBoxes(visibleIds().map((i) => layout.pos[i])));
              else if (e.key === "Escape") return setView({ selected: null });
              else return;
              e.preventDefault();
              setView({ pan });
            }}
            onPointerDown={(e) => {
              if ((e.target as HTMLElement).closest("button")) return;
              (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
              drag.current = { x: e.clientX, y: e.clientY, px: view.pan.x, py: view.pan.y, moved: false };
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d) return;
              const dx = e.clientX - d.x;
              const dy = e.clientY - d.y;
              if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
              setView({ pan: { x: d.px + dx, y: d.py + dy } });
              flashInstant();
            }}
            onPointerUp={() => {
              if (drag.current && !drag.current.moved) setSearchOpen(false);
              drag.current = null;
            }}
          >
            <div className={`ix-world ${instant ? "instant" : ""}`} style={{ transform }}>
              <svg className="ix-backdrop" style={{ left: -3000, top: -400, width: 6000, height: layout.bounds.maxY + 800 }} viewBox={`-3000 -400 6000 ${layout.bounds.maxY + 800}`}>
                <defs>
                  <linearGradient id="ixSil" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="#7897ff" stopOpacity=".07" />
                    <stop offset=".55" stopColor="#54cdb8" stopOpacity=".06" />
                    <stop offset="1" stopColor="#e8b66d" stopOpacity=".1" />
                  </linearGradient>
                </defs>
                {layout.bands
                  .filter((b) => b.round > 0 && b.phase !== "checkpoint")
                  .map((b, i) => (
                    <g key={i} className={`ix-band ${b.phase}`}>
                      <rect x={-3000} y={b.y0} width={6000} height={b.y1 - b.y0} />
                    </g>
                  ))}
                {layout.silhouettes.map((s) => {
                  // only draw the converged lantern shape once the round has actually converged
                  const inRound = trace.nodes.filter((n) => n.round === s.round);
                  if (!inRound.length || Math.max(...inRound.map((n) => n.revealAt)) > cursor) return null;
                  return <path key={s.round} className="ix-silhouette" d={s.d} />;
                })}
              </svg>
              {/* round / phase labels on the left margin */}
              {layout.bands
                .filter((b) => b.round > 0 && b.phase !== "checkpoint")
                .filter((b) => trace.nodes.some((n) => n.round === b.round && n.kind === "round" && n.revealAt <= cursor))
                .map((b, i) => (
                  <div
                    key={i}
                    className={`ix-band-label ${b.phase}`}
                    style={{
                      left: layout.bounds.minX - 40,
                      top: b.y0 + 14,
                      fontSize: Math.max(10, 10 / view.zoom),
                    }}
                  >
                    {b.phase === "explore" && (
                      <>
                        <b>Round {b.round}</b> · Explore
                        {level === "journey" && <em>{roundTitle(b.round)?.title}</em>}
                      </>
                    )}
                    {b.phase === "evaluate" && <>Evaluate evidence</>}
                    {b.phase === "decide" && <>Decide</>}
                  </div>
                ))}
              <svg className="ix-edges" style={{ left: -3000, top: -400, width: 6000, height: layout.bounds.maxY + 800 }} viewBox={`-3000 -400 6000 ${layout.bounds.maxY + 800}`}>
                <defs>
                  {(["contradicts", "prompted", "fork", "supports", "retrieved", "order", "considered", "raised", "sharedOrigin"] as const).map((k) => (
                    <marker key={k} id={`ix-arrow-${k}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M0,0 L8,4 L0,8 Z" className={`ix-arrowhead ${k}`} />
                    </marker>
                  ))}
                </defs>
                {edges.map((e) => {
                  const a = layout.pos[e.a];
                  const b = layout.pos[e.b];
                  if (!a || !b || !isVisible(e.a) || !isVisible(e.b)) return null;
                  const d = edgePath(a, b);
                  const dimmed = view.selected && !e.hl && !(view.selected === e.a || view.selected === e.b);
                  return (
                    <path
                      key={`${e.a}>${e.b}:${e.kind}`}
                      d={d}
                      className={`ix-edge ${e.kind} ${e.hl ? "hl" : ""} ${dimmed ? "dim" : ""}`}
                      markerEnd={["supports", "contradicts", "prompted", "fork", "raised", "retrieved"].includes(e.kind) ? `url(#ix-arrow-${e.kind})` : undefined}
                      strokeWidth={e.count > 1 ? Math.min(4, 1.2 + e.count * 0.5) : undefined}
                    />
                  );
                })}
              </svg>
              {ids.map(renderNode)}
            </div>

            {minimap && (
              <Minimap
                layout={layout}
                ids={ids.filter(isVisible)}
                trace={trace}
                view={view}
                size={size}
                onJump={(x, y) => setView({ pan: { x: size.w / 2 - x * view.zoom, y: size.h / 2 - y * view.zoom } })}
              />
            )}
          </div>

          <div className="ix-legend">
            <div className="ix-legend-nodes">
              <span><i className="k-agent" />What the agent did</span>
              <span><i className="k-evidence" />What the evidence shows</span>
              <span><i className="k-question" />Open question</span>
              <span><i className="k-decision" />Convergence decision</span>
              <span><i className="k-checkpoint" />Recorded checkpoint</span>
              <span><i className="k-fork" />Child Lantern</span>
            </div>
            <div className="ix-legend-edges">
              {EDGE_LEGEND.map((l) => (
                <button
                  key={l.kind}
                  className={hiddenEdges.has(l.kind) ? "off" : ""}
                  onClick={() => {
                    const next = new Set(hiddenEdges);
                    if (next.has(l.kind)) next.delete(l.kind);
                    else next.add(l.kind);
                    setHiddenEdges(next);
                  }}
                  title="Show / hide this relationship type"
                >
                  <svg width="22" height="6"><path d="M1 3H21" className={`ix-edge ${l.kind}`} /></svg>
                  {l.label}
                </button>
              ))}
            </div>
          </div>
          <div className="ix-help">Drag to pan · Scroll to zoom · Select any object to inspect · Double-click a child Lantern to enter it</div>
        </section>

        <TraceInspector
          question={question}
          readOnly={persisted && !props.branching}
          readOnlyReason={persisted && !props.branching ? "Branching is unavailable: this backend connection is read-only." : undefined}
          branching={props.branching}
          lantern={lantern}
          trace={trace}
          node={selectedNode}
          forkStub={view.selected?.startsWith("fork:") ? lanterns.find((l) => l.id === view.selected!.slice(5)) ?? null : null}
          cursor={cursor}
          latest={latest}
          snapshot={snapshot}
          composer={view.composer}
          expanded={expanded}
          onSelect={(id) => reveal(id)}
          onFocus={(ids) => focusOn(ids)}
          onToggleExpand={toggleExpand}
          onSeek={(s) => seek(s)}
          onLoadSnapshot={(cpId) => {
            const cp = trace.checkpoints.find((c) => c.id === cpId)!;
            setView((v) => ({ cursor: cp.seq >= latest ? -1 : cp.seq, snapshot: cpId, selected: cp.nodeId, composer: null, focusIds: [cp.nodeId], focusNonce: v.focusNonce + 1 }));
          }}
          onLatest={() => seek(latest)}
          onCompose={(draft) => setView({ composer: draft })}
          onCreate={props.onCreateFork}
          onCompare={props.onCompare}
          onOpen3D={props.onOpen3D}
          onOpenLantern={props.onOpenLantern}
          onExpandRound={(r) =>
            setView((v) => ({
              expanded: Array.from(new Set([...v.expanded, ...trace.nodes.filter((n) => n.round === r && n.kind === "group").map((n) => n.id)])),
              collapsedRounds: v.collapsedRounds.filter((x) => x !== r),
            }))
          }
          onClose={() => select(null)}
        />
      </div>

      <Timeline
        trace={trace}
        cursor={cursor}
        latest={latest}
        playing={playing}
        granularity={view.granularity}
        snapshot={snapshot?.id ?? null}
        follow={follow}
        setFollow={setFollow}
        onPlay={() => {
          if (!playing && cursor >= latest) seek(0);
          setPlaying(!playing);
        }}
        onStep={(d) => {
          setPlaying(false);
          step(d);
        }}
        onSeek={(s) => {
          setPlaying(false);
          seek(s);
        }}
        onGranularity={(g) => setView({ granularity: g })}
        onCheckpoint={(cpId) => {
          setPlaying(false);
          const cp = trace.checkpoints.find((c) => c.id === cpId)!;
          setView((v) => ({ cursor: cp.seq >= latest ? -1 : cp.seq, snapshot: null, selected: cp.nodeId, composer: null, focusIds: [cp.nodeId], focusNonce: v.focusNonce + 1 }));
        }}
      />
    </main>
  );
}

function Minimap({
  layout,
  ids,
  trace,
  view,
  size,
  onJump,
}: {
  layout: ReturnType<typeof computeLayout>;
  ids: string[];
  trace: Trace;
  view: ViewState;
  size: { w: number; h: number };
  onJump: (x: number, y: number) => void;
}) {
  const W = 168;
  const H = 128;
  const { minX, minY, maxX, maxY } = layout.bounds;
  const s = Math.min((W - 12) / (maxX - minX), (H - 12) / (maxY - minY));
  const ox = (W - (maxX - minX) * s) / 2 - minX * s;
  const oy = (H - (maxY - minY) * s) / 2 - minY * s;
  const vx = (-view.pan.x / view.zoom) * s + ox;
  const vy = (-view.pan.y / view.zoom) * s + oy;
  const kindOf = (id: string): TraceNode["kind"] | "summary" =>
    id.startsWith("fork:") ? "fork" : id.startsWith("sum-") ? "summary" : trace.nodes.find((n) => n.id === id)?.kind ?? "doc";
  return (
    <svg
      className="ix-minimap"
      width={W}
      height={H}
      onPointerDown={(e) => {
        e.stopPropagation();
        const r = e.currentTarget.getBoundingClientRect();
        onJump((e.clientX - r.left - ox) / s, (e.clientY - r.top - oy) / s);
      }}
    >
      {ids.map((id) => {
        const b = layout.pos[id];
        return <rect key={id} className={`mm-${kindOf(id)}`} x={b.x * s + ox} y={b.y * s + oy} width={Math.max(2, b.w * s)} height={Math.max(2, b.h * s)} rx={1} />;
      })}
      <rect className="mm-view" x={vx} y={vy} width={(size.w / view.zoom) * s} height={(size.h / view.zoom) * s} />
    </svg>
  );
}
