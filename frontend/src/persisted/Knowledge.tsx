import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, explorationClient, newIdempotencyKey } from "../api/client";
import type { KnowledgeAssertionBody, KnowledgeGraphT } from "../api/schemas";
import { Icon, Tag } from "../shared";

type Node = KnowledgeGraphT["nodes"][number];
type State = KnowledgeAssertionBody["epistemic_state"];

const GROUPS: { state: string; title: string; tone: string; blurb: string }[] = [
  { state: "known", title: "Known", tone: "teal", blurb: "Things the profile lists as prior knowledge, or that you confirmed." },
  { state: "interested", title: "Interested", tone: "blue", blurb: "Topics declared on the profile." },
  { state: "frontier", title: "Frontier", tone: "violet", blurb: "Listed as unresolved on the profile. Not a computed gap." },
  { state: "uncertain", title: "Uncertain", tone: "amber", blurb: "Recorded contradictions in this investigation." },
  { state: "encountered", title: "Encountered", tone: "gray", blurb: "Sources presented in this investigation. Encountered is not known." },
];

const BASIS: Record<string, string> = {
  profile_declared: "declared on the profile",
  profile_prior: "profile prior (not sourced evidence)",
  profile_unresolved: "listed as unresolved on the profile",
  presented_in_investigation: "presented in this investigation",
  contradiction: "recorded contradiction",
  user_confirmation: "your explicit assertion",
  inferred: "inferred",
  retrieved: "retrieved",
};

/**
 * Personal knowledge for one investigation (M8). Shows only what the backend records, with the
 * basis of every node. Corrections are stored as explicit user assertions; nothing is promoted
 * to "known" because a source was retrieved.
 */
export function Knowledge({ investigationId, question, onBack, onInvestigate }: { investigationId: string; question: string; onBack: () => void; onInvestigate: (question: string, profileId: string | null) => void }) {
  const [graph, setGraph] = useState<{ phase: "loading" } | { phase: "ready"; g: KnowledgeGraphT } | { phase: "error"; message: string }>({ phase: "loading" });
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pendingRef = useRef(false);

  const load = useCallback(
    (signal?: AbortSignal) =>
      explorationClient
        .getKnowledgeGraph(investigationId, signal)
        .then((g) => setGraph({ phase: "ready", g }))
        .catch((err) => !signal?.aborted && setGraph({ phase: "error", message: (err as Error).message })),
    [investigationId],
  );
  useEffect(() => {
    const c = new AbortController();
    void load(c.signal);
    return () => c.abort();
  }, [load]);

  const assert = async (node: Node, state: State) => {
    if (graph.phase !== "ready" || !graph.g.profile_id || pendingRef.current) return;
    pendingRef.current = true;
    setPending(node.id);
    setError(null);
    try {
      const g = await explorationClient.addKnowledgeAssertion(
        { profile_id: graph.g.profile_id, investigation_id: investigationId, subject: node.label, text: node.label, epistemic_state: state, basis: "user_confirmation" },
        newIdempotencyKey(),
      );
      setGraph({ phase: "ready", g });
    } catch (err) {
      setError(err instanceof ApiError ? `${err.message}${err.status ? ` (HTTP ${err.status})` : ""}` : (err as Error).message);
    } finally {
      pendingRef.current = false;
      setPending(null);
    }
  };

  return (
    <main className="app-main fx-screen" data-testid="knowledge">
      <header className="fx-head">
        <button className="icon-button" onClick={onBack} aria-label="Back to the investigation">
          <Icon name="back" size={16} />
        </button>
        <div>
          <small>Personal knowledge · recorded profile and assertions</small>
          <h1>{question}</h1>
          {graph.phase === "ready" && (
            <p className="fx-note" data-testid="knowledge-profile">
              {graph.g.profile_id ? (
                <>
                  Profile <code>{graph.g.profile_id}</code>
                </>
              ) : (
                "No research profile is attached to this investigation. Corrections need a profile, so they are unavailable here."
              )}
            </p>
          )}
        </div>
      </header>
      <div className="fx-body">
        {graph.phase === "loading" && <p className="fx-empty">Loading the knowledge view from the exploration API…</p>}
        {graph.phase === "error" && (
          <p className="ix-compose-error" role="alert">
            The knowledge view could not be loaded ({graph.message}).
          </p>
        )}
        {error && (
          <p className="ix-compose-error" role="alert" data-testid="knowledge-error">
            {error}
          </p>
        )}
        {graph.phase === "ready" && (
          <>
            {graph.g.notes.length > 0 && (
              <ul className="fx-list kn-notes">
                {graph.g.notes.map((n) => (
                  <li key={n} className="fx-note">
                    {n}
                  </li>
                ))}
              </ul>
            )}
            {GROUPS.map((grp) => {
              const nodes = graph.g.nodes.filter((n) => n.epistemic_state === grp.state);
              return (
                <section key={grp.state} data-testid={`knowledge-${grp.state}`}>
                  <h2>
                    {grp.title} <span className="fx-meta">({nodes.length})</span>
                  </h2>
                  <p className="fx-note">{grp.blurb}</p>
                  {nodes.length === 0 ? (
                    <p className="fx-empty">None recorded.</p>
                  ) : (
                    <ul className="fx-list kn-nodes">
                      {nodes.map((n) => (
                        <li key={n.id} className="kn-node" data-testid="knowledge-node">
                          <div className="fx-claim-head">
                            <span>
                              {n.label} {n.basis === "user_confirmation" && <Tag tone="teal">confirmed by you</Tag>}
                            </span>
                            {graph.g.profile_id && (
                              <span className="kn-actions">
                                {grp.state === "frontier" && (
                                  <button className="link-button" onClick={() => onInvestigate(n.label, graph.phase === "ready" ? graph.g.profile_id ?? null : null)} data-testid="investigate-frontier">
                                    Investigate…
                                  </button>
                                )}
                                {grp.state !== "known" && (
                                  <button className="link-button" disabled={pending !== null} onClick={() => void assert(n, "known")}>
                                    I know this
                                  </button>
                                )}
                                {grp.state === "known" && (
                                  <button className="link-button" disabled={pending !== null} onClick={() => void assert(n, "uncertain")}>
                                    I'm not sure about this
                                  </button>
                                )}
                                {grp.state !== "interested" && grp.state !== "known" && (
                                  <button className="link-button" disabled={pending !== null} onClick={() => void assert(n, "interested")}>
                                    Interested
                                  </button>
                                )}
                              </span>
                            )}
                          </div>
                          <p className="fx-meta">
                            Basis: {BASIS[n.basis] ?? n.basis}
                            {n.note ? ` — ${n.note}` : ""}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </>
        )}
      </div>
    </main>
  );
}
