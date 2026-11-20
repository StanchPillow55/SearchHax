import { useState } from "react";
import { Icon, InfoBlock, Tag } from "../shared";
import { QUESTION, STATUS_META, summarize } from "./data";
import { computeLayout } from "./layout";
import type { Lantern, Trace } from "./types";

/*
 * Preserves the original Lantern Constellation composition (parent lantern on top,
 * violet children below) and makes every Lantern enterable. Children now visibly emerge
 * from the specific parent checkpoint they were created from.
 */

const PARENT = { x: 335, y: 50, w: 250, h: 190 };
const RAIL_X = 460;
const RAIL_Y0 = 268;
const RAIL_STEP = 36;
const SLOTS = [
  { x: 120, y: 450 },
  { x: 360, y: 492 },
  { x: 610, y: 445 },
  { x: 740, y: 280 },
  { x: 40, y: 250 },
  { x: 735, y: 30 },
  { x: 25, y: 40 },
];

export function ConstellationView({
  lanterns,
  traces,
  latestOf,
  highlight,
  onOpen,
  onOpenAt,
  onCompareLanterns,
  onBack,
  onDemo,
}: {
  lanterns: Lantern[];
  traces: Record<string, Trace>;
  latestOf: (id: string) => number;
  highlight: string | null;
  onOpen: (id: string) => void;
  onOpenAt: (id: string, nodeId: string) => void;
  onCompareLanterns: () => void;
  onBack: () => void;
  onDemo: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(highlight);
  const [preview, setPreview] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState(false);
  const parent = lanterns.find((l) => !l.parentId)!;
  const ptrace = traces[parent.id];
  const children = lanterns.filter((l) => l.parentId === parent.id);
  const cps = ptrace.checkpoints;
  const cpY = (id?: string) => RAIL_Y0 + cps.findIndex((c) => c.id === id) * RAIL_STEP;
  const sel = lanterns.find((l) => l.id === selected) ?? null;

  const stat = (l: Lantern) => summarize(traces[l.id], latestOf(l.id));

  return (
    <main className="app-main constellation-screen">
      <header className="topbar">
        <div className="question-title">
          <button className="icon-button" onClick={onBack} title="Back to results">
            <Icon name="back" />
          </button>
          <div>
            <small>Active research question</small>
            <h1>{QUESTION}</h1>
          </div>
        </div>
        <div className="top-actions">
          <Tag tone="amber">Stopped with uncertainty</Tag>
          <button className="outline-button gold" onClick={onDemo}>
            <Icon name="play" size={14} /> Guided demo
          </button>
        </div>
      </header>
      <div className="const-head">
        <div>
          <small>Investigation constellation</small>
          <h2>One question, {lanterns.length} paths of inquiry</h2>
          <p>Zoom out to understand the research landscape. Double-click any Lantern — or choose Explore — to step inside it.</p>
        </div>
        <div>
          <button className="outline-button" onClick={onCompareLanterns}>
            <Icon name="compare" /> Compare Lanterns
          </button>
          <button className="primary-button" onClick={() => onOpen(parent.id)}>
            <Icon name="zoom" /> Explore parent investigation
          </button>
        </div>
      </div>
      <div className="const-body">
        <section className={`const-canvas ${zoomed ? "zoomed" : ""}`}>
          <div className="const-controls">
            <button onClick={() => setZoomed(!zoomed)}>
              <Icon name="zoom" />
            </button>
            <button onClick={() => setZoomed(false)}>Fit all</button>
            <span>
              {lanterns.length} Lanterns · {lanterns.reduce((a, l) => a + stat(l).sources, 0)} recorded sources · {cps.length} parent checkpoints
            </span>
          </div>
          <div className="constellation-graph cx-graph">
            <svg viewBox="0 0 950 640" preserveAspectRatio="none">
              <defs>
                <linearGradient id="line" x1="0" y1="0" x2="0" y2="1">
                  <stop stopColor="#6d8eff" />
                  <stop offset=".55" stopColor="#4cc9b0" />
                  <stop offset="1" stopColor="#e7ad5e" />
                </linearGradient>
              </defs>
              <path className="const-main" d={`M${RAIL_X} ${PARENT.y + PARENT.h} V${cpY(cps[cps.length - 1].id)}`} />
              {children.map((c) => {
                const slot = SLOTS[c.slot ?? 0];
                const sy = cpY(c.fromCheckpoint);
                const ex = slot.x + 100;
                const ey = slot.y < sy ? slot.y + 123 : slot.y;
                const horizontal = Math.abs(slot.y + 60 - sy) < 120;
                const d = horizontal
                  ? `M${RAIL_X} ${sy} C${(RAIL_X + slot.x) / 2} ${sy} ${(RAIL_X + slot.x) / 2} ${slot.y + 60} ${slot.x > RAIL_X ? slot.x : slot.x + 200} ${slot.y + 60}`
                  : `M${RAIL_X} ${sy} C${RAIL_X} ${(sy + ey) / 2} ${ex} ${(sy + ey) / 2} ${ex} ${ey}`;
                return <path key={c.id} className={`cx-link ${c.userCreated ? "new" : ""} ${selected === c.id ? "hl" : ""}`} d={d} />;
              })}
            </svg>

            <button
              className={`parent-lantern cx-parent ${selected === parent.id ? "cx-selected" : ""}`}
              style={{ left: PARENT.x, top: PARENT.y, width: PARENT.w, height: PARENT.h }}
              onClick={() => setSelected(parent.id)}
              onDoubleClick={() => onOpen(parent.id)}
            >
              <span className="lantern-shape">
                <i />
                <i />
              </span>
              <Tag tone="amber">Parent · stopped</Tag>
              <b>{parent.title}</b>
              <small>
                {stat(parent).rounds} rounds · {stat(parent).sources} sources · {stat(parent).openQuestions} open questions
              </small>
            </button>

            {/* checkpoint rail: where children were created from */}
            {cps.map((c) => (
              <button
                key={c.id}
                className={`cx-rail-gem ${c.resumable ? "" : "viewonly"}`}
                style={{ left: RAIL_X, top: cpY(c.id) }}
                onClick={() => onOpenAt(parent.id, c.nodeId)}
                title={`${c.short} · ${c.label} — open in investigation`}
              >
                <span className="tiny-gem" />
                <em>
                  {c.short} · {c.label}
                </em>
              </button>
            ))}

            {children.map((c) => {
              const slot = SLOTS[c.slot ?? 0];
              const meta = STATUS_META[c.status];
              const s = stat(c);
              const cp = cps.find((x) => x.id === c.fromCheckpoint);
              return (
                <div key={c.id} className="cx-child-wrap" style={{ left: slot.x, top: slot.y }}>
                  <button
                    className={`child-lantern cx-child status-${c.status} ${selected === c.id ? "cx-selected" : ""} ${highlight === c.id ? "newly-created" : ""}`}
                    onClick={() => setSelected(c.id)}
                    onDoubleClick={() => onOpen(c.id)}
                  >
                    <span className={`child-shape ${c.status === "not-started" ? "hollow" : ""}`} />
                    <Tag tone={meta.tone}>
                      {c.status === "researching" && <span className="cx-live" />}
                      {meta.label}
                    </Tag>
                    <b>{c.title}</b>
                    <small>
                      {c.status === "not-started"
                        ? `Not started · from ${cp?.short}`
                        : `${s.rounds} rounds · ${s.sources} sources · ${s.openQuestions} open · ${s.checkpoints} checkpoints`}
                    </small>
                  </button>
                  <div className="cx-child-actions">
                    <button onClick={() => setPreview(preview === c.id ? null : c.id)}>
                      <Icon name={preview === c.id ? "collapse" : "expand"} size={12} /> {preview === c.id ? "Hide" : "Preview"}
                    </button>
                    <button className="go" onClick={() => onOpen(c.id)}>
                      Explore <Icon name="arrow" size={12} />
                    </button>
                  </div>
                  {preview === c.id && <MiniTrace trace={traces[c.id]} latest={latestOf(c.id)} />}
                </div>
              );
            })}
          </div>
          <div className="const-legend">
            <span><i className="parent-key" />Parent checkpoint</span>
            <span><i className="active-key" />Child Lantern</span>
            <span><i className="relation-key" />Created from checkpoint</span>
            <span><span className="tiny-gem" />Recorded checkpoint</span>
            <span><span className="cx-hollow-key" />Saved · not started</span>
          </div>
        </section>
        {sel && (
          <LanternPanel
            lantern={sel}
            trace={traces[sel.id]}
            latest={latestOf(sel.id)}
            parentTrace={ptrace}
            onClose={() => setSelected(null)}
            onOpen={() => onOpen(sel.id)}
            onOpenAt={(nodeId) => onOpenAt(sel.id, nodeId)}
          />
        )}
      </div>
    </main>
  );
}

function MiniTrace({ trace, latest }: { trace: Trace; latest: number }) {
  const layout = computeLayout(trace, new Set(), new Set());
  const ids = Object.keys(layout.pos).filter((id) => (trace.nodes.find((n) => n.id === id)?.revealAt ?? 99) <= latest);
  if (ids.length === 0) return null;
  const { minX, minY, maxX } = layout.bounds;
  const maxY = Math.max(...ids.map((id) => layout.pos[id].y + layout.pos[id].h));
  const W = 196;
  const H = 120;
  const s = Math.min((W - 10) / (maxX - minX), (H - 10) / (maxY - minY));
  return (
    <div className="cx-preview">
      <svg width={W} height={H}>
        {layout.silhouettes.map((sil) => (
          <path key={sil.round} d={sil.d} transform={`translate(${W / 2 - ((minX + maxX) / 2) * s} ${5 - minY * s}) scale(${s})`} className="cx-preview-sil" />
        ))}
        {ids.map((id) => {
          const b = layout.pos[id];
          const n = trace.nodes.find((x) => x.id === id)!;
          return (
            <rect
              key={id}
              className={`mm-${n.kind}`}
              x={W / 2 + (b.x - (minX + maxX) / 2) * s}
              y={5 + (b.y - minY) * s}
              width={Math.max(2, b.w * s)}
              height={Math.max(2, b.h * s)}
              rx={1}
            />
          );
        })}
      </svg>
      <small>Internal structure · expand → converge per round</small>
    </div>
  );
}

function LanternPanel({
  lantern,
  trace,
  latest,
  parentTrace,
  onClose,
  onOpen,
  onOpenAt,
}: {
  lantern: Lantern;
  trace: Trace;
  latest: number;
  parentTrace: Trace;
  onClose: () => void;
  onOpen: () => void;
  onOpenAt: (nodeId: string) => void;
}) {
  const s = summarize(trace, latest);
  const meta = STATUS_META[lantern.status];
  const from = parentTrace.checkpoints.find((c) => c.id === lantern.fromCheckpoint);
  const lastDecision = [...trace.nodes].reverse().find((n) => n.kind === "decision" && n.revealAt <= latest);
  return (
    <aside className="inspector cx-panel">
      <div className="inspector-head">
        <div>
          <small>{lantern.parentId ? "Child Lantern" : "Parent Lantern"}</small>
          <h2>{lantern.title}</h2>
        </div>
        <button className="icon-button" onClick={onClose}>
          <Icon name="close" />
        </button>
      </div>
      <div className="inspector-scroll">
        <Tag tone={meta.tone}>{meta.label}</Tag>
        <InfoBlock label={lantern.parentId ? "Branch objective" : "Research question"}>
          <p>{lantern.objective}</p>
        </InfoBlock>
        <InfoBlock label="Inside this Lantern">
          <div className="ix-overview-grid">
            <span><b>{s.rounds}</b>search rounds</span>
            <span><b>{s.sources}</b>sources</span>
            <span><b>{s.openQuestions}</b>open questions</span>
            <span><b>{s.checkpoints}</b>checkpoints</span>
          </div>
          {lantern.status === "not-started" ? (
            <p className="ix-muted">This Lantern was saved without research. Nothing has been recorded yet.</p>
          ) : (
            <MiniTrace trace={trace} latest={latest} />
          )}
        </InfoBlock>
        {lastDecision && (
          <InfoBlock label="Latest recorded decision">
            <p>{lastDecision.label}</p>
          </InfoBlock>
        )}
        {from && (
          <InfoBlock label="Created from parent checkpoint">
            <p>
              <span className="tiny-gem" /> {from.short} · {from.label}
            </p>
          </InfoBlock>
        )}
        <InfoBlock label="Checkpoints">
          {trace.checkpoints.filter((c) => c.seq <= latest).length === 0 && <p className="ix-muted">None recorded yet.</p>}
          {trace.checkpoints
            .filter((c) => c.seq <= latest)
            .map((c) => (
              <button key={c.id} className="ix-link k-checkpoint" onClick={() => onOpenAt(c.nodeId)}>
                <span className="tiny-gem" />
                <span>
                  {c.short} · {c.label}
                </span>
                <em>{c.resumable ? "resumable" : "view only"}</em>
              </button>
            ))}
        </InfoBlock>
      </div>
      <div className="inspector-actions">
        <button className="primary" onClick={onOpen}>
          <Icon name="zoom" /> Explore investigation
        </button>
      </div>
    </aside>
  );
}
