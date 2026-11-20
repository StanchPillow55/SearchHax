import { useEffect, useMemo, useState } from "react";
import { explorationClient } from "../api/client";
import type { ExplorationExportT } from "../api/schemas";
import { Icon, Tag } from "../shared";
import { diffLineage, type Side } from "./lineageDiff";

/** Live parent ↔ child comparison (M6). Loads the parent's stored export; diffs records only. */
export function LineageCompare({ child, question, parentId, onBack, onOpen }: { child: ExplorationExportT; question: string; parentId: string; onBack: () => void; onOpen: (id: string) => void }) {
  const [parent, setParent] = useState<{ phase: "loading" } | { phase: "ready"; exp: ExplorationExportT } | { phase: "error"; message: string }>({ phase: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    explorationClient
      .getInvestigation(parentId, controller.signal)
      .then((exp) => setParent({ phase: "ready", exp }))
      .catch((err) => !controller.signal.aborted && setParent({ phase: "error", message: (err as Error).message }));
    return () => controller.abort();
  }, [parentId]);
  const diff = useMemo(() => (parent.phase === "ready" ? diffLineage(parent.exp, child) : null), [parent, child]);

  return (
    <main className="app-main fx-screen" data-testid="lineage-compare">
      <header className="fx-head">
        <button className="icon-button" onClick={onBack} aria-label="Back to the investigation">
          <Icon name="back" size={16} />
        </button>
        <div>
          <small>Compare with parent · recorded differences</small>
          <h1>{question}</h1>
          {typeof child.investigation.metadata?.objective === "string" && child.investigation.metadata.objective && (
            <p className="fx-note">
              <Tag tone="violet">Branch objective</Tag> {String(child.investigation.metadata.objective)}
            </p>
          )}
        </div>
      </header>
      <div className="fx-body">
        {parent.phase === "loading" && <p className="fx-empty">Loading the parent investigation {parentId}…</p>}
        {parent.phase === "error" && (
          <p className="ix-compose-error" role="alert">
            The parent investigation {parentId} could not be loaded ({parent.message}). Nothing is compared.
          </p>
        )}
        {diff && (
          <>
            <section className="lc-sides">
              <SideCard title="Parent" s={diff.parent} onOpen={() => onOpen(diff.parent.id)} />
              <SideCard title="Child" s={diff.child} />
            </section>
            {diff.child.searches === 0 && (
              <p className="fx-note" data-testid="lc-not-run">
                The child has not run any research, so everything it holds was inherited from the parent checkpoint. Differences below are only what
                the checkpoint left out.
              </p>
            )}
            <section>
              <h2>Claims</h2>
              <p className="fx-note">
                {diff.claims.inheritedUnchanged} unchanged from the parent · {diff.claims.added.length} new in the child · {diff.claims.changed.length} with a different
                status · {diff.claims.onlyInParent.length} only in the parent.
              </p>
              <ul className="fx-list" data-testid="lc-claims">
                {diff.claims.changed.map((c) => (
                  <li key={`c:${c.text}`}>
                    <Tag tone="amber">Status changed</Tag> {c.text} <span className="fx-meta">({c.parentStatus} → {c.childStatus})</span>
                  </li>
                ))}
                {diff.claims.added.map((c) => (
                  <li key={`a:${c.text}`}>
                    <Tag tone="teal">New</Tag> {c.text} <span className="fx-meta">({c.childStatus})</span>
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h2>Sources</h2>
              <p className="fx-note">
                {diff.sources.shared} shared · {diff.sources.added.length} new in the child · {diff.sources.onlyInParent} only in the parent.
              </p>
              {diff.sources.added.length > 0 && (
                <ul className="fx-list" data-testid="lc-sources">
                  {diff.sources.added.map((s) => (
                    <li key={s.url}>
                      {s.title || s.url}{" "}
                      <a href={s.url} target="_blank" rel="noreferrer noopener">
                        {s.url}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section>
              <h2>Open questions</h2>
              <p className="fx-note">
                {diff.questions.stillOpen} still open in both · {diff.questions.added.length} new in the child · {diff.questions.notOpenInChild.length} open in
                the parent but not in the child (dropped or answered — the record does not say which).
              </p>
              <ul className="fx-list">
                {diff.questions.added.map((q) => (
                  <li key={`qa:${q}`}>
                    <Tag tone="teal">New</Tag> {q}
                  </li>
                ))}
                {diff.questions.notOpenInChild.map((q) => (
                  <li key={`qn:${q}`}>
                    <Tag tone="gray">Not open in child</Tag> {q}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h2>Disagreements</h2>
              <p className="fx-note">
                Parent recorded {diff.contradictions.parent}, child recorded {diff.contradictions.child} ({diff.contradictions.added} not in the parent).
              </p>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function SideCard({ title, s, onOpen }: { title: string; s: Side; onOpen?: () => void }) {
  return (
    <div className="fx-outcome lc-side" data-testid={`lc-${title.toLowerCase()}`}>
      <div className="fx-claim-head">
        <b>
          {title} <code className="fx-meta">{s.id}</code>
        </b>
        {onOpen && (
          <button className="link-button" onClick={onOpen}>
            Open
          </button>
        )}
      </div>
      <p className="fx-meta">
        {s.status}
        {s.stopReason ? ` · ${s.stopReason.replace(/_/g, " ")}` : ""}
        {s.decisionSource ? ` · decided by ${s.decisionSource}` : ""}
      </p>
      {s.rationale && <p className="fx-rationale">{s.rationale}</p>}
      <ul className="fx-counts">
        <li>
          <b>{s.searches}</b> searches
        </li>
        <li>
          <b>{s.sources}</b> sources
        </li>
        <li>
          <b>{s.claims}</b> claims{s.claimRecords !== s.claims ? ` (${s.claimRecords} records)` : ""}
        </li>
        <li>
          <b>{s.openQuestions}</b> open questions{s.questionRecords !== s.openQuestions ? ` (${s.questionRecords} records)` : ""}
        </li>
      </ul>
    </div>
  );
}
