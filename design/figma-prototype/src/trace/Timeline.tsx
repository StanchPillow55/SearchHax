import { Icon } from "../shared";
import type { Trace } from "./types";

const KIND_CLASS: Record<string, string> = {
  intent: "agent",
  inherit: "agent",
  plan: "agent",
  search: "agent",
  retrieve: "agent",
  extract: "agent",
  evaluate: "evidence",
  relate: "evidence",
  question: "question",
  decide: "decision",
  checkpoint: "checkpoint",
  pending: "pending",
};

export function Timeline({
  trace,
  cursor,
  latest,
  playing,
  granularity,
  snapshot,
  follow,
  setFollow,
  onPlay,
  onStep,
  onSeek,
  onGranularity,
  onCheckpoint,
}: {
  trace: Trace;
  cursor: number;
  latest: number;
  playing: boolean;
  granularity: "event" | "round";
  snapshot: string | null;
  follow: boolean;
  setFollow: (v: boolean) => void;
  onPlay: () => void;
  onStep: (d: 1 | -1) => void;
  onSeek: (s: number) => void;
  onGranularity: (g: "event" | "round") => void;
  onCheckpoint: (id: string) => void;
}) {
  const events = trace.events.slice(0, latest + 1);
  const n = Math.max(1, events.length - 1);
  const pct = (seq: number) => `${(seq / n) * 100}%`;
  const ev = events[cursor];
  const rounds = trace.rounds
    .map((r) => {
      const inR = events.filter((e) => e.round === r.n);
      return inR.length ? { ...r, start: inR[0].seq, end: inR[inR.length - 1].seq } : null;
    })
    .filter(Boolean) as { n: number; title: string; start: number; end: number }[];
  const checkpoints = trace.checkpoints.filter((c) => c.seq <= latest);
  const nextCp = checkpoints.find((c) => c.seq > cursor);
  const prevCp = [...checkpoints].reverse().find((c) => c.seq < cursor);

  return (
    <div className="ix-timeline">
      <div className="ix-tl-controls">
        <button onClick={() => onSeek(0)} title="Start of investigation">
          <Icon name="skipStart" size={14} />
        </button>
        <button onClick={() => onStep(-1)} disabled={cursor <= 0} title={granularity === "event" ? "Previous event" : "Previous round milestone"}>
          <Icon name="prev" size={15} />
        </button>
        <button className="play" onClick={onPlay} title={playing ? "Pause" : "Play recorded history"}>
          <Icon name={playing ? "pause" : "play"} size={15} />
        </button>
        <button onClick={() => onStep(1)} disabled={cursor >= latest} title={granularity === "event" ? "Next event" : "Next round milestone"}>
          <Icon name="next" size={15} />
        </button>
        <button onClick={() => onSeek(latest)} disabled={cursor >= latest} title="Return to latest state">
          <Icon name="skipEnd" size={14} />
        </button>
        <div className="ix-gran">
          <button className={granularity === "event" ? "active" : ""} onClick={() => onGranularity("event")}>
            Events
          </button>
          <button className={granularity === "round" ? "active" : ""} onClick={() => onGranularity("round")}>
            Milestones
          </button>
        </div>
      </div>

      <div className="ix-tl-main">
        <div className="ix-tl-now">
          <span className={`ix-tl-kind ${KIND_CLASS[ev?.kind ?? "plan"]}`}>{ev?.kind === "decide" ? "decision" : ev?.kind}</span>
          <b>
            Event {cursor + 1} / {latest + 1} · {ev?.label}
          </b>
          <span>{ev?.detail}</span>
        </div>
        <div className="ix-tl-track">
          {rounds.map((r) => (
            <div key={r.n} className="ix-tl-round" style={{ left: pct(r.start), width: `calc(${pct(r.end)} - ${pct(r.start)})` }}>
              <span>
                Round {r.n} · {r.title}
              </span>
            </div>
          ))}
          <div className="ix-tl-rail">
            <div className="ix-tl-progress" style={{ width: pct(cursor) }} />
          </div>
          {events.map((e) => (
            <button
              key={e.seq}
              className={`ix-tl-tick ${KIND_CLASS[e.kind]} ${e.seq <= cursor ? "reached" : ""} ${e.seq === cursor ? "current" : ""}`}
              style={{ left: pct(e.seq) }}
              title={`${e.seq + 1}. ${e.label}`}
              onClick={() => (e.kind === "checkpoint" ? onCheckpoint(trace.checkpoints.find((c) => c.seq === e.seq)!.id) : onSeek(e.seq))}
            >
              {e.kind === "checkpoint" ? (
                <span className={`ix-tl-gem ${trace.checkpoints.find((c) => c.seq === e.seq)?.resumable ? "" : "viewonly"} ${snapshot && trace.checkpoints.find((c) => c.id === snapshot)?.seq === e.seq ? "loaded" : ""}`}>
                  <em>{trace.checkpoints.find((c) => c.seq === e.seq)?.short}</em>
                </span>
              ) : e.kind === "decide" ? (
                <span className="ix-tl-decision" />
              ) : (
                <i />
              )}
            </button>
          ))}
          <input
            className="ix-tl-scrub"
            type="range"
            min={0}
            max={latest}
            value={cursor}
            onChange={(e) => onSeek(Number(e.target.value))}
            aria-label="Investigation timeline scrubber"
          />
        </div>
      </div>

      <div className="ix-tl-side">
        <label className="ix-follow">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow playback
        </label>
        <div className="ix-tl-jumps">
          <button disabled={!prevCp} onClick={() => prevCp && onCheckpoint(prevCp.id)}>
            <span className="tiny-gem" /> {prevCp ? `← ${prevCp.short}` : "No earlier"}
          </button>
          <button disabled={!nextCp} onClick={() => nextCp && onCheckpoint(nextCp.id)}>
            <span className="tiny-gem" /> {nextCp ? `${nextCp.short} →` : "No later"}
          </button>
        </div>
        <button className="ix-latest" disabled={cursor >= latest && !snapshot} onClick={() => onSeek(latest)}>
          Return to latest <Icon name="arrow" size={13} />
        </button>
      </div>
    </div>
  );
}
