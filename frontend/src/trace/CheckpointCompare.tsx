import { Icon, Tag } from "../shared";
import { summarize } from "./data";
import { CLAIM_LABEL, CLAIM_TONE, nodeStatus } from "./graph";
import { computeLayout } from "./layout";
import type { Lantern, Trace, TraceNode } from "./types";

export function CheckpointCompare({
  lantern,
  trace,
  a,
  b,
  setPair,
  onBack,
  onShow,
}: {
  lantern: Lantern;
  trace: Trace;
  a: string;
  b: string;
  setPair: (a: string, b: string) => void;
  onBack: () => void;
  onShow: (nodeId: string, checkpointId: string) => void;
}) {
  let A = trace.checkpoints.find((c) => c.id === a)!;
  let B = trace.checkpoints.find((c) => c.id === b)!;
  const swapped = A.seq > B.seq;
  if (swapped) [A, B] = [B, A];
  const same = A.id === B.id;
  const between = (n: TraceNode) => n.revealAt > A.seq && n.revealAt <= B.seq;
  const known = (n: TraceNode) => n.revealAt <= A.seq;
  const limited = !A.recordsClaims || !B.recordsClaims;

  const newDocs = trace.nodes.filter((n) => n.kind === "doc" && between(n));
  const newClaims = trace.nodes.filter((n) => (n.kind === "claim" || n.kind === "relation") && between(n));
  const newContras = trace.nodes.filter((n) => n.kind === "contradiction" && between(n));
  const revised = trace.nodes.filter((n) => {
    if (n.kind !== "claim" || !known(n)) return false;
    return nodeStatus(n, A.seq)?.status !== nodeStatus(n, B.seq)?.status;
  });
  const questions = trace.nodes.filter((n) => n.kind === "question" && n.revealAt <= B.seq);
  const qState = (n: TraceNode) => {
    const at = known(n) ? nodeStatus(n, A.seq)?.status : null;
    const bt = nodeStatus(n, B.seq)?.status ?? "open";
    if (!at) return { kind: "new", label: "Newly opened", at, bt };
    if (bt === "resolved") return { kind: "resolved", label: "Resolved", at, bt };
    if (at !== bt) return { kind: "changed", label: "Status changed", at, bt };
    return { kind: "open", label: "Still open", at, bt };
  };
  const sA = summarize(trace, A.seq);
  const sB = summarize(trace, B.seq);

  // mini map with change highlighting (all rounds expanded, groups expanded so sources show)
  const groups = trace.nodes.filter((n) => n.kind === "group").map((n) => n.id);
  const layout = computeLayout(trace, new Set(groups), new Set());
  const ids = Object.keys(layout.pos).filter((id) => {
    const n = trace.nodes.find((x) => x.id === id);
    return n && n.revealAt <= B.seq;
  });
  const { minX, minY, maxX } = layout.bounds;
  const maxY = Math.max(...ids.map((id) => layout.pos[id].y + layout.pos[id].h));
  const W = 300;
  const s = Math.min((W - 20) / (maxX - minX), 1);
  const H = (maxY - minY) * s + 20;
  const changeClass = (id: string) => {
    const n = trace.nodes.find((x) => x.id === id)!;
    if (revised.some((r) => r.id === id)) return "revised";
    if (known(n)) return "before";
    return "after";
  };

  const Item = ({ n, children }: { n: TraceNode; children?: React.ReactNode }) => (
    <button className="cmp-item" onClick={() => onShow(n.id, B.id)}>
      <span className={`ix-kind-dot k-${n.kind}`} />
      <span>
        {n.label}
        {children}
      </span>
      <Icon name="arrow" size={12} />
    </button>
  );
  const NotRecorded = ({ cp }: { cp: typeof A }) => (
    <p className="cmp-unrecorded">
      <Icon name="alert" size={12} /> Not recorded at {cp.short} — only supported differences are shown.
    </p>
  );

  return (
    <main className="app-main cmp-screen">
      <header className="cmp-head">
        <div>
          <button className="icon-button" onClick={onBack} title="Return to investigation">
            <Icon name="back" />
          </button>
          <span>
            <small>{lantern.title} · checkpoint comparison</small>
            <h1>What changed between two recorded checkpoints?</h1>
          </span>
        </div>
        <div className="cmp-head-actions">
          <span className="ix-sim-badge">
            <Icon name="spark" size={11} /> Simulated · illustrative
          </span>
          <button className="outline-button" onClick={onBack}>
            Return to investigation
          </button>
        </div>
      </header>

      <div className="cmp-selectors">
        {[
          { label: "Checkpoint A", cp: A, s: sA, tone: "blue", which: "a" },
          { label: "Checkpoint B", cp: B, s: sB, tone: "amber", which: "b" },
        ].map(({ label, cp, s: st, tone, which }, i) => (
          <div key={label} className={`cmp-sel ${which}`}>
            <Tag tone={tone}>{label}</Tag>
            <select
              value={cp.id}
              onChange={(e) => (which === "a" ? setPair(e.target.value, B.id) : setPair(A.id, e.target.value))}
            >
              {trace.checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.short} · {c.label}
                </option>
              ))}
            </select>
            <small>
              Event {cp.seq + 1} · {st.sources} sources · {cp.recordsClaims ? `${st.claims} claims · ${st.openQuestions} open questions` : "claims not recorded"}
            </small>
            {i === 0 && <span className="cmp-vs"><Icon name="compare" /> compared with</span>}
          </div>
        ))}
      </div>
      {swapped && <p className="cmp-swap">Checkpoints were ordered chronologically: A is always the earlier one.</p>}

      {same ? (
        <div className="cmp-empty">Choose two different checkpoints to compare.</div>
      ) : (
        <div className="cmp-body">
          <section className="cmp-main">
            <div className="cmp-frontier">
              <div>
                <small>Recorded frontier at {A.short}</small>
                {A.frontier === null ? <NotRecorded cp={A} /> : A.frontier.length ? A.frontier.map((f) => <b key={f}>{f}</b>) : <b>None</b>}
              </div>
              <Icon name="arrow" />
              <div>
                <small>Recorded frontier at {B.short}</small>
                {B.frontier === null ? <NotRecorded cp={B} /> : B.frontier.length ? B.frontier.map((f) => <b key={f} className={A.frontier?.includes(f) ? "" : "new"}>{f}</b>) : <b>None</b>}
              </div>
            </div>
            <div className="cmp-status">
              <span>
                Status: <b>{A.status}</b> → <b>{B.status}</b>
              </span>
            </div>

            <div className="cmp-grid">
              <article>
                <span className="change-icon new"><Icon name="plus" /></span>
                <div>
                  <small>Additional evidence</small>
                  <h3>{newDocs.length} new sources</h3>
                  {newDocs.map((d) => (
                    <Item key={d.id} n={d}>
                      <em className={`ix-origin inline o-${d.origin}`}>{d.origin?.[0].toUpperCase()}</em>
                    </Item>
                  ))}
                </div>
              </article>
              <article>
                <span className="change-icon relation"><Icon name="branch" /></span>
                <div>
                  <small>New or revised relationships</small>
                  {limited ? (
                    <NotRecorded cp={!A.recordsClaims ? A : B} />
                  ) : (
                    <>
                      <h3>{newClaims.length} new · {revised.length} revised</h3>
                      {newClaims.map((c) => <Item key={c.id} n={c} />)}
                      {revised.map((c) => (
                        <Item key={c.id} n={c}>
                          <span className="cmp-rev">
                            <Tag tone={CLAIM_TONE[nodeStatus(c, A.seq)!.status]}>{CLAIM_LABEL[nodeStatus(c, A.seq)!.status]}</Tag> →{" "}
                            <Tag tone={CLAIM_TONE[nodeStatus(c, B.seq)!.status]}>{CLAIM_LABEL[nodeStatus(c, B.seq)!.status]}</Tag>
                          </span>
                        </Item>
                      ))}
                    </>
                  )}
                </div>
              </article>
              <article>
                <span className="change-icon conflict"><Icon name="alert" /></span>
                <div>
                  <small>New contradictions</small>
                  {limited ? <NotRecorded cp={!A.recordsClaims ? A : B} /> : (
                    <>
                      <h3>{newContras.length} new</h3>
                      {newContras.map((c) => <Item key={c.id} n={c} />)}
                    </>
                  )}
                </div>
              </article>
              <article>
                <span className="change-icon open"><Icon name="search" /></span>
                <div>
                  <small>Questions resolved or still open</small>
                  {limited ? <NotRecorded cp={!A.recordsClaims ? A : B} /> : (
                    <>
                      <h3>{questions.length} questions tracked</h3>
                      {questions.map((qn) => {
                        const st = qState(qn);
                        return (
                          <Item key={qn.id} n={qn}>
                            <span className={`cmp-q ${st.kind}`}>{st.label}{st.at && st.at !== st.bt ? `: ${CLAIM_LABEL[st.at]} → ${CLAIM_LABEL[st.bt]}` : ""}</span>
                          </Item>
                        );
                      })}
                    </>
                  )}
                </div>
              </article>
            </div>
            <p className="cmp-footnote">
              Differences are computed only from what each checkpoint persisted. Nothing between checkpoints is inferred.
            </p>
          </section>

          <aside className="cmp-map">
            <h3>Where the changes happened</h3>
            <div className="cmp-map-legend">
              <span><i className="before" />Known at {A.short}</span>
              <span><i className="after" />Added by {B.short}</span>
              <span><i className="revised" />Revised</span>
            </div>
            <div className="cmp-map-scroll">
              <svg width={W} height={H}>
                {ids.map((id) => {
                  const box = layout.pos[id];
                  const n = trace.nodes.find((x) => x.id === id)!;
                  return (
                    <rect
                      key={id}
                      className={`cmp-r ${changeClass(id)} k-${n.kind}`}
                      x={(box.x - minX) * s + 10}
                      y={(box.y - minY) * s + 10}
                      width={Math.max(3, box.w * s)}
                      height={Math.max(3, box.h * s)}
                      rx={n.kind === "checkpoint" ? 1 : 3}
                      onClick={() => onShow(id, B.id)}
                    >
                      <title>{n.label}</title>
                    </rect>
                  );
                })}
                {[A, B].map((cp) => {
                  const box = layout.pos[cp.nodeId];
                  return box ? (
                    <text key={cp.id} x={(box.x + box.w - minX) * s + 16} y={(box.y + box.h / 2 - minY) * s + 13} className="cmp-cp-label">
                      {cp.short}
                    </text>
                  ) : null;
                })}
              </svg>
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}
