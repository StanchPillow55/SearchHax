import { useEffect, useMemo, useRef, useState } from "react";
import {
  Icon,
  InfoBlock,
  Tag,
  childEvidence,
  parentEvidence,
  projectEvidence,
  type EvidencePoint,
} from "./shared";
import { CheckpointCompare } from "./trace/CheckpointCompare";
import { ConstellationView } from "./trace/Constellation";
import { DemoGuide, type DemoStep } from "./trace/DemoGuide";
import { INITIAL_LANTERNS, TRACES, forkTrace } from "./trace/data";
import { revealPath } from "./trace/graph";
import { Interior, defaultView, type ViewPatch } from "./trace/Interior";
import type { ComposerDraft, Lantern, Trace, ViewState } from "./trace/types";
import "./trace/trace.css";
import "./persisted/persisted.css";
import { PersistedWorkspace } from "./persisted/PersistedWorkspace";
import { readRecent, readUrlState, writeUrlState, type AppMode } from "./persisted/urlState";

type Screen =
  | "home"
  | "active"
  | "results"
  | "constellation"
  | "interior"
  | "checkpointCompare"
  | "knowledge"
  | "space"
  | "compare";
type Inspector = "claim" | "checkpoint" | "lantern" | "unknown";

const question =
  "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?";

function Sidebar({
  screen,
  setScreen,
  collapsed,
  setCollapsed,
  mode,
  onMode,
  recentVersion,
}: {
  screen: Screen;
  setScreen: (s: Screen) => void;
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  mode: AppMode;
  onMode: (m: AppMode) => void;
  recentVersion: number;
}) {
  void recentVersion;
  const live = mode === "live";
  const liveRecent = live ? readRecent().slice(0, 4) : [];
  const nav = [
    ["home", "home", "Research home"],
    ["constellation", "lantern", "Saved Lanterns"],
    ["knowledge", "knowledge", "Personal knowledge"],
    ["results", "search", "Search & history"],
  ] as const;
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <button className="brand" onClick={() => setScreen("home")} aria-label="SearchHax home">
        <span className="brandmark">
          <span />
          <span />
        </span>
        {!collapsed && (
          <strong>
            Search<span>Hax</span>
          </strong>
        )}
      </button>
      <div className={`mode-switch ${collapsed ? "collapsed" : ""}`} role="group" aria-label="Data mode">
        <button className={live ? "active live" : ""} onClick={() => onMode("live")} title="Persisted investigations from the exploration API (read-only)" data-testid="mode-live">
          <i />
          {!collapsed && "Live data"}
        </button>
        <button className={!live ? "active demo" : ""} onClick={() => onMode("demo")} title="Simulated prototype data" data-testid="mode-demo">
          <i />
          {!collapsed && "Demo"}
        </button>
      </div>
      <button
        className="new-button"
        onClick={() => setScreen("home")}
        disabled={live}
        title={live ? "Starting investigations is not part of the read-only integration" : undefined}
      >
        <Icon name="plus" />
        {!collapsed && <span>New investigation</span>}
      </button>
      <nav>
        <p className="nav-label">{!collapsed && "Workspace"}</p>
        {live ? (
          <button className="active" onClick={() => {
              writeUrlState({ mode: "live", investigation: null, node: null, checkpoint: null }, { push: true });
              window.dispatchEvent(new PopStateEvent("popstate"));
            }} title="Stored investigations">
            <Icon name="lantern" />
            {!collapsed && <span>Investigations</span>}
          </button>
        ) : (
          nav.map(([id, icon, label]) => (
            <button
              key={id}
              className={screen === id ? "active" : ""}
              onClick={() => setScreen(id)}
              title={label}
            >
              <Icon name={icon} />
              {!collapsed && <span>{label}</span>}
            </button>
          ))
        )}
      </nav>
      {!collapsed && live && (
        <div className="recent">
          <p className="nav-label">Recently opened</p>
          {liveRecent.length === 0 && <small className="recent-empty">None yet</small>}
          {liveRecent.map((r) => (
            <button
              key={r.id}
              onClick={() => {
                writeUrlState({ mode: "live", investigation: r.id, node: null, checkpoint: null }, { push: true });
                window.dispatchEvent(new PopStateEvent("popstate"));
              }}
            >
              <i className="status-dot teal" />
              <span>
                <b>{r.question || r.id}</b>
                <small>{r.id}</small>
              </span>
            </button>
          ))}
        </div>
      )}
      {!collapsed && !live && (
        <div className="recent">
          <p className="nav-label">Recent investigations · demo</p>
          <button onClick={() => setScreen("results")}>
            <i className="status-dot amber" />
            <span>
              <b>NVIDIA capacity loop</b>
              <small>Stopped with uncertainty</small>
            </span>
          </button>
          <button onClick={() => setScreen("constellation")}>
            <i className="status-dot violet" />
            <span>
              <b>Power constraints</b>
              <small>Child Lantern · active</small>
            </span>
          </button>
          <button>
            <i className="status-dot teal" />
            <span>
              <b>AI chip demand</b>
              <small>Completed · 3 days ago</small>
            </span>
          </button>
        </div>
      )}
      <div className="sidebar-bottom">
        <button>
          <Icon name="settings" />
          {!collapsed && <span>Settings</span>}
        </button>
        <button className="collapse" onClick={() => setCollapsed(!collapsed)}>
          <Icon name="chevron" />
          {!collapsed && <span>Collapse</span>}
        </button>
        {!collapsed && (
          <div className="profile">
            <span>AK</span>
            <div>
              <b>Alex Kim</b>
              <small>Researcher plan</small>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function Home({ start }: { start: () => void }) {
  const [input, setInput] = useState(question);
  return (
    <main className="home-screen">
      <div className="home-orbit orbit-one" />
      <div className="home-orbit orbit-two" />
      <header className="home-top">
        <span>
          <Icon name="spark" size={15} /> Prototype research environment
        </span>
        <button>How SearchHax works</button>
      </header>
      <section className="home-hero">
        <div className="hero-lantern" aria-hidden="true">
          <span className="beam b1" />
          <span className="beam b2" />
          <span className="beam b3" />
          <span className="glow" />
          <i className="cap top" />
          <i className="cap bottom" />
        </div>
        <div className="eyebrow">Navigate what’s known. Illuminate what isn’t.</div>
        <h1>
          Where questions become
          <br />
          <em>living research.</em>
        </h1>
        <p>
          Explore evidence, understand uncertainty, and branch into the questions that
          matter—without losing the path that brought you there.
        </p>
        <div className="research-input">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-label="Research question"
          />
          <div className="input-footer">
            <span>
              <Icon name="spark" size={16} /> Deep exploration <b>·</b> 24 source budget
            </span>
            <button onClick={start} disabled={!input.trim()}>
              Begin research <Icon name="arrow" size={17} />
            </button>
          </div>
        </div>
        <small className="prototype-note">
          Simulated prototype · No live sources or credits will be used
        </small>
      </section>
      <section className="home-grid">
        <div className="section-heading">
          <div>
            <span>Continue exploring</span>
            <h2>Your research, still growing</h2>
          </div>
          <button>
            View all <Icon name="arrow" size={15} />
          </button>
        </div>
        <div className="recent-cards">
          <button className="recent-card featured" onClick={start}>
            <div className="mini-lantern">
              <i />
              <i />
              <i />
            </div>
            <div>
              <Tag tone="amber">Stopped with uncertainty</Tag>
              <h3>NVIDIA’s infrastructure investment loop</h3>
              <p>14 claims · 23 sources · 3 open questions</p>
            </div>
            <Icon name="arrow" />
          </button>
          <button className="recent-card">
            <Tag tone="teal">Evidence sufficient</Tag>
            <h3>How inference economics differ from training</h3>
            <p>9 claims · 16 sources</p>
            <div className="card-bottom">
              <span>Updated yesterday</span>
              <Icon name="arrow" />
            </div>
          </button>
          <button className="recent-card">
            <Tag tone="violet">Active branch</Tag>
            <h3>Grid constraints on new data centers</h3>
            <p>6 claims · 11 sources</p>
            <div className="card-bottom">
              <span>Researching now</span>
              <Icon name="arrow" />
            </div>
          </button>
        </div>
        <div className="direction-row">
          <div>
            <span className="direction-icon">
              <Icon name="knowledge" />
            </span>
            <p>
              <b>From your knowledge frontier</b>
              <br />
              Suggested directions based on topics you’ve encountered but not yet explored.
            </p>
          </div>
          <button>How does power availability shape AI capacity?</button>
          <button>Who carries the financing risk in GPU clouds?</button>
        </div>
      </section>
    </main>
  );
}

function Topbar({ status, onBack, title, statusLabel }: { status: "active" | "stopped"; onBack?: () => void; title?: string; statusLabel?: React.ReactNode }) {
  return (
    <header className="topbar">
      <div className="question-title">
        {onBack && (
          <button className="icon-button" onClick={onBack}>
            <Icon name="back" />
          </button>
        )}
        <div>
          <small>Active research question</small>
          <h1>{title ?? question}</h1>
        </div>
      </div>
      <div className="top-actions">
        {statusLabel ? statusLabel : status === "active" ? (
          <Tag tone="blue">Researching now</Tag>
        ) : (
          <Tag tone="amber">Stopped with uncertainty</Tag>
        )}
        <button className="outline-button">
          <Icon name="source" size={16} /> Sources
        </button>
        <button className="icon-button">
          <span className="more">•••</span>
        </button>
      </div>
    </header>
  );
}

function Active({ finish }: { finish: () => void }) {
  const [paused, setPaused] = useState(false);
  const [progress, setProgress] = useState(64);
  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => setProgress((p) => (p >= 78 ? 46 : p + 1)), 900);
    return () => clearInterval(t);
  }, [paused]);
  return (
    <main className="app-main active-screen">
      <Topbar status="active" />
      <div className="active-layout">
        <section className="activity-panel">
          <div className="activity-head">
            <div>
              <span className="pulse" />
              <div>
                <small>Current objective</small>
                <h2>Tracing the capacity–financing feedback loop</h2>
              </div>
            </div>
            <button className="icon-button" onClick={() => setPaused(!paused)}>
              <Icon name={paused ? "play" : "pause"} />
            </button>
          </div>
          <p className="objective">
            Testing whether infrastructure financing expands GPU demand, or mostly shifts risk
            between NVIDIA, cloud providers, and their customers.
          </p>
          <div className="budget">
            <div>
              <span>Research progress</span>
              <b>{progress}%</b>
            </div>
            <div className="progress">
              <i style={{ width: `${progress}%` }} />
            </div>
            <small>
              16 of 24 sources evaluated <span>·</span> 2 exploration paths active
            </small>
          </div>
          <div className="activity-stream">
            <h3>
              Live activity <span>Simulated</span>
            </h3>
            <article className="activity current">
              <span className="activity-symbol">
                <Icon name="search" />
              </span>
              <div>
                <b>Evaluating financing relationships</b>
                <p>Comparing CoreWeave filings with lender and infrastructure disclosures</p>
                <small>
                  <i /> In progress · Why this matters: tests who carries expansion risk
                </small>
              </div>
            </article>
            <article className="activity">
              <span className="activity-symbol teal-bg">
                <Icon name="source" />
              </span>
              <div>
                <b>New evidence connected</b>
                <p>
                  Long-term customer commitments can support data-center financing, but introduce
                  concentration risk.
                </p>
                <small>SEC filing · Source reviewed</small>
              </div>
            </article>
            <article className="activity">
              <span className="activity-symbol violet-bg">
                <Icon name="branch" />
              </span>
              <div>
                <b>Relationship emerging</b>
                <p>GPU supply commitments and customer contracts appear mutually reinforcing.</p>
                <small>Supported by 3 independent sources</small>
              </div>
            </article>
            <article className="activity dim">
              <span className="activity-symbol">
                <Icon name="search" />
              </span>
              <div>
                <b>Next: test energy constraint</b>
                <p>Look for evidence that power availability limits deployed capacity.</p>
              </div>
            </article>
          </div>
          <button className="finish-demo" onClick={finish}>
            Skip to completed research state <Icon name="arrow" />
          </button>
        </section>
        <section className="active-canvas">
          <div className="canvas-label">
            <div>
              <span>Lantern forming</span>
              <small>Evidence reorganizes as research develops</small>
            </div>
            <div>
              <button>
                <Icon name="zoom" />
              </button>
              <button>Fit</button>
            </div>
          </div>
          <LanternGraph variant="active" onSelect={() => {}} />
          <div className="canvas-legend">
            <span>
              <i className="blue" />
              Exploration
            </span>
            <span>
              <i className="teal" />
              Evidence
            </span>
            <span>
              <i className="amber" />
              Checkpoint
            </span>
          </div>
        </section>
      </div>
    </main>
  );
}

