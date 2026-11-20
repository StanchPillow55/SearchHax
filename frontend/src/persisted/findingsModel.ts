/*
 * Findings model (M5) built ONLY from persisted records: claims, evidence links, evidence
 * spans, documents, provenance, contradictions, unresolved questions and the recorded
 * convergence decision. Nothing is synthesized here.
 *
 * Three kinds of support are kept apart:
 *   - exact quote:   an evidence link whose quoted span was validated against the stored text
 *   - semantic only: the link supports the claim, but its quote did not validate
 *   - independent:   distinct recorded ORIGINS among supporting sources. A source whose origin
 *                    is unknown is never counted as independent; derivative sources that share
 *                    an origin group count once.
 */
import type { ExplorationExportT } from "../api/schemas";
import { GroundedAnswer, type GroundedAnswerT } from "../api/schemas";

export type ClaimStatusT = "supported" | "contradicted" | "insufficient" | "hypothesis";

export interface EvidenceRow {
  linkId: string;
  spanId: string;
  quote: string;
  stance: string;
  quoteValid: boolean;
  semantic: string;
  documentId: string | null;
  title: string;
  url: string;
  originKind: "original" | "derivative" | "unknown";
  originKey: string | null;
}

export interface Finding {
  /** First stored claim id in the group (used for "show in trace"). */
  claimId: string;
  /** Every stored claim record with this exact text and status (duplicates are grouped, not erased). */
  claimIds: string[];
  text: string;
  scope: string;
  status: ClaimStatusT;
  supporting: EvidenceRow[];
  contradicting: EvidenceRow[];
  other: EvidenceRow[];
  exactQuoteSupport: number;
  semanticOnlySupport: number;
  independentOrigins: number;
  supportingSources: number;
  unknownOriginSources: number;
  derivativeSources: number;
}

export interface Outcome {
  status: string;
  stopReason: string | null;
  decisionSource: string | null;
  rationale: string;
  verified: boolean;
  partial: boolean;
  headline: string;
}

export interface FindingsModel {
  question: string;
  outcome: Outcome;
  findings: Finding[];
  contradictions: ExplorationExportT["contradictions"];
  openQuestions: ExplorationExportT["unresolved_questions"];
  answer: GroundedAnswerT | null;
  answerInvalid: boolean;
  counts: Record<ClaimStatusT, number>;
  unlinkedClaims: number;
}

const ORDER: ClaimStatusT[] = ["supported", "contradicted", "insufficient", "hypothesis"];

export function outcomeOf(exp: ExplorationExportT): Outcome {
  const inv = exp.investigation;
  const stopReason = inv.stop_reason ?? null;
  const decisionSource = inv.decision_source ?? null;
  const verified = inv.status === "stopped" && stopReason === "evidence_sufficient" && decisionSource === "convergence";
  const partial = inv.status !== "stopped" || stopReason !== "evidence_sufficient";
  let headline: string;
  if (inv.status === "created") headline = "Not started: no research has run yet.";
  else if (inv.status === "blocked") headline = `Blocked before completing: ${inv.blocker ?? "see the recorded blocker"}. Partial result.`;
  else if (inv.status === "running") headline = "In progress: these are the findings recorded so far, not a conclusion.";
  else if (stopReason === "budget_exhausted") headline = "Partial result: the research budget ran out before the controller judged the evidence sufficient.";
  else if (stopReason === "unresolved_uncertainty") headline = "Stopped with unresolved uncertainty: open questions remain material.";
  else if (stopReason === "evidence_sufficient")
    headline =
      decisionSource === "convergence"
        ? "The convergence controller judged the evidence sufficient under its policy. This is a stopping decision, not proof."
        : "Stopped as sufficient by the fallback rule (the convergence controller was unavailable). Treat as partial.";
  else headline = `Stopped: ${stopReason?.replace(/_/g, " ") ?? "no reason recorded"}. Partial result.`;
  return { status: inv.status, stopReason, decisionSource, rationale: inv.decision_rationale ?? "", verified, partial, headline };
}

