/*
 * Parent ↔ child comparison (M6) computed from the two stored exports. Nothing is inferred:
 * items are matched by stable record content (claim text + status, canonical URL, question
 * text), and each side's stopping decision is shown as recorded.
 */
import type { ExplorationExportT } from "../api/schemas";

const norm = (t: string) => t.toLowerCase().replace(/\s+/g, " ").trim();

export interface ClaimDiff {
  text: string;
  parentStatus: string | null;
  childStatus: string | null;
}
export interface Side {
  id: string;
  status: string;
  stopReason: string | null;
  decisionSource: string | null;
  rationale: string;
  searches: number;
  claims: number;
  sources: number;
  openQuestions: number;
}
export interface LineageDiff {
  parent: Side;
  child: Side;
  claims: { added: ClaimDiff[]; changed: ClaimDiff[]; inheritedUnchanged: number; onlyInParent: ClaimDiff[] };
  sources: { added: { url: string; title: string }[]; shared: number; onlyInParent: number };
  questions: { notOpenInChild: string[]; added: string[]; stillOpen: number };
  contradictions: { added: number; parent: number; child: number };
}

function side(e: ExplorationExportT): Side {
  const inv = e.investigation;
  return {
    id: inv.id,
    status: inv.status,
    stopReason: inv.stop_reason ?? null,
    decisionSource: inv.decision_source ?? null,
    rationale: inv.decision_rationale ?? "",
    searches: inv.usage.search_calls,
    claims: e.claims.length,
    sources: e.documents.length,
    openQuestions: e.unresolved_questions.length,
  };
}

export function diffLineage(parent: ExplorationExportT, child: ExplorationExportT): LineageDiff {
  // Claims: keyed by text. A status change on the same text is a "changed" finding.
  const pClaims = new Map<string, string>();
  for (const c of parent.claims) pClaims.set(norm(c.text), c.status);
  const cClaims = new Map<string, { text: string; status: string }>();
  for (const c of child.claims) cClaims.set(norm(c.text), { text: c.text, status: c.status });
  const added: ClaimDiff[] = [];
  const changed: ClaimDiff[] = [];
  let unchanged = 0;
  for (const [k, c] of cClaims) {
    const ps = pClaims.get(k);
    if (ps === undefined) added.push({ text: c.text, parentStatus: null, childStatus: c.status });
    else if (ps !== c.status) changed.push({ text: c.text, parentStatus: ps, childStatus: c.status });
    else unchanged += 1;
  }
  const onlyInParent: ClaimDiff[] = parent.claims
    .filter((c) => !cClaims.has(norm(c.text)))
    .map((c) => ({ text: c.text, parentStatus: c.status, childStatus: null }));

  const pUrls = new Set(parent.documents.map((d) => d.canonical_url));
  const cUrls = new Set(child.documents.map((d) => d.canonical_url));
  const addedSources = child.documents.filter((d) => !pUrls.has(d.canonical_url)).map((d) => ({ url: d.canonical_url, title: d.title }));

  const pQ = new Set(parent.unresolved_questions.map((q) => norm(q.text)));
  const cQ = new Set(child.unresolved_questions.map((q) => norm(q.text)));
  const notOpenInChild = parent.unresolved_questions.filter((q) => !cQ.has(norm(q.text))).map((q) => q.text);
  const addedQ = child.unresolved_questions.filter((q) => !pQ.has(norm(q.text))).map((q) => q.text);

  const pX = new Set(parent.contradictions.map((x) => norm(`${x.subject_name}|${x.predicate}|${x.conflicting_object}`)));
  const addedX = child.contradictions.filter((x) => !pX.has(norm(`${x.subject_name}|${x.predicate}|${x.conflicting_object}`))).length;

  return {
    parent: side(parent),
    child: side(child),
    claims: { added, changed, inheritedUnchanged: unchanged, onlyInParent },
    sources: { added: addedSources, shared: [...cUrls].filter((u) => pUrls.has(u)).length, onlyInParent: [...pUrls].filter((u) => !cUrls.has(u)).length },
    questions: { notOpenInChild, added: addedQ, stillOpen: [...cQ].filter((q) => pQ.has(q)).length },
    contradictions: { added: addedX, parent: parent.contradictions.length, child: child.contradictions.length },
  };
}