function LanternGraph({
  variant,
  selected,
  onSelect,
  child,
}: {
  variant: "active" | "result" | "constellation";
  selected?: string;
  onSelect: (id: string, type?: Inspector) => void;
  child?: boolean;
}) {
  if (variant === "constellation") return null;
  return (
    <div className={`lantern-graph ${variant} ${child ? "child-view" : ""}`}>
      <svg className="connections" viewBox="0 0 800 620" preserveAspectRatio="none">
        <defs>
          <linearGradient id="line" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#6d8eff" />
            <stop offset=".55" stopColor="#4cc9b0" />
            <stop offset="1" stopColor="#e7ad5e" />
          </linearGradient>
        </defs>
        <path
          className="trunk"
          d="M400 75 C400 115 310 120 250 185 M400 75C400 120 490 120 550 185 M400 75C400 138 400 145 400 205"
        />
        <path d="M250 205C280 270 320 295 365 325M550 205C520 270 480 295 435 325M400 225V325" />
        <path d="M365 345C330 390 305 405 280 440M435 345C475 390 500 405 520 440M400 345V465" />
        <path
          className="final-path"
          d="M280 458C310 500 350 505 400 520M520 458C490 500 450 505 400 520M400 480v40"
        />
      </svg>
      <button className="intent-node" onClick={() => onSelect("intent", "lantern")}>
        <small>Research intent</small>
        <b>
          {child ? "Are energy constraints the true bottleneck?" : "Map the capacity feedback loop"}
        </b>
      </button>
      <button className="evidence-node n1" onClick={() => onSelect("gpu", "claim")}>
        <span>GPU supply</span>
        <small>4 sources</small>
      </button>
      <button
        className={`evidence-node n2 ${selected === "claim" ? "selected" : ""}`}
        onClick={() => onSelect("claim", "claim")}
      >
        <span>
          Customer commitments
          <br />
          enable financing
        </span>
        <small>5 sources · mixed</small>
      </button>
      <button className="evidence-node n3" onClick={() => onSelect("demand", "claim")}>
        <span>AI demand</span>
        <small>3 sources</small>
      </button>
      <button className="claim-pill p1" onClick={() => onSelect("contracts", "claim")}>
        Long-term contracts
      </button>
      <button className="claim-pill p2" onClick={() => onSelect("risk", "claim")}>
        Concentration risk
      </button>
      <button className="claim-pill p3" onClick={() => onSelect("expansion", "claim")}>
        Data-center expansion
      </button>
      <button className="claim-pill p4 uncertain" onClick={() => onSelect("energy", "unknown")}>
        <Icon name="alert" size={14} /> Energy constraint unclear
      </button>
      <button className="converge-node" onClick={() => onSelect("checkpoint", "checkpoint")}>
        <span className="diamond" />
        <div>
          <small>Convergence checkpoint</small>
          <b>Reinforcing loop supported, but risk transfer is unresolved</b>
        </div>
      </button>
      {variant === "active" ? (
        <div className="searching-node">
          <span />
          <b>Evaluating financing disclosures</b>
        </div>
      ) : (
        <button className="branch-node" onClick={() => onSelect("energy", "unknown")}>
          <Icon name="branch" size={17} />
          <div>
            <small>Open question</small>
            <b>Does energy availability cap the loop?</b>
          </div>
        </button>
      )}
    </div>
  );
}

function Findings({ onClaim, onUnknown }: { onClaim: () => void; onUnknown: () => void }) {
  return (
    <div className="findings">
      <div className="summary-card">
        <div className="summary-top">
          <Tag tone="teal">What we found</Tag>
          <span>Illustrative prototype synthesis</span>
        </div>
        <h2>
          A reinforcing loop exists—but it depends on concentrated customers and infrastructure
          financing.
        </h2>
        <p>
          NVIDIA’s GPU supply and investments can help specialist cloud providers expand capacity.
          Their long-term customer commitments may support financing for more infrastructure, which
          in turn creates demand for additional GPUs.
        </p>
        <div className="summary-metrics">
          <span>
            <b>5</b> supported claims
          </span>
          <span>
            <b>2</b> disputed relationships
          </span>
          <span>
            <b>3</b> open questions
          </span>
        </div>
      </div>
      <div className="finding-section">
        <div className="section-title">
          <h3>Evidence-backed findings</h3>
          <button>View all 5</button>
        </div>
        <button className="finding-card" onClick={onClaim}>
          <span className="finding-icon">
            <Icon name="check" />
          </span>
          <div>
            <h4>Customer commitments can make infrastructure expansion financeable</h4>
            <p>
              Long-term contracts signal future revenue, helping GPU cloud providers raise debt for
              data-center expansion.
            </p>
            <small>
              <b>Strong support</b> · 5 sources · 3 independent
            </small>
          </div>
          <Icon name="chevron" />
        </button>
        <button className="finding-card" onClick={onClaim}>
          <span className="finding-icon">
            <Icon name="check" />
          </span>
          <div>
            <h4>NVIDIA benefits twice from capacity expansion</h4>
            <p>
              Provider growth expands its customer base while increasing demand for GPU systems.
            </p>
            <small>
              <b>Moderate support</b> · 4 sources
            </small>
          </div>
          <Icon name="chevron" />
        </button>
      </div>
      <div className="finding-section uncertain-section">
        <div className="section-title">
          <h3>What remains uncertain</h3>
          <span>Needs further research</span>
        </div>
        <button className="uncertain-card" onClick={onUnknown}>
          <Icon name="alert" />
          <div>
            <b>Power availability may constrain capacity more than GPU supply</b>
            <p>Evidence is regional and does not establish the scale of the constraint.</p>
          </div>
          <span>
            Investigate <Icon name="arrow" />
          </span>
        </button>
        <button className="uncertain-card" onClick={onClaim}>
          <Icon name="alert" />
          <div>
            <b>Risk may be transferred rather than reduced</b>
            <p>It is unclear how much demand risk ultimately remains with providers and lenders.</p>
          </div>
          <span>
            Inspect <Icon name="arrow" />
          </span>
        </button>
      </div>
      <div className="stop-card">
        <span>
          <Icon name="lantern" />
        </span>
        <div>
          <small>Why research stopped</small>
          <b>
            Strong support for the core loop; insufficient independent evidence on who ultimately
            carries financial risk.
          </b>
          <p>
            The remaining budget was unlikely to resolve this without more targeted filings or user
            direction.
          </p>
        </div>
        <button>Resume research</button>
      </div>
    </div>
  );
}

