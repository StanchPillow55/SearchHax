import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, explorationClient } from "../api/client";
import { API_CONFIG, apiOriginLabel } from "../api/config";
import type { CreateBranchBody, InvestigationSummaryT } from "../api/schemas";
import { ConstellationView } from "../trace/Constellation";
import type { BranchingState } from "../trace/Inspector";
import type { ComposerDraft, Lantern } from "../trace/types";
import { adaptInvestigation } from "./adapter";
import { Icon, Tag, type EvidencePoint } from "../shared";
import { STATUS_META } from "../trace/data";
import { revealPath } from "../trace/graph";
import { CheckpointCompare } from "../trace/CheckpointCompare";
import { Interior, defaultView, type ViewPatch } from "../trace/Interior";
import type { Trace, ViewState } from "../trace/types";
import { toEvidencePoint } from "./policy";
import { lanternStatus } from "./adapter";
import { useInvestigation } from "./useInvestigation";
import { readRecent, readUrlState, rememberRecent, writeUrlState } from "./urlState";

export interface Space3DArgs {
  question: string;
  checkpoints: { id: string; label: string; points: EvidencePoint[] }[];
  initialCheckpoint?: string;
  initialEvidenceId: string | null;
  onBack: () => void;
  onShowInTrace: (evidenceId: string) => void;
}