export function buildFindings(exp: ExplorationExportT): FindingsModel {
  const spans = new Map(exp.evidence_spans.map((s) => [s.id, s]));
  const docs = new Map(exp.documents.map((d) => [d.id, d]));
  const prov = new Map(exp.provenance.map((p) => [p.document_id, p]));

  const row = (link: ExplorationExportT["evidence_links"][number]): EvidenceRow => {
    const span = spans.get(link.evidence_span_id);
    const documentId = span?.document_id ?? null;
    const doc = documentId ? docs.get(documentId) : undefined;
    const p = documentId ? prov.get(documentId) : undefined;
    const originKind = (p?.origin_kind ?? "unknown") as EvidenceRow["originKind"];
    // A recorded origin identity: shared group, explicit origin id, or the document itself when it IS the original.
    const originKey = p?.shared_origin_group || p?.origin_id || (originKind === "original" && documentId ? `doc:${documentId}` : null);
    return {
      linkId: link.id,
      spanId: link.evidence_span_id,
      quote: span?.text ?? "",
      stance: link.stance,
      quoteValid: link.quote_valid,
      semantic: link.semantic_status,
      documentId,
      title: doc?.title ?? (documentId ? documentId : "Source not recorded"),
      url: doc?.canonical_url ?? "",
      originKind,
      originKey,
    };
  };

  const byClaim = new Map<string, EvidenceRow[]>();
  for (const link of exp.evidence_links) {
    const list = byClaim.get(link.claim_id) ?? [];
    list.push(row(link));
    byClaim.set(link.claim_id, list);
  }

  // Group stored claims that repeat the same text with the same status; keep every record id.
  const norm = (t: string) => t.toLowerCase().replace(/\s+/g, " ").trim();
  const groups = new Map<string, ExplorationExportT["claims"]>();
  for (const c of exp.claims) {
    const key = `${c.status}|${norm(c.text)}`;
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }

  const findings: Finding[] = [...groups.values()].map((group) => {
    const c = group[0];
    const rows = group.flatMap((g) => byClaim.get(g.id) ?? []);
    const supporting = rows.filter((r) => r.stance === "supports");
    const contradicting = rows.filter((r) => r.stance === "contradicts");
    const other = rows.filter((r) => r.stance !== "supports" && r.stance !== "contradicts");
    const supportDocs = new Map<string, EvidenceRow>();
    for (const r of supporting) if (r.documentId && !supportDocs.has(r.documentId)) supportDocs.set(r.documentId, r);
    const origins = new Set<string>();
    let unknown = 0;
    let derivative = 0;
    for (const r of supportDocs.values()) {
      if (r.originKey) origins.add(r.originKey);
      else unknown += 1;
      if (r.originKind === "derivative") derivative += 1;
    }
    return {
      claimId: c.id,
      claimIds: group.map((g) => g.id),
      text: c.text,
      scope: c.scope ?? "",
      status: c.status as ClaimStatusT,
      supporting,
      contradicting,
      other,
      exactQuoteSupport: supporting.filter((r) => r.quoteValid).length,
      semanticOnlySupport: supporting.filter((r) => !r.quoteValid).length,
      independentOrigins: origins.size,
      supportingSources: supportDocs.size,
      unknownOriginSources: unknown,
      derivativeSources: derivative,
    };
  });
  findings.sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));

  // Counts are of stored claim records, so they match the backend.
  const counts = { supported: 0, contradicted: 0, insufficient: 0, hypothesis: 0 } as Record<ClaimStatusT, number>;
  for (const c of exp.claims) counts[c.status as ClaimStatusT] = (counts[c.status as ClaimStatusT] ?? 0) + 1;

  const rawAnswer = (exp as Record<string, unknown>).answer;
  const parsed = rawAnswer == null ? null : GroundedAnswer.safeParse(rawAnswer);

  return {
    question: exp.investigation.question,
    outcome: outcomeOf(exp),
    findings,
    contradictions: exp.contradictions,
    openQuestions: exp.unresolved_questions,
    answer: parsed?.success ? parsed.data : null,
    answerInvalid: !!parsed && !parsed.success,
    counts,
    unlinkedClaims: exp.claims.filter((c) => !byClaim.has(c.id)).length,
  };
}