function InspectorPanel({
  type,
  close,
  fork,
  saved,
  setSaved,
  evidence,
}: {
  type: Inspector;
  close: () => void;
  fork: () => void;
  saved: boolean;
  setSaved: (v: boolean) => void;
  evidence?: EvidencePoint | null;
}) {
  if (type === "checkpoint")
    return (
      <aside className="inspector">
        <InspectorHead
          label="Convergence checkpoint"
          title="Capacity loop established"
          close={close}
        />
        <div className="inspector-scroll">
          <div className="checkpoint-hero">
            <span className="large-diamond" />
            <Tag tone="amber">Stopped with uncertainty</Tag>
            <h3>
              Enough evidence to support the core relationship—not enough to resolve where risk
              accumulates.
            </h3>
          </div>
          <InfoBlock label="What had been discovered">
            <p>
              GPU access, customer commitments, and infrastructure financing appear to reinforce one
              another across multiple sources.
            </p>
          </InfoBlock>
          <InfoBlock label="Why research stopped">
            <p>
              Further broad search produced derivative reporting rather than new independent
              evidence.
            </p>
          </InfoBlock>
          <InfoBlock label="Remaining uncertainty">
            <ul>
              <li>Who holds downside demand risk?</li>
              <li>How binding are energy constraints?</li>
            </ul>
          </InfoBlock>
        </div>
        <div className="inspector-actions">
          <button className="primary" onClick={fork}>
            <Icon name="branch" /> Fork from checkpoint
          </button>
          <button>Resume parent research</button>
        </div>
      </aside>
    );
  if (type === "lantern")
    return (
      <aside className="inspector">
        <InspectorHead label="Child Lantern" title="Power constraints on expansion" close={close} />
        <div className="inspector-scroll">
          <Tag tone="violet">Active investigation</Tag>
          <InfoBlock label="Branch objective">
            <p>
              Determine whether energy availability is a more binding constraint on AI capacity than
              GPU supply.
            </p>
          </InfoBlock>
          <InfoBlock label="Parent investigation">
            <p>{question}</p>
          </InfoBlock>
          <InfoBlock label="New findings">
            <p>
              Interconnection queues and local power delivery timelines vary substantially by
              market.
            </p>
          </InfoBlock>
          <div className="difference">
            <Icon name="spark" />
            <div>
              <b>Different from parent</b>
              <p>
                This branch narrows the question from financing dynamics to physical deployment
                limits.
              </p>
            </div>
          </div>
        </div>
        <div className="inspector-actions">
          <button className="primary">
            Open this Lantern <Icon name="arrow" />
          </button>
          <button>Compare with parent</button>
        </div>
      </aside>
    );
  return (
    <aside className="inspector">
      <InspectorHead
        label={type === "unknown" ? "Unresolved question" : "Selected claim"}
        title={
          type === "unknown"
            ? "Does power availability cap expansion?"
            : (evidence?.title ?? "Customer commitments can enable infrastructure financing")
        }
        close={close}
      />
      <div className="inspector-scroll">
        <div className="claim-context">
          <small>In context of</small>
          <p>{question}</p>
        </div>
        {type === "claim" && (
          <>
            <div className="support-row">
              <Tag tone="teal">Supported by 5 sources</Tag>
              <span>3 independent</span>
            </div>
            <blockquote>
              “
              {evidence?.summary ??
                "Contracted customer demand and committed capacity may support access to capital, while increasing exposure to a small number of counterparties."}
              ”
            </blockquote>
            <div className="source-card">
              <span className="source-logo">F</span>
              <div>
                <b>{evidence?.source ?? "Infrastructure financing disclosure"}</b>
                <p>Recorded passage · Illustrative prototype source</p>
              </div>
              <Icon name="arrow" />
            </div>
            <InfoBlock label="Why this evidence matters">
              <p>
                It links future customer revenue to the ability to finance additional GPU
                infrastructure, but does not prove that financing risk is reduced.
              </p>
            </InfoBlock>
            <InfoBlock label="Provenance & limitations">
              <ul>
                <li>Primary company disclosure</li>
                <li>Self-reported projections</li>
                <li>Independent confirmation is limited</li>
              </ul>
            </InfoBlock>
          </>
        )}
        <div className="challenge-box">
          <span>
            <Icon name="branch" />
          </span>
          <div>
            <b>
              {type === "unknown" ? "Investigate this question" : "Challenge or extend this claim"}
            </b>
            <p>
              Your prompt will stay attached to this{" "}
              {type === "unknown" ? "open question" : "claim"} and its parent research.
            </p>
          </div>
          <textarea
            defaultValue={
              type === "unknown"
                ? "Is energy availability the true bottleneck for AI capacity expansion?"
                : "Is this true? Find independent evidence that does not rely on company disclosures."
            }
          />
          <div className="context-chain">
            <span>Original question</span>
            <Icon name="chevron" size={13} />
            <span>Selected {type === "unknown" ? "question" : "claim"}</span>
            <Icon name="chevron" size={13} />
            <b>Branch prompt</b>
          </div>
        </div>
      </div>
      <div className="inspector-actions split">
        <button className={saved ? "saved" : ""} onClick={() => setSaved(true)}>
          <Icon name={saved ? "check" : "lantern"} />
          {saved ? "Lantern saved" : "Save Lantern"}
        </button>
        <button className="primary" onClick={fork}>
          <Icon name="branch" /> Fork & investigate
        </button>
        <small>
          Fork & investigate starts simulated research and may consume credits in the production
          product.
        </small>
      </div>
    </aside>
  );
}

function InspectorHead({
  label,
  title,
  close,
}: {
  label: string;
  title: string;
  close: () => void;
}) {
  return (
    <div className="inspector-head">
      <div>
        <small>{label}</small>
        <h2>{title}</h2>
      </div>
      <button className="icon-button" onClick={close}>
        <Icon name="close" />
      </button>
    </div>
  );
}
function Results({
  initialMode = "findings",
  initialInspector = null,
  initialEvidence = null,
  goCompare,
  goSpace,
}: {
  initialMode?: "findings" | "lantern";
  initialInspector?: Inspector | null;
  initialEvidence?: EvidencePoint | null;
  goCompare: () => void;
  goSpace: () => void;
}) {
  const [mode, setMode] = useState<"findings" | "lantern">(initialMode);
  const [inspector, setInspector] = useState<Inspector | null>(
    initialInspector ?? (initialMode === "lantern" ? "checkpoint" : null),
  );
  const [saved, setSaved] = useState(false);
  const [forked, setForked] = useState(false);
  const [inspectedEvidence, setInspectedEvidence] = useState<EvidencePoint | null>(initialEvidence);
  const open = (id: string, type: Inspector = "claim") => {
    setInspectedEvidence(null);
    setInspector(type);
  };
  return (
    <main className="app-main results-screen">
      <Topbar status="stopped" />
      <div className="workspace-tabs">
        <div>
          <button
            className={mode === "findings" ? "active" : ""}
            onClick={() => setMode("findings")}
          >
            Findings
          </button>
          <button className={mode === "lantern" ? "active" : ""} onClick={() => setMode("lantern")}>
            Lantern map <span>9</span>
          </button>
        </div>
        <div>
          <button onClick={goSpace}>
            <Icon name="cube" /> 3D evidence
          </button>
          <button onClick={goCompare}>
            <Icon name="compare" /> Compare
          </button>
        </div>
      </div>
      <div className={`results-body ${inspector ? "with-inspector" : ""}`}>
        <section className="results-content">
          {mode === "findings" ? (
            <Findings
              onClaim={() => {
                setInspectedEvidence(null);
                setInspector("claim");
              }}
              onUnknown={() => {
                setInspectedEvidence(null);
                setInspector("unknown");
              }}
            />
          ) : (
            <div className="map-wrap">
              <div className="map-toolbar">
                <div>
                  <Tag tone="blue">Parent Lantern</Tag>
                  <span>23 sources · 9 connected objects</span>
                </div>
                <div>
                  <button>
                    <Icon name="zoom" />
                  </button>
                  <button>100%</button>
                  <button>Fit view</button>
                </div>
              </div>
              <div className="parent-preserved">
                <Icon name="lantern" size={14} />
                <span>
                  <b>Original preserved</b>
                  Child Lanterns inherit this checkpoint without rewriting the parent.
                </span>
              </div>
              <LanternGraph
                variant="result"
                selected={inspector === "claim" ? "claim" : ""}
                onSelect={open}
              />
              <div className="canvas-help">
                Drag to pan · Scroll to zoom · Select any object to inspect
              </div>
            </div>
          )}
        </section>
        {inspector && (
          <InspectorPanel
            type={inspector}
            close={() => setInspector(null)}
            fork={() => {
              setForked(true);
              setInspector("lantern");
              setMode("lantern");
            }}
            saved={saved}
            setSaved={setSaved}
            evidence={inspectedEvidence}
          />
        )}
      </div>
      {forked && (
        <div className="toast">
          <span>
            <Icon name="check" />
          </span>
          <div>
            <b>Child Lantern created</b>
            <p>“Power constraints on expansion” is ready and researching in this prototype.</p>
          </div>
          <button onClick={() => setForked(false)}>
            <Icon name="close" />
          </button>
        </div>
      )}
    </main>
  );
}