/** Persisted / live mode: a real investigation from the exploration API, read-only. */
export function PersistedWorkspace({ render3D, onRecentChange }: { render3D: (a: Space3DArgs) => React.ReactNode; onRecentChange?: () => void }) {
  const [investigationId, setInvestigationId] = useState<string | null>(() => readUrlState().investigation);
  const { state, retry, refresh } = useInvestigation(investigationId);
  const [branchPending, setBranchPending] = useState(false);
  const pendingRef = useRef(false); // synchronous double-submit guard
  const [branchError, setBranchError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ childId: string; checkpoint: string; mode: "saved" | "investigate" } | null>(null);
  const [views, setViews] = useState<Record<string, ViewState>>({});
  const [screen, setScreen] = useState<"interior" | "compare" | "space" | "constellation">("interior");
  const [cmp, setCmp] = useState<{ a: string; b: string } | null>(null);
  const [space, setSpace] = useState<{ evidenceId: string | null; checkpoint?: string } | null>(null);
  const [restoreNotice, setRestoreNotice] = useState<string | null>(null);

  // Browser back/forward between investigations.
  useEffect(() => {
    const onPop = () => {
      const u = readUrlState();
      if (u.mode === "live") setInvestigationId(u.investigation);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const open = (id: string | null, push = true) => {
    setScreen("interior");
    setBranchError(null);
    setCreated(null);
    setRestoreNotice(null);
    setInvestigationId(id);
    writeUrlState({ mode: "live", investigation: id, node: id ? views[id]?.selected ?? null : null, checkpoint: id ? views[id]?.snapshot ?? null : null }, { push });
  };

  const ready = state.phase === "ready" ? state : null;
  const trace = ready?.data.trace;

  // First load of an investigation: restore selection / snapshot from the URL if they exist in THIS record.
  useEffect(() => {
    if (!ready || views[ready.id]) return;
    const u = readUrlState();
    const t = ready.data.trace;
    let v = defaultView();
    const missing: string[] = [];
    if (u.checkpoint) {
      const cp = t.checkpoints.find((c) => c.id === u.checkpoint);
      if (cp) v = { ...v, snapshot: cp.id, cursor: cp.seq >= t.events.length - 1 ? -1 : cp.seq, selected: cp.nodeId };
      else missing.push(`checkpoint ${u.checkpoint}`);
    }
    if (u.node) {
      const node = t.nodes.find((n) => n.id === u.node) ?? (u.node.startsWith("fork:") ? { id: u.node } : null);
      if (node && "kind" in node) {
        const { expand, round } = revealPath(t, node.id);
        v = { ...v, selected: node.id, expanded: Array.from(new Set([...v.expanded, ...expand])), collapsedRounds: v.collapsedRounds.filter((r) => r !== round), focusIds: [node.id], focusNonce: 1 };
      } else missing.push(`item ${u.node}`);
    }
    if (missing.length) setRestoreNotice(`The saved ${missing.join(" and ")} is not part of ${ready.id}, so it was not restored.`);
    setViews((cur) => ({ ...cur, [ready.id]: v }));
    rememberRecent({ id: ready.id, question: ready.data.trace.question ?? "", status: ready.data.lantern.status });
    onRecentChange?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready?.id, ready?.loadedAt, ready ? !!views[ready.id] : false]);

  const view = ready ? views[ready.id] : undefined;

  // Keep the URL in step with the current selection so a reload reopens the same place.
  useEffect(() => {
    if (!ready || !view) return;
    writeUrlState({ mode: "live", investigation: ready.id, node: view.selected, checkpoint: view.snapshot });
  }, [ready, view?.selected, view?.snapshot]);

  const setView = (patch: ViewPatch) => {
    if (!ready) return;
    setViews((cur) => {
      const v = cur[ready.id] ?? defaultView();
      const p = typeof patch === "function" ? patch(v) : patch;
      return { ...cur, [ready.id]: { ...v, ...p } };
    });
  };

  const lanterns = useMemo(() => (ready ? [ready.data.lantern, ...ready.data.related] : []), [ready]);

  if (!investigationId) return <Picker onOpen={(id) => open(id)} />;
  if (state.phase === "loading" || state.phase === "idle" || (ready && !view))
    return (
      <Shell>
        <div className="pw-card pw-loading" data-testid="pw-loading">
          <span className="pulse" />
          <div>
            <b>Loading {investigationId}</b>
            <p>Reading the investigation, its recorded events and branch records from {apiOriginLabel()}.</p>
          </div>
        </div>
      </Shell>
    );
  if (state.phase === "error") return <ErrorPanel id={state.id} error={state.error} onRetry={retry} onClose={() => open(null)} />;
  if (!ready || !trace || !view) return null;

  if (trace.events.length === 0) return <EmptyInvestigation trace={trace} status={ready.data.lantern.status} id={ready.id} onClose={() => open(null)} />;

  const latest = trace.events.length - 1;
  const spaceCheckpoints = trace.checkpoints.map((c) => ({ id: c.id, label: `${c.short} · ${c.label}`, points: (trace.policyByCheckpoint?.[c.id] ?? []).map(toEvidencePoint) }));

  if (screen === "space" && space)
    return (
      <>
        {render3D({
          question: trace.question ?? "",
          checkpoints: spaceCheckpoints,
          initialCheckpoint: space.checkpoint,
          initialEvidenceId: space.evidenceId,
          onBack: () => setScreen("interior"),
          onShowInTrace: (evidenceId) => {
            const point = Object.values(trace.policyByCheckpoint ?? {}).flat().find((p) => p.evidenceId === evidenceId);
            const docId = point?.documentId && trace.nodes.some((n) => n.id === point.documentId) ? point.documentId : null;
            setScreen("interior");
            if (!docId) {
              setRestoreNotice(`Recorded point ${evidenceId} has no matching document in this trace.`);
              return;
            }
            const { expand, round } = revealPath(trace, docId);
            setView((v) => ({ selected: docId, composer: null, expanded: Array.from(new Set([...v.expanded, ...expand])), collapsedRounds: v.collapsedRounds.filter((r) => r !== round), focusIds: [docId], focusNonce: v.focusNonce + 1 }));
          },
        })}
      </>
    );

  if (screen === "constellation")
    return (
      <LiveConstellation
        currentId={ready.id}
        onBack={() => setScreen("interior")}
        onOpen={(id) => open(id)}
        onOpenAt={(id, nodeId) => {
          if (id === ready.id) {
            const { expand, round } = revealPath(trace, nodeId);
            setView((v) => ({ selected: nodeId, snapshot: null, cursor: -1, composer: null, expanded: Array.from(new Set([...v.expanded, ...expand])), collapsedRounds: v.collapsedRounds.filter((r) => r !== round), focusIds: [nodeId], focusNonce: v.focusNonce + 1 }));
            setScreen("interior");
            return;
          }
          writeUrlState({ mode: "live", investigation: id, node: nodeId, checkpoint: null }, { push: true });
          setViews((cur) => {
            const next = { ...cur };
            delete next[id];
            return next;
          });
          setScreen("interior");
          setInvestigationId(id);
        }}
      />
    );

  const allowInvestigate = API_CONFIG.allowBillableResearch;
  const branching: BranchingState = {
    pending: branchPending,
    error: branchError,
    allowInvestigate,
    investigateDisabledReason: allowInvestigate ? undefined : "Billable research is turned off in this build (VITE_ALLOW_BILLABLE_RESEARCH is not true).",
  };

  const createBranch = async (draft: ComposerDraft, mode: "saved" | "investigate") => {
    if (pendingRef.current) return; // double-submit guard (state updates are async)
    const cp = trace.checkpoints.find((c) => c.id === draft.checkpointId);
    if (!cp || !cp.forkable) {
      setBranchError("Choose a persisted checkpoint to branch from.");
      return;
    }
    // Attach only records that existed at the chosen checkpoint (the backend validates this too).
    const atCp = (id: string) => (trace.nodes.find((n) => n.id === id)?.revealAt ?? Infinity) <= cp.seq;
    const snapshotDocs = new Set(cp.detail?.documents.map((d) => d.id) ?? []);
    const body: CreateBranchBody = {
      from_checkpoint_id: cp.id,
      objective: draft.intent === "continue" ? "" : draft.objective.trim(),
      intervention_type: draft.intent === "continue" ? "continue" : draft.intent === "challenge" ? "challenge_evidence" : "fork",
      constraints: { max_searches: draft.maxSearches ?? 1 },
      attached_claim_ids: draft.claimId && atCp(draft.claimId) ? [draft.claimId] : [],
      attached_source_ids: draft.sourceIds.filter((id) => atCp(id) && (snapshotDocs.size === 0 || snapshotDocs.has(id))),
    };
    pendingRef.current = true;
    setBranchPending(true);
    setBranchError(null);
    try {
      const branch = await explorationClient.createBranch(ready.id, body);
      if (mode === "investigate") {
        await explorationClient.resumeBranch(branch.id, { confirmedBillable: true });
      }
      setCreated({ childId: branch.child_investigation_id, checkpoint: cp.short, mode });
      setView((v) => ({ composer: null, selected: `fork:${branch.child_investigation_id}`, focusIds: [cp.nodeId, `fork:${branch.child_investigation_id}`], focusNonce: v.focusNonce + 1 }));
      refresh();
    } catch (err) {
      setBranchError(err instanceof ApiError ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}` : (err as Error).message);
    } finally {
      pendingRef.current = false;
      setBranchPending(false);
    }
  };

  const startResearch = async () => {
    if (pendingRef.current || !trace.branchId) return;
    pendingRef.current = true;
    setBranchPending(true);
    setBranchError(null);
    try {
      await explorationClient.resumeBranch(trace.branchId, { confirmedBillable: true });
      refresh();
    } catch (err) {
      setBranchError((err as Error).message);
    } finally {
      pendingRef.current = false;
      setBranchPending(false);
    }
  };

  if (screen === "compare" && cmp)
    return (
      <CheckpointCompare
        lantern={ready.data.lantern}
        trace={trace}
        a={cmp.a}
        b={cmp.b}
        setPair={(a, b) => setCmp({ a, b })}
        onBack={() => setScreen("interior")}
        onShow={(nodeId, cpId) => {
          const cp = trace.checkpoints.find((c) => c.id === cpId)!;
          const { expand, round } = revealPath(trace, nodeId);
          setView((v) => ({ cursor: cp.seq >= latest ? -1 : cp.seq, snapshot: cpId, selected: nodeId, expanded: Array.from(new Set([...v.expanded, ...expand])), collapsedRounds: v.collapsedRounds.filter((r) => r !== round), focusIds: [nodeId], focusNonce: v.focusNonce + 1 }));
          setScreen("interior");
        }}
      />
    );

  return (
    <>
      {created && (
        <div className="toast ix-toast" role="status" data-testid="branch-created">
          <span>
            <Icon name="check" />
          </span>
          <div>
            <b>Child investigation saved · {created.mode === "investigate" ? "research step run" : "not started"}</b>
            <p>
              <code>{created.childId}</code> was created from {created.checkpoint}. The parent investigation was not modified.
            </p>
            <div className="ix-toast-actions">
              <button onClick={() => open(created.childId)}>Open child</button>
              <button onClick={() => setScreen("constellation")}>View in Constellation</button>
            </div>
          </div>
          <button onClick={() => setCreated(null)} aria-label="Dismiss">
            <Icon name="close" />
          </button>
        </div>
      )}
      {(restoreNotice || ready.warnings.length > 0) && (
        <div className="pw-notice" role="status">
          <Icon name="alert" size={13} />
          <span>{[restoreNotice, ...ready.warnings].filter(Boolean).join(" ")}</span>
          <button onClick={() => setRestoreNotice(null)} aria-label="Dismiss">
            <Icon name="close" size={12} />
          </button>
        </div>
      )}
      <Interior
        key={ready.id}
        lantern={ready.data.lantern}
        lanterns={lanterns}
        trace={trace}
        latest={latest}
        view={view}
        setView={setView}
        backLabel="Investigations"
        onBack={() => open(null)}
        onOpenLantern={(id) => open(id)}
        onCompare={(a, b) => {
          setCmp({ a, b });
          setScreen("compare");
        }}
        onOpen3D={(evId) => {
          const cur = view.cursor < 0 ? latest : view.cursor;
          const cp = [...trace.checkpoints].reverse().find((c) => c.seq <= cur && (trace.policyByCheckpoint?.[c.id]?.length ?? 0) > 0) ?? trace.checkpoints.find((c) => (trace.policyByCheckpoint?.[c.id]?.length ?? 0) > 0);
          setSpace({ evidenceId: evId, checkpoint: cp?.id });
          setScreen("space");
        }}
        branching={branching}
        onConstellation={() => setScreen("constellation")}
        onCreateFork={(d, m) => void createBranch(d, m)}
        onStartResearch={() => void startResearch()}
        onDemo={() => {}}
      />
    </>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="app-main pw-screen">
      <header className="pw-head">
        <div>
          <small>Live data · read-only</small>
          <h1>Stored investigations</h1>
        </div>
        <span className="ix-sim-badge persisted">
          <Icon name="source" size={11} /> Exploration API · {apiOriginLabel()}
        </span>
      </header>
      <div className="pw-body">{children}</div>
    </main>
  );
}

function Picker({ onOpen }: { onOpen: (id: string) => void }) {
  const [value, setValue] = useState("");
  const recent = readRecent();
  const [list, setList] = useState<{ phase: "loading" } | { phase: "ready"; items: InvestigationSummaryT[]; total: number } | { phase: "unavailable"; reason: string }>({ phase: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    explorationClient
      .listInvestigations(100, 0, controller.signal)
      .then((r) => setList({ phase: "ready", items: r.items, total: r.total }))
      .catch((err) => {
        if (controller.signal.aborted) return;
        const old = err instanceof ApiError && (err.status === 404 || err.status === 405 || err.kind === "not_found");
        setList({ phase: "unavailable", reason: old ? "This backend does not provide the investigation list endpoint." : (err as Error).message });
      });
    return () => controller.abort();
  }, []);
  const valid = /^[A-Za-z0-9_:.-]{1,200}$/.test(value.trim());
  return (
    <Shell>
      <form
        className="pw-card pw-open"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) onOpen(value.trim());
        }}
      >
        <label htmlFor="pw-id">Open a stored investigation by ID</label>
        <div>
          <input id="pw-id" data-testid="investigation-id-input" value={value} placeholder="inv_…" onChange={(e) => setValue(e.target.value)} autoComplete="off" spellCheck={false} />
          <button type="submit" className="primary-button" disabled={!valid}>
            Open <Icon name="arrow" size={14} />
          </button>
        </div>
        <p>
          Paste an investigation ID (as shown in the operator console), or choose one from the stored list below.
        </p>
      </form>
      <section className="pw-recent" data-testid="investigation-list">
        <h2>Stored investigations{list.phase === "ready" ? ` (${list.total})` : ""}</h2>
        {list.phase === "loading" && <p className="pw-empty-line">Loading the list from the exploration API…</p>}
        {list.phase === "unavailable" && <p className="pw-empty-line">List unavailable: {list.reason} Open one by ID instead.</p>}
        {list.phase === "ready" && list.items.length === 0 && <p className="pw-empty-line">The backend has no stored investigations.</p>}
        {list.phase === "ready" &&
          list.items.map((r) => {
            const status = lanternStatus(r.status, r.stop_reason);
            const meta = STATUS_META[status] ?? { tone: "gray", label: r.status };
            return (
              <button key={r.id} className="pw-recent-card" onClick={() => onOpen(r.id)} data-testid="investigation-row">
                <span className={`pw-recent-icon ${r.parent_investigation_id ? "child" : ""}`}>
                  <Icon name={r.parent_investigation_id ? "branch" : "lantern"} size={16} />
                </span>
                <span>
                  <b>{r.question}</b>
                  <small>
                    <code>{r.id}</code> · {r.event_count} events · {r.checkpoint_count} checkpoints · {new Date(r.created_at).toLocaleString()}
                    {r.parent_investigation_id ? ` · child of ${r.parent_investigation_id} (${r.intervention_type ?? "branch"})` : ""}
                  </small>
                </span>
                <Tag tone={meta.tone}>{meta.label}</Tag>
              </button>
            );
          })}
      </section>
      <section className="pw-recent">
        <h2>Recently opened</h2>
        {recent.length === 0 && <p className="pw-empty-line">Nothing opened in this browser yet.</p>}
        {recent.map((r) => {
          const meta = STATUS_META[r.status] ?? { tone: "gray", label: r.status };
          return (
            <button key={r.id} className="pw-recent-card" onClick={() => onOpen(r.id)}>
              <span className="pw-recent-icon">
                <Icon name="lantern" size={16} />
              </span>
              <span>
                <b>{r.question || r.id}</b>
                <small>
                  <code>{r.id}</code> · opened {new Date(r.openedAt).toLocaleString()}
                </small>
              </span>
              <Tag tone={meta.tone}>{meta.label}</Tag>
            </button>
          );
        })}
      </section>
      <p className="pw-footnote">
        Live mode reads persisted records. Saving a child Lantern creates a branch record locally without research; running research is billable and
        {API_CONFIG.allowBillableResearch ? " requires an explicit confirmation each time." : " is turned off in this build."} Switch to Demo in the sidebar for the simulated prototype journey.
      </p>
    </Shell>
  );
}

function ErrorPanel({ id, error, onRetry, onClose }: { id: string; error: ApiError | Error; onRetry: () => void; onClose: () => void }) {
  const kind = error instanceof ApiError ? error.kind : "unknown";
  const title: Record<string, string> = {
    not_found: "Investigation not found",
    network: "Exploration API unreachable",
    timeout: "The exploration API did not respond in time",
    http: "The exploration API returned an error",
    contract: "The response did not match the expected contract",
    unknown: "This investigation could not be displayed",
  };
  const body: Record<string, string> = {
    not_found: `No investigation with ID ${id} exists in this backend.`,
    network: `Could not reach ${apiOriginLabel()}. Check that the FastAPI service is running and that the dev proxy target is correct.`,
    timeout: "The request was cancelled. The backend may be busy; try again.",
    http: error.message,
    contract: "Nothing was rendered, to avoid showing incomplete or misread records.",
    unknown: error.message,
  };
  return (
    <Shell>
      <div className="pw-card pw-error" role="alert" data-testid="pw-error" data-kind={kind}>
        <Icon name="alert" size={20} />
        <div>
          <b>{title[kind] ?? title.unknown}</b>
          <p>{body[kind] ?? body.unknown}</p>
          {error instanceof ApiError && error.issues?.length ? (
            <ul>
              {error.issues.map((i) => (
                <li key={i}>
                  <code>{i}</code>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="pw-actions">
            {kind !== "not_found" && kind !== "contract" && (
              <button className="primary-button" onClick={onRetry}>
                Retry
              </button>
            )}
            <button className="outline-button" onClick={onClose}>
              Choose another investigation
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
}

function EmptyInvestigation({ trace, status, id, onClose }: { trace: Trace; status: string; id: string; onClose: () => void }) {
  const meta = STATUS_META[status] ?? { tone: "gray", label: status };
  return (
    <Shell>
      <div className="pw-card pw-empty" data-testid="pw-empty">
        <Icon name="lantern" size={22} />
        <div>
          <small>
            <code>{id}</code>
          </small>
          <h2 data-testid="research-question">{trace.question}</h2>
          <span data-testid="investigation-status">
            <Tag tone={meta.tone}>{meta.label}</Tag>
          </span>
          <p>No investigation events were recorded for this investigation, so there is no journey to play back. Nothing is reconstructed from its final state.</p>
          {(trace.unplacedCheckpoints?.length ?? 0) > 0 && <p>{trace.unplacedCheckpoints!.length} persisted checkpoint(s) exist without a recorded event.</p>}
          <button className="outline-button" onClick={onClose}>
            Choose another investigation
          </button>
        </div>
      </div>
    </Shell>
  );
}

/** Live Lantern family: the root investigation and its recorded children, each loaded from the API. */
function LiveConstellation({ currentId, onBack, onOpen, onOpenAt }: { currentId: string; onBack: () => void; onOpen: (id: string) => void; onOpenAt: (id: string, nodeId: string) => void }) {
  const [state, setState] = useState<
    | { phase: "loading" }
    | { phase: "error"; message: string }
    | { phase: "ready"; lanterns: Lantern[]; traces: Record<string, Trace>; question: string; hidden: number; notes: string[] }
  >({ phase: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    const c = explorationClient;
    (async () => {
      try {
        const notes: string[] = [];
        // Walk up recorded parent links to the root of the family.
        let rootId = currentId;
        for (let i = 0; i < 10; i++) {
          const t = await c.getTrace(rootId, controller.signal);
          if (!t.parent_investigation_id) break;
          rootId = t.parent_investigation_id;
        }
        const branches = await c.getBranches(rootId, controller.signal);
        const children = branches.filter((b) => b.parent_investigation_id === rootId);
        const shown = children.slice(0, 7);
        const ids = [rootId, ...shown.map((b) => b.child_investigation_id)];
        const settled = await Promise.allSettled(
          ids.map(async (id) => {
            const [e, t] = await Promise.all([c.getInvestigation(id, controller.signal), c.getTrace(id, controller.signal)]);
            return adaptInvestigation(e, t, id === rootId ? branches : []);
          }),
        );
        if (controller.signal.aborted) return;
        if (settled[0].status === "rejected") throw settled[0].reason;
        const loaded = settled.map((r) => (r.status === "fulfilled" ? r.value : null));
        settled.forEach((r, i) => {
          if (i > 0 && r.status === "rejected") notes.push(`Child ${ids[i]} could not be loaded (${(r.reason as Error).message}) and is not drawn.`);
        });
        const traces: Record<string, Trace> = {};
        const lanterns: Lantern[] = [];
        let slot = 0;
        loaded.forEach((a, i) => {
          if (!a) return;
          traces[a.lantern.id] = a.trace;
          if (i === 0) lanterns.push({ ...a.lantern, parentId: undefined });
          else {
            const b = shown[i - 1];
            lanterns.push({ ...a.lantern, parentId: rootId, fromCheckpoint: b.from_checkpoint_id, slot: slot++ });
            if (!loaded[0]!.trace.checkpoints.some((cp) => cp.id === b.from_checkpoint_id))
              notes.push(`${b.child_investigation_id} was created from ${b.from_checkpoint_id}, which has no recorded checkpoint event in the parent timeline.`);
          }
        });
        setState({ phase: "ready", lanterns, traces, question: loaded[0]!.trace.question ?? "", hidden: children.length - shown.length, notes });
      } catch (err) {
        if (!controller.signal.aborted) setState({ phase: "error", message: (err as Error).message });
      }
    })();
    return () => controller.abort();
  }, [currentId]);

  if (state.phase === "loading")
    return (
      <Shell>
        <div className="pw-card pw-loading">
          <span className="pulse" />
          <div>
            <b>Loading the Lantern family</b>
            <p>Reading the root investigation, its branch records and each child from {apiOriginLabel()}.</p>
          </div>
        </div>
      </Shell>
    );
  if (state.phase === "error")
    return (
      <Shell>
        <div className="pw-card pw-error" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <b>The Lantern family could not be loaded</b>
            <p>{state.message}</p>
            <div className="pw-actions">
              <button className="outline-button" onClick={onBack}>
                Back to the investigation
              </button>
            </div>
          </div>
        </div>
      </Shell>
    );
  return (
    <>
      {(state.hidden > 0 || state.notes.length > 0) && (
        <div className="pw-notice" role="status">
          <Icon name="alert" size={13} />
          <span>
            {state.hidden > 0 ? `${state.hidden} more child investigation(s) are not drawn. ` : ""}
            {state.notes.join(" ")}
          </span>
        </div>
      )}
      <ConstellationView
        lanterns={state.lanterns}
        traces={state.traces}
        latestOf={(id) => (state.traces[id]?.events.length ?? 1) - 1}
        highlight={currentId}
        onOpen={onOpen}
        onOpenAt={onOpenAt}
        onBack={onBack}
        question={state.question}
        persisted
      />
    </>
  );
}
