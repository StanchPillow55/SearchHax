import { useMemo, useState } from "react";
import type { ExplorationExportT } from "../api/schemas";
import { Icon, Tag } from "../shared";
import { buildFindings, type ClaimStatusT, type EvidenceRow, type Finding } from "./findingsModel";

const STATUS: Record<ClaimStatusT, { label: string; tone: string; blurb: string }> = {
  supported: { label: "Supported", tone: "teal", blurb: "Recorded evidence supports the claim." },
  contradicted: { label: "Contradicted", tone: "coral", blurb: "Recorded evidence contradicts the claim." },
  insufficient: { label: "Insufficient evidence", tone: "amber", blurb: "Evidence was found but does not settle the claim." },
  hypothesis: { label: "Hypothesis", tone: "gray", blurb: "Proposed, not yet tested against evidence." },
};

/**
 * Findings for a persisted investigation (M5). Everything shown is a recorded record; the only
 * prose not taken from a record is the fixed explanatory copy. A stored cited answer is shown
 * separately and labelled as a synthesis.
 */
export function Findings({ exp, onBack, onShowInTrace }: { exp: ExplorationExportT; onBack: () => void; onShowInTrace: (recordId: string) => void }) {
  const model = useMemo(() => buildFindings(exp), [exp]);
  const [filter, setFilter] = useState<ClaimStatusT | "all">("all");
  const shown = model.findings.filter((f) => filter === "all" || f.status === filter);
  const o = model.outcome;
  return (
    <main className="app-main fx-screen" data-testid="findings">
      <header className="fx-head">
        <button className="icon-button" onClick={onBack} aria-label="Back to the investigation">
          <Icon name="back" size={16} />
        </button>
        <div>
          <small>Findings · from recorded evidence</small>
          <h1 data-testid="findings-question">{model.question}</h1>
        </div>
      </header>

      <div className="fx-body">
        <section className={`fx-outcome ${o.verified ? "ok" : "partial"}`} data-testid="findings-outcome">
          <Tag tone={o.verified ? "teal" : "amber"}>{o.verified ? "Controller: evidence sufficient" : "Partial / not verified"}</Tag>
          <p className="fx-headline">{o.headline}</p>
          {o.rationale && (
            <p className="fx-rationale">
              <b>Recorded rationale{o.decisionSource ? ` (${o.decisionSource})` : ""}:</b> {o.rationale}
            </p>
          )}
          <ul className="fx-counts">
            {(Object.keys(STATUS) as ClaimStatusT[]).map((k) => (
              <li key={k}>
                <b>{model.counts[k]}</b> {STATUS[k].label.toLowerCase()}
              </li>
            ))}
            <li>
              <b>{model.contradictions.length}</b> recorded contradiction{model.contradictions.length === 1 ? "" : "s"}
            </li>
            <li>
              <b>{model.openQuestions.length}</b> open question{model.openQuestions.length === 1 ? "" : "s"}
            </li>
          </ul>
        </section>

        {model.answer && (
          <section className="fx-answer" data-testid="findings-answer">
            <h2>Cited summary</h2>
            <p className="fx-note">
              Synthesized{model.answer.model ? ` by ${model.answer.model}` : ""} from this investigation's recorded evidence. It explains the evidence; it does not
              verify anything new. Check each citation.
            </p>
            {model.answer.blocked ? (
              <p className="fx-note">Summary was blocked: {model.answer.blocker ?? "no reason recorded"}.</p>
            ) : (
              model.answer.markdown.split(/\n{2,}/).map((para, i) => <p key={i}>{para}</p>)
            )}
            {model.answer.citations.length > 0 && (
              <ol className="fx-citations">
                {model.answer.citations.map((c) => (
                  <li key={c.marker}>
                    <b>[{c.marker}]</b> {c.title || c.document_id || "untitled"} {c.url && <a href={c.url} target="_blank" rel="noreferrer noopener">{host(c.url)}</a>}
                    {c.quote && <q>{c.quote}</q>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}
        {model.answerInvalid && <p className="fx-note">A stored summary exists but did not match the expected contract, so it is not shown.</p>}

        <section>
          <div className="fx-section-head">
            <h2>Claims</h2>
            <div className="fx-filter" role="group" aria-label="Filter claims by status">
              {(["all", "supported", "contradicted", "insufficient", "hypothesis"] as const).map((k) => (
                <button key={k} className={filter === k ? "active" : ""} onClick={() => setFilter(k)} aria-pressed={filter === k}>
                  {k === "all" ? `All (${model.findings.length})` : `${STATUS[k].label} (${model.findings.filter((f) => f.status === k).length})`}
                </button>
              ))}
            </div>
          </div>
          {model.findings.length === 0 && <p className="fx-empty">No claims were extracted in this investigation, so there are no findings to show.</p>}
          {model.unlinkedClaims > 0 && (
            <p className="fx-note">
              {model.unlinkedClaims} claim{model.unlinkedClaims === 1 ? " has" : "s have"} no recorded evidence link. They are listed, but nothing supports them in this record.
            </p>
          )}
          <ol className="fx-claims">
            {shown.map((f) => (
              <ClaimCard key={f.claimId} f={f} onShow={() => onShowInTrace(f.claimId)} />
            ))}
          </ol>
        </section>

        <section>
          <h2>Contradictions</h2>
          {model.contradictions.length === 0 ? (
            <p className="fx-empty">No contradictions were recorded.</p>
          ) : (
            <ul className="fx-list" data-testid="findings-contradictions">
              {model.contradictions.map((c) => (
                <li key={c.id}>
                  <b>
                    {c.subject_name} · {c.predicate}
                  </b>
                  : “{c.supported_object}” vs “{c.conflicting_object}”<p className="fx-note">{c.detail}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2>Still open</h2>
          {model.openQuestions.length === 0 ? (
            <p className="fx-empty">No open questions were recorded.</p>
          ) : (
            <ul className="fx-list" data-testid="findings-open">
              {model.openQuestions.map((q) => (
                <li key={q.id}>
                  {q.text} <span className="fx-meta">{q.kind}</span>
                  {q.recordIds.length > 1 && (
                    <p className="fx-note" data-testid="open-question-repeats">
                      Recorded as {q.recordIds.length} separate question records ({q.recordIds.join(", ")}). Repetition is not extra importance.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}

function ClaimCard({ f, onShow }: { f: Finding; onShow: () => void }) {
  const meta = STATUS[f.status] ?? { label: f.status, tone: "gray", blurb: "" };
  return (
    <li className="fx-claim" data-testid="finding" data-status={f.status}>
      <div className="fx-claim-head">
        <Tag tone={meta.tone}>{meta.label}</Tag>
        <button className="link-button" onClick={onShow}>
          Show in trace
        </button>
      </div>
      <p className="fx-claim-text">{f.text}</p>
      {f.claimIds.length > 1 && (
        <p className="fx-meta" data-testid="finding-duplicates">
          Recorded as {f.claimIds.length} separate claim records ({f.claimIds.join(", ")}). Repetition is not extra support.
        </p>
      )}
      {f.scope && <p className="fx-meta">Scope: {f.scope}</p>}
      <ul className="fx-support" aria-label="How this claim is supported">
        <li title="Links whose quoted text was validated against the stored page">
          <b>{f.exactQuoteSupport}</b> exact-quote support
        </li>
        <li title="Links that support the claim but whose quote did not validate">
          <b>{f.semanticOnlySupport}</b> semantic-only support
        </li>
        <li title="Distinct recorded origins among supporting sources. Unknown origins are not counted.">
          <b>{f.independentOrigins}</b> independent origin{f.independentOrigins === 1 ? "" : "s"} of {f.supportingSources} source{f.supportingSources === 1 ? "" : "s"}
        </li>
        {f.unknownOriginSources > 0 && (
          <li className="warn">
            <b>{f.unknownOriginSources}</b> with unknown origin (not counted as independent)
          </li>
        )}
        {f.derivativeSources > 0 && (
          <li>
            <b>{f.derivativeSources}</b> derivative (repeats another source)
          </li>
        )}
      </ul>
      {[...f.supporting, ...f.contradicting, ...f.other].length > 0 && (
        <details>
          <summary>Evidence ({f.supporting.length + f.contradicting.length + f.other.length})</summary>
          <ul className="fx-evidence">
            {[...f.supporting, ...f.contradicting, ...f.other].map((r) => (
              <EvidenceItem key={r.linkId} r={r} />
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

function EvidenceItem({ r }: { r: EvidenceRow }) {
  return (
    <li>
      <div className="fx-ev-meta">
        <Tag tone={r.stance === "supports" ? "teal" : r.stance === "contradicts" ? "coral" : "gray"}>{r.stance}</Tag>
        <Tag tone={r.quoteValid ? "teal" : "amber"}>{r.quoteValid ? "quote validated" : "quote not validated"}</Tag>
        <span className="fx-meta">origin: {r.originKind}</span>
      </div>
      {r.quote ? <q>{r.quote}</q> : <p className="fx-note">The quoted span is not in this record.</p>}
      <p className="fx-meta">
        {r.title}
        {r.url && (
          <>
            {" · "}
            <a href={r.url} target="_blank" rel="noreferrer noopener">
              {host(r.url)}
            </a>
          </>
        )}
      </p>
    </li>
  );
}

function host(url: string) {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}