const concepts = [
  {
    name: "AI infrastructure",
    type: "interested",
    desc: "Followed across 5 investigations",
    x: 44,
    y: 42,
  },
  { name: "GPU supply", type: "known", desc: "You marked this as familiar", x: 25, y: 62 },
  {
    name: "Project financing",
    type: "encountered",
    desc: "Seen in 3 evidence sources",
    x: 67,
    y: 67,
  },
  { name: "Power interconnection", type: "frontier", desc: "2 unresolved questions", x: 76, y: 28 },
  {
    name: "Demand concentration",
    type: "encountered",
    desc: "Seen in this investigation",
    x: 47,
    y: 78,
  },
];

function Knowledge() {
  const [selected, setSelected] = useState(concepts[3]);
  const [graph, setGraph] = useState(true);
  return (
    <main className="app-main knowledge-screen">
      <header className="simple-header">
        <div>
          <small>Personal knowledge</small>
          <h1>Your evolving research landscape</h1>
          <p>What you care about, what you know, and where your next questions are forming.</p>
        </div>
        <div>
          <button className="outline-button">
            <Icon name="search" /> Search concepts
          </button>
          <button className="primary-button">
            <Icon name="plus" /> Add interest
          </button>
        </div>
      </header>
      <div className="knowledge-summary">
        <div>
          <span className="knowledge-swatch interested" />
          <p>
            <b>Interested</b>
            <small>Topics you want to follow</small>
          </p>
          <strong>12</strong>
        </div>
        <div>
          <span className="knowledge-swatch known" />
          <p>
            <b>Previously known</b>
            <small>Knowledge you confirmed</small>
          </p>
          <strong>8</strong>
        </div>
        <div>
          <span className="knowledge-swatch encountered" />
          <p>
            <b>Encountered</b>
            <small>Seen—not assumed mastered</small>
          </p>
          <strong>34</strong>
        </div>
        <div>
          <span className="knowledge-swatch frontier" />
          <p>
            <b>Knowledge frontier</b>
            <small>Unresolved or unexplored</small>
          </p>
          <strong>7</strong>
        </div>
      </div>
      <div className="knowledge-layout">
        <section className="knowledge-map">
          <div className="knowledge-toolbar">
            <div>
              <button className={graph ? "active" : ""} onClick={() => setGraph(true)}>
                Map
              </button>
              <button className={!graph ? "active" : ""} onClick={() => setGraph(false)}>
                Cards
              </button>
            </div>
            <span>Showing recorded relationships only</span>
          </div>
          {graph ? (
            <div className="concept-map">
              <svg viewBox="0 0 800 520">
                <path d="M350 210 200 320M350 210l185 140M350 210l260-80M200 320l175 80" />
                <path className="dashed" d="M535 350l75-220" />
              </svg>
              {concepts.map((c) => (
                <button
                  key={c.name}
                  className={`concept-node ${c.type} ${selected.name === c.name ? "selected" : ""}`}
                  style={{ left: `${c.x}%`, top: `${c.y}%` }}
                  onClick={() => setSelected(c)}
                >
                  <i />
                  <b>{c.name}</b>
                  <small>{c.desc}</small>
                </button>
              ))}
              <div className="sparse-note">
                <Icon name="knowledge" />
                <span>
                  <b>Connections are intentionally sparse</b>Only relationships recorded through
                  your research are shown.
                </span>
              </div>
            </div>
          ) : (
            <div className="concept-cards">
              {concepts.map((c) => (
                <button onClick={() => setSelected(c)}>
                  <Tag
                    tone={
                      c.type === "frontier"
                        ? "amber"
                        : c.type === "known"
                          ? "green"
                          : c.type === "interested"
                            ? "violet"
                            : "blue"
                    }
                  >
                    {c.type}
                  </Tag>
                  <b>{c.name}</b>
                  <p>{c.desc}</p>
                </button>
              ))}
            </div>
          )}
        </section>
        <aside className="knowledge-inspector">
          <small>Knowledge frontier</small>
          <h2>{selected.name}</h2>
          <Tag tone={selected.type === "frontier" ? "amber" : "blue"}>
            {selected.type === "frontier" ? "Unresolved topic" : selected.type}
          </Tag>
          <InfoBlock label="Why this appears">
            <p>
              {selected.type === "frontier"
                ? "Two investigations raised questions about grid capacity and deployment timelines, but neither resolved them."
                : selected.desc + "."}
            </p>
          </InfoBlock>
          <InfoBlock label="Recorded relationships">
            <div className="relation">
              <span>may constrain</span>
              <b>AI infrastructure</b>
            </div>
          </InfoBlock>
          <div className="knowledge-correction">
            <b>Is this inaccurate?</b>
            <p>SearchHax never assumes encountering a concept means you’ve mastered it.</p>
            <button>Correct knowledge assertion</button>
          </div>
          <button className="primary wide">
            <Icon name="branch" /> Start linked investigation
          </button>
          <button className="secondary wide">Explore related evidence</button>
        </aside>
      </div>
    </main>
  );
}

export interface PersistedSpaceDataset {
  question: string;
  initialCheckpoint?: string;
  checkpoints: { id: string; label: string; points: EvidencePoint[] }[];
}
const PLACEHOLDER_POINT: EvidencePoint = { id: "none", relevance: 0, novelty: 0, graphGap: 0, action: "archive", title: "No recorded point", source: "", summary: "" };

export function EvidenceSpace({
  back,
  highlightInLantern,
  initialEvidence,
  highlightLabel = "Highlight in Lantern",
  dataset,
}: {
  back: () => void;
  highlightInLantern: (evidence: EvidencePoint) => void;
  initialEvidence?: EvidencePoint | null;
  highlightLabel?: string;
  /** Persisted mode: recorded Focus coordinates per checkpoint. No demo points are mixed in. */
  dataset?: PersistedSpaceDataset;
}) {
  const firstWithPoints = dataset ? (dataset.checkpoints.find((c) => c.id === dataset.initialCheckpoint) ?? dataset.checkpoints.find((c) => c.points.length) ?? dataset.checkpoints[0]) : null;
  const [selected, setSelected] = useState<EvidencePoint>(
    initialEvidence ?? (dataset ? (firstWithPoints?.points[0] ?? PLACEHOLDER_POINT) : parentEvidence[2]),
  );
  const [checkpoint, setCheckpoint] = useState(dataset ? (firstWithPoints?.id ?? "") : "Final checkpoint");
  const [empty, setEmpty] = useState(dataset ? !(firstWithPoints?.points.length) : false);
  const datasetCp = dataset?.checkpoints.find((c) => c.id === checkpoint) ?? null;
  const [lantern, setLantern] = useState<"parent" | "child">(
    initialEvidence && !parentEvidence.some((p) => p.id === initialEvidence.id) ? "child" : "parent",
  );
  const [compare, setCompare] = useState(false);
  const [tool, setTool] = useState<"rotate" | "pan">("rotate");
  const [yaw, setYaw] = useState(-0.58);
  const [pitch, setPitch] = useState(0.38);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<EvidencePoint | null>(null);
  const [drag, setDrag] = useState<{
    x: number;
    y: number;
    yaw: number;
    pitch: number;
    panX: number;
    panY: number;
  } | null>(null);
  const [preview, setPreview] = useState(false);
  const [branchCreated, setBranchCreated] = useState(false);
  const [weights, setWeights] = useState({ relevance: 1, novelty: 1, graphGap: 1 });
  const evidence = dataset
    ? (datasetCp?.points ?? [])
    : compare
    ? [
        ...parentEvidence,
        ...childEvidence.filter((p) => !parentEvidence.some((parent) => parent.id === p.id)),
      ]
    : lantern === "parent"
      ? parentEvidence
      : childEvidence;
  const cubeCorners = [
    { relevance: 0, novelty: 0, graphGap: 0 },
    { relevance: 1, novelty: 0, graphGap: 0 },
    { relevance: 0, novelty: 1, graphGap: 0 },
    { relevance: 1, novelty: 1, graphGap: 0 },
    { relevance: 0, novelty: 0, graphGap: 1 },
    { relevance: 1, novelty: 0, graphGap: 1 },
    { relevance: 0, novelty: 1, graphGap: 1 },
    { relevance: 1, novelty: 1, graphGap: 1 },
  ].map((p) => projectEvidence(p, yaw, pitch, zoom, pan));
  const cubeEdges = [
    [0, 1],
    [0, 2],
    [0, 4],
    [1, 3],
    [1, 5],
    [2, 3],
    [2, 6],
    [3, 7],
    [4, 5],
    [4, 6],
    [5, 7],
    [6, 7],
  ];
  const rankedPreview = [...evidence]
    .sort(
      (a, b) =>
        b.relevance * weights.relevance +
        b.novelty * weights.novelty +
        b.graphGap * weights.graphGap -
        (a.relevance * weights.relevance +
          a.novelty * weights.novelty +
          a.graphGap * weights.graphGap),
    )
    .slice(0, 3);
  return (
    <main className="app-main space-screen">
      <Topbar
        status="stopped"
        onBack={back}
        title={dataset?.question}
        statusLabel={dataset ? <Tag tone="teal">Persisted · recorded coordinates</Tag> : undefined}
      />
      <div className="space-head">
        <div>
          <small>3D evidence space</small>
          <h2>How evidence aligned with this investigation</h2>
          <p>Position reflects ranking signals—not factual confidence.</p>
        </div>
        {dataset ? (
          <div>
            <select
              aria-label="Recorded checkpoint"
              value={checkpoint}
              onChange={(e) => {
                const next = dataset.checkpoints.find((c) => c.id === e.target.value);
                setCheckpoint(e.target.value);
                setEmpty(!next?.points.length);
                const same = next?.points.find((pt) => pt.id === selected.id);
                if (same || next?.points[0]) setSelected(same ?? next!.points[0]);
              }}
            >
              {dataset.checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label} · {c.points.length} recorded points
                </option>
              ))}
            </select>
          </div>
        ) : (
        <div>
          <select
            aria-label="Lantern"
            value={lantern}
            onChange={(e) => {
              const next = e.target.value as "parent" | "child";
              setLantern(next);
              setCompare(false);
              setSelected(next === "parent" ? parentEvidence[2] : childEvidence[2]);
            }}
          >
            <option value="parent">Parent · capacity loop</option>
            <option value="child">Child · power constraints</option>
          </select>
          <select
            value={checkpoint}
            onChange={(e) => {
              setCheckpoint(e.target.value);
              setEmpty(e.target.value === "Earlier checkpoint");
            }}
          >
            <option>Final checkpoint</option>
            <option>Expansion checkpoint</option>
            <option>Earlier checkpoint</option>
          </select>
          <button
            className={`outline-button ${compare ? "active" : ""}`}
            onClick={() => setCompare(!compare)}
          >
            <Icon name="compare" /> {compare ? "Comparing" : "Compare Lanterns"}
          </button>
        </div>
        )}
      </div>
      <div className="snapshot-context">
        <div>
          <span className="snapshot-marker">
            <Icon name="lantern" size={15} />
          </span>
          <p>
            <b>{dataset ? (datasetCp?.label ?? "No checkpoint") : checkpoint}</b>
            <small>{dataset ? (datasetCp ? `Checkpoint ${datasetCp.id}` : "No persisted checkpoint") : empty ? "Historical research state" : "Stopped with uncertainty"}</small>
          </p>
        </div>
        <p>
          {dataset && empty
            ? "This checkpoint recorded no Focus policy coordinates. Nothing is plotted, and nothing is estimated."
            : empty
            ? "This checkpoint predates stored ranking coordinates."
            : "Showing evidence positions recorded at this checkpoint. Positions have not been regenerated."}
        </p>
        <Tag tone={empty ? "blue" : "amber"}>{empty ? "Playback only" : "Recorded snapshot"}</Tag>
      </div>
      <div className="space-layout with-snapshot">
        <section className="plot-wrap">
          {!empty ? (
            <>
              <div className="plot-explanation">
                Explore how the research agent evaluated evidence. Each point is positioned by
                relevance, novelty, and connection to unanswered questions. Its color shows what the
                agent decided to do with it.
              </div>
              <svg
                className={`policy-plot ${tool}`}
                viewBox="0 0 780 550"
                role="application"
                aria-label="Interactive Focus policy scoring space"
                onPointerDown={(e) => {
                  e.currentTarget.setPointerCapture(e.pointerId);
                  setDrag({ x: e.clientX, y: e.clientY, yaw, pitch, panX: pan.x, panY: pan.y });
                }}
                onPointerMove={(e) => {
                  if (!drag) return;
                  const dx = e.clientX - drag.x;
                  const dy = e.clientY - drag.y;
                  if (tool === "rotate") {
                    setYaw(drag.yaw + dx * 0.009);
                    setPitch(Math.max(-1.15, Math.min(1.15, drag.pitch + dy * 0.009)));
                  } else setPan({ x: drag.panX + dx, y: drag.panY + dy });
                }}
                onPointerUp={() => setDrag(null)}
                onPointerCancel={() => setDrag(null)}
                onWheel={(e) => {
                  e.preventDefault();
                  setZoom((z) => Math.max(0.65, Math.min(1.55, z - e.deltaY * 0.001)));
                }}
              >
                <g className="policy-cube">
                  {cubeEdges.map(([a, b], i) => (
                    <line
                      key={i}
                      x1={cubeCorners[a].x}
                      y1={cubeCorners[a].y}
                      x2={cubeCorners[b].x}
                      y2={cubeCorners[b].y}
                    />
                  ))}
                </g>
                <g className="axis-labels">
                  <text x={cubeCorners[0].x} y={cubeCorners[0].y + 18}>
                    0
                  </text>
                  <text x={cubeCorners[1].x + 8} y={cubeCorners[1].y}>
                    1 · Intent alignment (X)
                  </text>
                  <text x={cubeCorners[2].x - 8} y={cubeCorners[2].y - 10}>
                    1 · Novelty (Y)
                  </text>
                  <text x={cubeCorners[4].x - 8} y={cubeCorners[4].y - 10}>
                    1 · Open-question alignment (Z)
                  </text>
                </g>
                {[...evidence]
                  .sort(
                    (a, b) =>
                      projectEvidence(a, yaw, pitch, zoom, pan).depth -
                      projectEvidence(b, yaw, pitch, zoom, pan).depth,
                  )
                  .map((p) => {
                    const pos = projectEvidence(p, yaw, pitch, zoom, pan);
                    const isNew =
                      compare && !p.shared && childEvidence.some((child) => child.id === p.id);
                    return (
                      <g
                        key={p.id}
                        className={`evidence-mark ${p.action} ${selected.id === p.id ? "selected" : ""}`}
                        transform={`translate(${pos.x} ${pos.y})`}
                        onPointerEnter={() => setHovered(p)}
                        onPointerLeave={() => setHovered(null)}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelected(p);
                        }}
                        tabIndex={0}
                        role="button"
                        aria-label={`${p.title}, ${p.action}`}
                      >
                        {isNew ? (
                          <path d="M0-8 8 0 0 8-8 0Z" />
                        ) : (
                          <circle r={p.shared && compare ? 7 : 6} />
                        )}
                        {p.shared && compare && <circle className="shared-ring" r="11" />}
                      </g>
                    );
                  })}
              </svg>
              {hovered &&
                (() => {
                  const pos = projectEvidence(hovered, yaw, pitch, zoom, pan);
                  return (
                    <div
                      className="policy-tooltip"
                      style={{ left: `${pos.x / 7.8}%`, top: `${pos.y / 5.5}%` }}
                    >
                      <Tag
                        tone={
                          hovered.action === "consider"
                            ? "green"
                            : hovered.action === "investigate"
                              ? "amber"
                              : "gray"
                        }
                      >
                        {hovered.action}
                      </Tag>
                      <b>{hovered.title}</b>
                      <small>{hovered.source}</small>
                      <p>{hovered.summary}</p>
                      <div>
                        <span>
                          Intent <b>{hovered.relevance.toFixed(2)}</b>
                        </span>
                        <span>
                          Novelty <b>{hovered.novelty.toFixed(2)}</b>
                        </span>
                        <span>
                          Open questions <b>{hovered.graphGap.toFixed(2)}</b>
                        </span>
                      </div>
                    </div>
                  );
                })()}
              <div className="policy-legend">
                <span>
                  <i className="consider" />
                  Consider
                </span>
                <span>
                  <i className="investigate" />
                  Investigate
                </span>
                <span>
                  <i className="archive" />
                  Archive
                </span>
                {compare && (
                  <>
                    <span className="legend-divider" />
                    <span>
                      <i className="shared-marker" />
                      Shared
                    </span>
                    <span>
                      <i className="new-marker" />
                      New in child
                    </span>
                  </>
                )}
              </div>
              <div className="plot-controls">
                <button
                  className={tool === "rotate" ? "active" : ""}
                  onClick={() => setTool("rotate")}
                >
                  <Icon name="cube" /> Rotate
                </button>
                <button className={tool === "pan" ? "active" : ""} onClick={() => setTool("pan")}>
                  <Icon name="arrow" /> Pan
                </button>
                <button onClick={() => setZoom((z) => Math.min(1.55, z + 0.12))}>＋</button>
                <button onClick={() => setZoom((z) => Math.max(0.65, z - 0.12))}>−</button>
                <button
                  onClick={() => {
                    setYaw(-0.58);
                    setPitch(0.38);
                    setZoom(1);
                    setPan({ x: 0, y: 0 });
                  }}
                >
                  Reset
                </button>
              </div>
            </>
          ) : (
            <div className="empty-space">
              <span>
                <Icon name="cube" size={30} />
              </span>
              <h3>No recorded coordinates</h3>
              <p>
                Evidence ranking coordinates were not stored for this historical checkpoint. Choose
                a later checkpoint to explore its distribution.
              </p>
              {!dataset && (
                <button
                  onClick={() => {
                    setEmpty(false);
                    setCheckpoint("Final checkpoint");
                  }}
                >
                  View final checkpoint
                </button>
              )}
            </div>
          )}
        </section>
        <aside className="space-inspector">
          <Tag
            tone={
              selected.action === "consider"
                ? "green"
                : selected.action === "investigate"
                  ? "amber"
                  : "gray"
            }
          >
            {selected.action}
          </Tag>
          <h2>{selected.title}</h2>
          <p className="source-line">
            {selected.source} · {dataset ? <>Recorded candidate <code>{selected.id}</code></> : "Illustrative recorded passage"}
          </p>
          <div className="score-list">
            <div>
              <span>Intent alignment</span>
              <b>{selected.relevance.toFixed(2)}</b>
              <i>
                <em style={{ width: `${selected.relevance * 100}%` }} />
              </i>
            </div>
            <div>
              <span>Novelty</span>
              <b>{selected.novelty.toFixed(2)}</b>
              <i>
                <em style={{ width: `${selected.novelty * 100}%` }} />
              </i>
            </div>
            <div>
              <span>Unresolved-question alignment</span>
              <b>{selected.graphGap.toFixed(2)}</b>
              <i>
                <em style={{ width: `${selected.graphGap * 100}%` }} />
              </i>
            </div>
          </div>
          <div className="score-warning">
            <Icon name="alert" />
            <p>
              These values show research relevance. They do not measure whether a claim is true.
            </p>
          </div>
          <InfoBlock label="Evidence passage">
            <blockquote>{selected.summary}</blockquote>
          </InfoBlock>
          <button className="primary wide" onClick={() => highlightInLantern(selected)}>
            <Icon name="lantern" /> {highlightLabel}
          </button>
          <button
            className={`secondary wide ${branchCreated ? "branch-created" : ""}`}
            disabled={!!dataset}
            title={dataset ? "Read-only integration: creating Lanterns from persisted data arrives in Milestone 2." : undefined}
            onClick={() => setBranchCreated(true)}
          >
            <Icon name={branchCreated ? "check" : "branch"} />{" "}
            {branchCreated ? "Child Lantern created" : "Launch Lantern from evidence"}
          </button>
{!dataset && (
                    <small className="eligibility">
            <Icon name="check" /> Eligible checkpoint available · parent remains unchanged
          </small>
          )}
          <button className="ranking-preview-toggle" onClick={() => setPreview(!preview)}>
            <span>
              <Icon name="settings" /> Preview ranking priorities
            </span>
            <Icon name="chevron" />
          </button>
          {preview && (
            <div className="ranking-preview">
              <div className="preview-notice">
                <Icon name="alert" />
                <p>
                  <b>Display-only preview</b>Weights reorder this list only. Recorded scores and
                  point positions never change.
                </p>
              </div>
              {(["relevance", "novelty", "graphGap"] as const).map((key) => (
                <label key={key}>
                  <span>
                    {key === "graphGap" ? "Open questions" : key[0].toUpperCase() + key.slice(1)}{" "}
                    <b>{weights[key].toFixed(1)}×</b>
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step=".1"
                    value={weights[key]}
                    onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                  />
                </label>
              ))}
              <small>Preview order</small>
              {rankedPreview.map((p, i) => (
                <div className="preview-rank" key={p.id}>
                  <b>{i + 1}</b>
                  <span>{p.title}</span>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

function Compare({ back }: { back: () => void }) {
  const [filter, setFilter] = useState("All differences");
  return (
    <main className="app-main compare-screen">
      <Topbar status="stopped" onBack={back} />
      <div className="compare-head">
        <div>
          <small>Compare related Lanterns</small>
          <h2>What changed when we followed the power constraint?</h2>
        </div>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option>All differences</option>
          <option>Contradictions only</option>
          <option>New evidence only</option>
        </select>
      </div>
      <div className="compare-pair">
        <div>
          <Tag tone="amber">Parent Lantern</Tag>
          <h3>NVIDIA infrastructure investment loop</h3>
          <p>Stopped with uncertainty · 23 sources</p>
        </div>
        <span className="versus">
          <Icon name="compare" /> compared with
        </span>
        <div>
          <Tag tone="violet">Child Lantern</Tag>
          <h3>Power constraints on AI capacity</h3>
          <p>Active branch · 14 sources</p>
        </div>
      </div>
      <div className="compare-content">
        <section className="compare-summary">
          <h3>The research frontier shifted</h3>
          <p>
            The parent identified energy as a possible constraint. The child found stronger regional
            evidence that grid access delays deployment—but not enough to generalize globally.
          </p>
          <div className="shift-visual">
            <div>
              <small>Parent frontier</small>
              <span>
                Who carries
                <br />
                financing risk?
              </span>
            </div>
            <Icon name="arrow" />
            <div>
              <small>Child frontier</small>
              <span>
                Where is power
                <br />
                actually binding?
              </span>
            </div>
          </div>
        </section>
        <section className="difference-grid">
          <article className="diff-card shared">
            <div>
              <span>
                <Icon name="source" />
              </span>
              <small>Shared evidence</small>
              <b>6 sources used by both Lanterns</b>
            </div>
            <p>
              Both rely on capacity plans, customer commitments, and regional buildout disclosures.
            </p>
            <button>
              Review shared sources <Icon name="arrow" />
            </button>
          </article>
          <article className="diff-card new">
            <div>
              <span>
                <Icon name="spark" />
              </span>
              <small>New in child</small>
              <b>8 sources on power and grid access</b>
            </div>
            <p>Utility filings and interconnection studies add geographic specificity.</p>
            <button>
              Review new evidence <Icon name="arrow" />
            </button>
          </article>
          <article className="diff-card conflict">
            <div>
              <span>
                <Icon name="alert" />
              </span>
              <small>Contradictory evidence</small>
              <b>Constraint severity differs by region</b>
            </div>
            <p>Some markets report multi-year delays; others show capacity already secured.</p>
            <button>
              Inspect contradiction <Icon name="arrow" />
            </button>
          </article>
        </section>
        <section className="conclusion-compare">
          <h3>Different conclusions</h3>
          <div className="conclusion-cols">
            <div>
              <small>Parent conclusion</small>
              <p>
                Financing and customer demand reinforce capacity expansion, with energy as an
                unresolved constraint.
              </p>
              <Tag tone="amber">Stopped: diminishing new evidence</Tag>
            </div>
            <div>
              <small>Child conclusion</small>
              <p>
                Power is a binding constraint in specific markets, but available evidence does not
                support a global conclusion.
              </p>
              <Tag tone="violet">Active: testing regional variation</Tag>
            </div>
          </div>
        </section>
        <section className="open-compare">
          <div>
            <Icon name="alert" />
            <span>
              <small>Unresolved in both</small>
              <b>
                Can providers relocate capacity quickly enough to route around grid constraints?
              </b>
            </span>
          </div>
          <button>
            <Icon name="branch" /> Create a focused Lantern
          </button>
        </section>
      </div>
    </main>
  );
}

const ALL_EVIDENCE: EvidencePoint[] = [
  ...parentEvidence,
  ...childEvidence.filter((c) => !parentEvidence.some((p) => p.id === c.id)),
];

const P = TRACES.parent;
const seqOf = (id: string) => P.nodes.find((n) => n.id === id)!.revealAt;

export default function App() {
  const [mode, setModeState] = useState<AppMode>(() => readUrlState().mode);
  const [recentVersion, setRecentVersion] = useState(0);
  const setMode = (m: AppMode) => {
    setModeState(m);
    if (m === "demo") writeUrlState({ mode: "demo", investigation: null, node: null, checkpoint: null }, { push: true });
    else writeUrlState({ mode: "live" }, { push: true });
  };
  useEffect(() => {
    const onPop = () => setModeState(readUrlState().mode);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const [screen, setScreen] = useState<Screen>("home");
  const [collapsed, setCollapsed] = useState(false);
  const [resultEntry, setResultEntry] = useState<"default" | "evidence">("default");
  const [focusedEvidence, setFocusedEvidence] = useState<EvidencePoint | null>(null);
  const [spaceFrom, setSpaceFrom] = useState<"results" | "interior">("results");

  // ── Lantern + investigation state (lifted so every Lantern keeps its place) ──
  const [lanterns, setLanterns] = useState<Lantern[]>(INITIAL_LANTERNS);
  const [activeLantern, setActiveLantern] = useState("parent");
  const [views, setViews] = useState<Record<string, ViewState>>({});
  const [live, setLive] = useState<Record<string, number>>({});
  const [cmp, setCmp] = useState({ a: "c2", b: "c4" });
  const [constHighlight, setConstHighlight] = useState<string | null>(null);
  const [toast, setToast] = useState<{ id: string; title: string; from: string; mode: string } | null>(null);
  const [demo, setDemo] = useState<number | null>(null);
  const forkCount = useRef(0);

  const traces = useMemo(() => {
    const out: Record<string, Trace> = { ...TRACES };
    for (const l of lanterns) if (l.userCreated && l.parentId) out[l.id] = forkTrace(l, out[l.parentId] ?? TRACES.parent);
    return out;
  }, [lanterns]);
  const latestOf = (id: string) => {
    const t = traces[id];
    const full = t.events.length - 1;
    return live[id] !== undefined ? Math.min(full, live[id]) : full;
  };

  // simulated live research for "Fork & Investigate" Lanterns
  useEffect(() => {
    const pending = lanterns.filter((l) => l.createdMode === "investigate" && (live[l.id] ?? 0) < traces[l.id].events.length - 1);
    if (!pending.length) return;
    const t = window.setTimeout(() => {
      setLive((cur) => {
        const next = { ...cur };
        for (const l of pending) next[l.id] = (cur[l.id] ?? 1) + 1;
        return next;
      });
    }, 1700);
    return () => window.clearTimeout(t);
  }, [lanterns, live, traces]);

  const getView = (id: string) => views[id] ?? defaultView();
  const patchView = (id: string, patch: ViewPatch) =>
    setViews((cur) => {
      const v = cur[id] ?? defaultView();
      const p = typeof patch === "function" ? patch(v) : patch;
      return { ...cur, [id]: { ...v, ...p } };
    });

  const openLantern = (id: string) => {
    setActiveLantern(id);
    setScreen("interior");
  };
  const openAt = (id: string, nodeId: string, extra: Partial<ViewState> = {}) => {
    const t = traces[id];
    const { expand, round } = revealPath(t, nodeId);
    patchView(id, (v) => ({
      selected: nodeId,
      composer: null,
      expanded: Array.from(new Set([...v.expanded, ...expand])),
      collapsedRounds: v.collapsedRounds.filter((r) => r !== round),
      focusIds: [nodeId],
      focusNonce: v.focusNonce + 1,
      ...extra,
    }));
    openLantern(id);
  };

  const createFork = (draft: ComposerDraft, mode: "saved" | "investigate", fromId = activeLantern) => {
    forkCount.current += 1;
    const id = `fork-${forkCount.current}`;
    const used = new Set(lanterns.map((l) => l.slot));
    const slot = [3, 4, 5, 6, 0, 1, 2].find((s) => !used.has(s)) ?? 6;
    const lantern: Lantern = {
      id,
      title: draft.title,
      objective: draft.objective,
      status: mode === "investigate" ? "researching" : "not-started",
      parentId: fromId,
      fromCheckpoint: draft.checkpointId ?? undefined,
      attachedClaim: draft.claimId ?? undefined,
      attachedSources: draft.sourceIds,
      userCreated: true,
      createdMode: mode,
      slot,
    };
    setLanterns((cur) => [...cur, lantern]);
    if (mode === "investigate") setLive((cur) => ({ ...cur, [id]: 1 }));
    patchView(fromId, (v) => ({ composer: null, selected: `fork:${id}`, focusIds: [`fork:${id}`, traces[fromId].checkpoints.find((c) => c.id === draft.checkpointId)?.nodeId ?? ""], focusNonce: v.focusNonce + 1 }));
    const cp = traces[fromId].checkpoints.find((c) => c.id === draft.checkpointId);
    setToast({ id, title: draft.title, from: cp ? `${cp.short} · ${cp.label}` : "parent", mode });
    setConstHighlight(id);
    return id;
  };

  const startResearch = (id: string) => {
    setLanterns((cur) => cur.map((l) => (l.id === id ? { ...l, createdMode: "investigate", status: "researching" } : l)));
    setLive((cur) => ({ ...cur, [id]: 1 }));
  };

  const highlightFromSpace = (evidence: EvidencePoint) => {
    const order = [activeLantern, "parent", "power"];
    for (const lid of order) {
      const node = traces[lid]?.nodes.find((n) => n.evId === evidence.id);
      if (node) {
        openAt(lid, node.id, { cursor: -1, snapshot: null });
        return;
      }
    }
    openLantern(activeLantern);
  };

  // ── Guided demo: the 12-step journey ──
  const demoForkId = useRef<string | null>(null);
  const parentAt = (patch: Partial<ViewState>) => {
    setViews((cur) => ({ ...cur, parent: { ...(cur.parent ?? defaultView()), composer: null, ...patch, focusNonce: (cur.parent?.focusNonce ?? 0) + 1 } }));
    setActiveLantern("parent");
    setScreen("interior");
  };
  const demoSteps: DemoStep[] = [
    {
      title: "Open the parent Lantern from the Constellation",
      body: "The Constellation is the zoomed-out research landscape. Entering the parent Lantern shows its whole recorded journey: three rounds that each expand into searches and sources, then converge on a decision.",
      run: () => parentAt({ cursor: -1, snapshot: null, selected: null, expanded: [], collapsedRounds: [], zoom: 0.16, focusIds: ["intent", "cp-c4", "g5", "g1"] }),
    },
    {
      title: "See exploration round 1 and its searches",
      body: "Step back to the first round. Blue nodes are what the agent did: it opened round 1 and issued two searches. The source groups are what those searches returned.",
      run: () => parentAt({ cursor: seqOf("g2"), snapshot: null, selected: "r1", expanded: [], focusIds: ["r1", "q1", "q2", "g1", "g2"] }),
    },
    {
      title: "Expand a source cluster",
      body: "Source groups are summarised by default. Expanding “Customers & financing” reveals its documents. Origin badges show primary (P), secondary (S) and derivative (D) sources.",
      run: () => parentAt({ cursor: seqOf("p7"), snapshot: null, selected: "g2", expanded: ["g2"], focusIds: ["g2", "d4", "d5", "d6", "d7"] }),
    },
    {
      title: "Open an extracted claim",
      body: "After evaluation, passages are grouped around the claims they support or challenge. This claim links customer contracts to financing. Its supporting passages are highlighted, and the collateral contradiction sits beside it.",
      run: () => parentAt({ cursor: seqOf("k3"), snapshot: null, selected: "k2", expanded: ["g2", "d4", "d6"], focusIds: ["k2", "x1", "p4", "p6"] }),
    },
    {
      title: "Step forward to the next recorded decision",
      body: "Paths converge on a recorded decision. The inspector explains it from recorded controller fields (trigger, frontier, budget), not from private model reasoning.",
      run: () => parentAt({ cursor: seqOf("dc1"), snapshot: null, selected: "dc1", focusIds: ["dc1", "cp-c2", "oq1", "k2"] }),
    },
    {
      title: "The agent continues in a new direction",
      body: "Round 2 opens. The dashed amber edge shows that the open question on downside risk prompted the follow-up search.",
      run: () => parentAt({ cursor: seqOf("q3"), snapshot: null, selected: "r2", focusIds: ["oq1", "r2", "q3"] }),
    },
    {
      title: "The graph expands with additional sources",
      body: "New searches return more sources and the round widens again. Shared-origin links show that a blog restates a rating note and that a risk-factor section comes from the same filing as round 1.",
      run: () => parentAt({ cursor: seqOf("p12"), snapshot: null, selected: "g3", expanded: ["g2", "g3", "g4"], focusIds: ["g3", "g4", "q3", "q4"] }),
    },
    {
      title: "The investigation stops with unresolved uncertainty",
      body: "After a third round on power, the controller stops: new results were mostly derivative. Stopping is a convergence decision — it does not mean the conclusions are verified.",
      run: () => parentAt({ cursor: -1, snapshot: null, selected: "dc3", focusIds: ["dc3", "cp-c4", "oq3", "x3"] }),
    },
    {
      title: "Return to an earlier checkpoint",
      body: "Load checkpoint C2, the persisted state after round 1 was evaluated. The gold banner shows this is a resumable snapshot, not just an event in the playback history. C1 is view-only because no research state was saved with it.",
      run: () => parentAt({ cursor: seqOf("cp-c2"), snapshot: "c2", selected: "cp-c2", focusIds: ["cp-c2", "dc1", "k2"] }),
    },
    {
      title: "Fork a Lantern to challenge a specific claim",
      body: "From C2, challenge the contracts → financing claim. The new Lantern keeps the original question, the claim, its sources, the parent and the checkpoint. Choose Save Lantern (no new research) or Fork & Investigate (starts simulated research). Press Next to fork and investigate.",
      run: () => {
        const k2 = P.nodes.find((n) => n.id === "k2")!;
        parentAt({
          cursor: seqOf("cp-c2"),
          snapshot: "c2",
          selected: "k2",
          focusIds: ["k2", "cp-c2"],
          composer: {
            intent: "challenge",
            claimId: "k2",
            sourceIds: ["d4", "d6"],
            checkpointId: "c2",
            title: "Verify the customer-financing claim",
            objective: `Test whether “${k2.label}” holds using only sources that do not originate from company disclosures.`,
          },
        });
      },
    },
    {
      title: "The child appears in the Constellation",
      body: "The new child Lantern emerges from parent checkpoint C2 on the rail, not from the final state. It is researching in this simulation; open it to watch its first round arrive.",
      run: () => {
        let id =
          demoForkId.current ??
          lanterns.find((l) => l.userCreated && l.fromCheckpoint === "c2" && l.attachedClaim === "k2")?.id ??
          null;
        if (!id || !lanterns.some((l) => l.id === id)) {
          const k2 = P.nodes.find((n) => n.id === "k2")!;
          id = createFork(
            {
              intent: "challenge",
              claimId: "k2",
              sourceIds: ["d4", "d6"],
              checkpointId: "c2",
              title: "Verify the customer-financing claim",
              objective: `Test whether “${k2.label}” holds using only sources that do not originate from company disclosures.`,
            },
            "investigate",
            "parent",
          );
          demoForkId.current = id;
        }
        setToast(null);
        setConstHighlight(id);
        setScreen("constellation");
      },
    },
    {
      title: "Return to the original investigation where you left it",
      body: "The parent is unchanged and reopens exactly where you were: snapshot C2 loaded, with the new child shown emerging from that checkpoint. Use the breadcrumbs to move between parent and child without losing your place in either.",
      run: () => {
        setActiveLantern("parent");
        setScreen("interior");
      },
    },
  ];
  const startDemo = () => {
    setDemo(0);
    demoSteps[0].run();
  };

  const active = lanterns.find((l) => l.id === activeLantern) ?? lanterns[0];

  let content: React.ReactNode;
  if (screen === "home") content = <Home start={() => setScreen("active")} />;
  else if (screen === "active") content = <Active finish={() => setScreen("results")} />;
  else if (screen === "results")
    content = (
      <Results
        initialMode={resultEntry === "evidence" ? "lantern" : "findings"}
        initialInspector={resultEntry === "evidence" ? "claim" : null}
        initialEvidence={resultEntry === "evidence" ? focusedEvidence : null}
        goCompare={() => setScreen("compare")}
        goSpace={() => {
          setSpaceFrom("results");
          setScreen("space");
        }}
      />
    );
  else if (screen === "constellation")
    content = (
      <ConstellationView
        key={constHighlight ?? "c"}
        lanterns={lanterns}
        traces={traces}
        latestOf={latestOf}
        highlight={constHighlight}
        onOpen={openLantern}
        onOpenAt={(id, nodeId) => openAt(id, nodeId)}
        onCompareLanterns={() => setScreen("compare")}
        onBack={() => setScreen("results")}
        onDemo={startDemo}
      />
    );
  else if (screen === "interior")
    content = (
      <Interior
        key={active.id}
        lantern={active}
        lanterns={lanterns}
        trace={traces[active.id]}
        latest={latestOf(active.id)}
        view={getView(active.id)}
        setView={(p) => patchView(active.id, p)}
        onBack={() => setScreen("constellation")}
        onOpenLantern={openLantern}
        onCompare={(a, b) => {
          setCmp({ a, b });
          setScreen("checkpointCompare");
        }}
        onOpen3D={(evId) => {
          setFocusedEvidence(evId ? ALL_EVIDENCE.find((e) => e.id === evId) ?? null : null);
          setSpaceFrom("interior");
          setScreen("space");
        }}
        onCreateFork={(d, m) => createFork(d, m)}
        onStartResearch={() => startResearch(active.id)}
        onDemo={startDemo}
      />
    );
  else if (screen === "checkpointCompare")
    content = (
      <CheckpointCompare
        lantern={active}
        trace={traces[active.id]}
        a={traces[active.id].checkpoints.some((c) => c.id === cmp.a) ? cmp.a : traces[active.id].checkpoints[0].id}
        b={traces[active.id].checkpoints.some((c) => c.id === cmp.b) ? cmp.b : traces[active.id].checkpoints.slice(-1)[0].id}
        setPair={(a, b) => setCmp({ a, b })}
        onBack={() => setScreen("interior")}
        onShow={(nodeId, cpId) => {
          const cp = traces[active.id].checkpoints.find((c) => c.id === cpId)!;
          openAt(active.id, nodeId, { cursor: cp.seq >= latestOf(active.id) ? -1 : cp.seq, snapshot: cpId });
        }}
      />
    );
  else if (screen === "knowledge") content = <Knowledge />;
  else if (screen === "space")
    content = (
      <EvidenceSpace
        key={focusedEvidence?.id ?? "space"}
        initialEvidence={focusedEvidence}
        highlightLabel={spaceFrom === "interior" ? "Show in investigation trace" : "Highlight in Lantern"}
        back={() => {
          if (spaceFrom === "interior") setScreen("interior");
          else {
            setResultEntry("default");
            setScreen("results");
          }
        }}
        highlightInLantern={(evidence) => {
          if (spaceFrom === "interior") highlightFromSpace(evidence);
          else {
            setFocusedEvidence(evidence);
            setResultEntry("evidence");
            setScreen("results");
          }
        }}
      />
    );
  else content = <Compare back={() => setScreen("constellation")} />;

  if (mode === "live")
    return (
      <div className="app-shell" data-mode="live">
        <Sidebar screen={screen} setScreen={setScreen} collapsed={collapsed} setCollapsed={setCollapsed} mode={mode} onMode={setMode} recentVersion={recentVersion} />
        <PersistedWorkspace
          onRecentChange={() => setRecentVersion((v) => v + 1)}
          render3D={(a) => (
            <EvidenceSpace
              key={`${a.initialCheckpoint}:${a.initialEvidenceId}`}
              dataset={{ question: a.question, checkpoints: a.checkpoints, initialCheckpoint: a.initialCheckpoint }}
              initialEvidence={a.initialEvidenceId ? (a.checkpoints.find((c) => c.id === a.initialCheckpoint)?.points.find((p) => p.id === a.initialEvidenceId) ?? null) : null}
              highlightLabel="Show in investigation trace"
              back={a.onBack}
              highlightInLantern={(e) => a.onShowInTrace(e.id)}
            />
          )}
        />
      </div>
    );

  return (
    <div className="app-shell" data-mode="demo">
      <Sidebar screen={screen} setScreen={setScreen} collapsed={collapsed} setCollapsed={setCollapsed} mode={mode} onMode={setMode} recentVersion={recentVersion} />
      <div className="demo-ribbon" data-testid="demo-ribbon">
        <Icon name="spark" size={11} /> Demo mode · simulated data, not backend output
      </div>
      {content}
      {toast && demo === null && (
        <div className="toast ix-toast">
          <span>
            <Icon name="check" />
          </span>
          <div>
            <b>Child Lantern created · {toast.mode === "investigate" ? "researching" : "saved, not started"}</b>
            <p>
              “{toast.title}” emerges from {toast.from}. The original investigation is unchanged.
            </p>
            <div className="ix-toast-actions">
              <button
                onClick={() => {
                  openLantern(toast.id);
                  setToast(null);
                }}
              >
                Open child
              </button>
              <button
                onClick={() => {
                  setConstHighlight(toast.id);
                  setScreen("constellation");
                  setToast(null);
                }}
              >
                View in Constellation
              </button>
            </div>
          </div>
          <button onClick={() => setToast(null)}>
            <Icon name="close" />
          </button>
        </div>
      )}
      {demo !== null && <DemoGuide steps={demoSteps} index={demo} setIndex={setDemo} onExit={() => setDemo(null)} />}
    </div>
  );
}
