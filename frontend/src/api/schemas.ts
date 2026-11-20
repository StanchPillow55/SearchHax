/*
 * Runtime-validated mirrors of shared/contracts.py (CONTRACT_VERSION 1.0.0).
 *
 * The backend uses extra="ignore" and adds fields compatibly, so every object here is
 * .passthrough(): unknown fields are kept, required fields are enforced. Only fields
 * the frontend reads are declared. A response that fails these checks is reported as a
 * contract error instead of being rendered.
 */
import { z } from "zod";

const obj = <T extends z.ZodRawShape>(shape: T) => z.object(shape).passthrough();
const nullableStr = z.string().nullable().optional();
const anyRecord = z.record(z.string(), z.unknown());

export const VerificationStatus = z.enum(["supported", "contradicted", "insufficient", "hypothesis"]);
export const StopReason = z.enum([
  "evidence_sufficient",
  "low_expected_value",
  "no_useful_actions",
  "budget_exhausted",
  "unresolved_uncertainty",
]);
export const InvestigationStatus = z.enum(["created", "running", "stopped", "blocked"]);
export const OriginKind = z.enum(["original", "derivative", "unknown"]);

export const AttentionComponents = obj({ R: z.number(), G: z.number(), D: z.number(), F: z.number(), score: z.number() });

export const InvestigationBudget = obj({
  max_searches: z.number(),
  max_fetched_urls: z.number(),
  max_llm_calls: z.number(),
  searches_used: z.number(),
  urls_fetched: z.number(),
  llm_calls_used: z.number(),
});

export const UsageMetrics = obj({
  search_calls: z.number().default(0),
  fetch_calls: z.number().default(0),
  llm_calls: z.number().default(0),
  urls_fetched: z.number().default(0),
  providers_used: z.array(z.string()).default([]),
  dry_run: z.boolean().default(false),
});

export const Investigation = obj({
  id: z.string(),
  question: z.string(),
  budget: InvestigationBudget,
  status: InvestigationStatus,
  stop_reason: StopReason.nullable().optional(),
  decision_source: z.enum(["convergence", "fallback"]).nullable().optional(),
  decision_rationale: z.string().default(""),
  usage: UsageMetrics,
  created_at: z.string(),
  updated_at: z.string(),
  live_extraction_blocked: z.boolean().default(false),
  blocker: nullableStr,
  metadata: anyRecord.default({}),
});

export const Document = obj({
  id: z.string(),
  canonical_url: z.string(),
  title: z.string(),
  origin_id: nullableStr,
  providers: z.array(z.string()).default([]),
});

export const DocumentVersion = obj({
  id: z.string(),
  document_id: z.string(),
  content_hash: z.string(),
  fetched_at: z.string(),
  content: z.string(),
  publish_date: nullableStr,
});

export const EvidenceSpan = obj({
  id: z.string(),
  version_id: z.string(),
  document_id: z.string(),
  text: z.string(),
  start: z.number(),
  end: z.number(),
  content_hash: z.string(),
  attention: AttentionComponents.nullable().optional(),
  quote_valid: z.boolean().default(false),
});

export const Claim = obj({
  id: z.string(),
  text: z.string(),
  scope: z.string().default(""),
  status: VerificationStatus,
  document_id: nullableStr,
  span_id: nullableStr,
});

export const Relationship = obj({
  id: z.string(),
  predicate: z.string(),
  claim_id: nullableStr,
  status: VerificationStatus,
  document_id: nullableStr,
  subject_name: z.string().default(""),
  object_name: z.string().default(""),
  source_document_ids: z.array(z.string()).default([]),
});

export const EvidenceLink = obj({
  id: z.string(),
  claim_id: z.string(),
  relationship_id: nullableStr,
  evidence_span_id: z.string(),
  stance: z.enum(["supports", "contradicts", "mentions", "insufficient"]),
  quote_valid: z.boolean(),
  semantic_status: VerificationStatus,
});

export const SourceProvenance = obj({
  id: z.string(),
  document_id: z.string(),
  provider: nullableStr,
  providers: z.array(z.string()).default([]),
  origin_url: nullableStr,
  origin_id: nullableStr,
  origin_kind: OriginKind.default("unknown"),
  cited_origin_ids: z.array(z.string()).default([]),
  shared_origin_group: nullableStr,
  notes: z.string().default(""),
});

export const UnresolvedQuestion = obj({
  id: z.string(),
  text: z.string(),
  importance: z.number().optional(),
  missing_evidence: z.number().optional(),
  kind: z.string().default("gap"),
});

export const EvidenceCandidate = obj({
  id: z.string(),
  document_id: nullableStr,
  url: z.string(),
  title: z.string(),
  snippet: z.string(),
  providers: z.array(z.string()).default([]),
  attention: AttentionComponents,
  knowledge_value: obj({ score: z.number() }).nullable().optional(),
  publish_date: nullableStr,
});

export const Contradiction = obj({
  id: z.string(),
  subject_name: z.string(),
  predicate: z.string(),
  supported_object: z.string(),
  conflicting_object: z.string(),
  original_document_id: z.string(),
  conflicting_document_id: z.string(),
  detail: z.string(),
});

export const Checkpoint = obj({
  id: z.string(),
  investigation_id: z.string(),
  step: z.number(),
  state_json: anyRecord.default({}),
  stop_reason: StopReason.nullable().optional(),
  created_at: z.string(),
  summary: z.string().default(""),
});

export const ConvergenceDecision = obj({
  stop: z.boolean().default(false),
  stop_reason: StopReason.nullable().optional(),
  rationale: z.string(),
  decision_source: z.enum(["convergence", "fallback"]),
});

export const ExplorationExport = obj({
  contract_version: z.string(),
  investigation: Investigation,
  documents: z.array(Document).default([]),
  document_versions: z.array(DocumentVersion).default([]),
  evidence_spans: z.array(EvidenceSpan).default([]),
  claims: z.array(Claim).default([]),
  relationships: z.array(Relationship).default([]),
  evidence_links: z.array(EvidenceLink).default([]),
  provenance: z.array(SourceProvenance).default([]),
  unresolved_questions: z.array(UnresolvedQuestion).default([]),
  candidates: z.array(EvidenceCandidate).default([]),
  contradictions: z.array(Contradiction).default([]),
  checkpoints: z.array(Checkpoint).default([]),
  decision: ConvergenceDecision.nullable().optional(),
});

export const TraceStage = z.enum(["search", "retrieval", "ranking", "extraction", "convergence", "checkpoint", "ingest", "blocked"]);

export const TraceEvent = obj({
  id: z.string(),
  investigation_id: z.string(),
  sequence: z.number(),
  // Unknown future stages are kept (as strings) and rendered generically, not dropped.
  stage: z.string(),
  created_at: z.string(),
  summary: z.string(),
  payload: anyRecord.default({}),
  checkpoint_id: nullableStr,
});

export const TraceNode = obj({
  id: z.string(),
  type: z.string(),
  label: z.string(),
  stage: z.string(),
  event_id: z.string(),
  epistemic_status: z.string().default("unknown"),
  payload: anyRecord.default({}),
});

export const InvestigationTrace = obj({
  investigation_id: z.string(),
  question: z.string(),
  incomplete: z.boolean(),
  incomplete_reason: nullableStr,
  events: z.array(TraceEvent).default([]),
  nodes: z.array(TraceNode).default([]),
  edges: z.array(obj({ id: z.string(), source: z.string(), target: z.string(), kind: z.string() })).default([]),
  artifact_notes: z.array(anyRecord).default([]),
  search_event_count: z.number().default(0),
  fetch_event_count: z.number().default(0),
  llm_event_count: z.number().default(0),
  usage_search_calls: z.number().default(0),
  usage_fetch_calls: z.number().default(0),
  usage_llm_calls: z.number().default(0),
  parent_investigation_id: nullableStr,
  branch_id: nullableStr,
  intervention_type: nullableStr,
  from_checkpoint_id: nullableStr,
  // Additive (1.0.x): recorded with a branch at creation time. Absent on older backends.
  branch_objective: nullableStr,
  attached_claims: z.array(obj({ id: z.string(), text: z.string().default(""), status: z.string().nullable().optional() })).default([]),
  attached_sources: z.array(obj({ id: z.string(), title: z.string().default(""), url: z.string().default("") })).default([]),
});

export const BranchRecord = obj({
  id: z.string(),
  parent_investigation_id: z.string(),
  child_investigation_id: z.string(),
  from_checkpoint_id: z.string(),
  intervention_type: z.string(),
  objective: z.string().default(""),
  created_at: z.string(),
});
export const BranchList = z.array(BranchRecord);

export const InvestigationSummary = obj({
  id: z.string(),
  question: z.string(),
  status: InvestigationStatus,
  stop_reason: StopReason.nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  parent_investigation_id: nullableStr,
  branch_id: nullableStr,
  intervention_type: nullableStr,
  from_checkpoint_id: nullableStr,
  event_count: z.number().default(0),
  checkpoint_count: z.number().default(0),
});
export const InvestigationList = obj({ items: z.array(InvestigationSummary), total: z.number(), limit: z.number(), offset: z.number() });
export type InvestigationSummaryT = z.infer<typeof InvestigationSummary>;

export const InterventionType = z.enum(["fork", "challenge_evidence", "continue"]);
export interface CreateBranchBody {
  from_checkpoint_id: string;
  objective: string;
  intervention_type: z.infer<typeof InterventionType>;
  constraints?: { max_searches?: number | null; max_fetched_urls?: number | null; max_llm_calls?: number | null };
  attached_claim_ids?: string[];
  attached_source_ids?: string[];
}

/** One recorded Focus policy coordinate (checkpoint.state_json.policy_space[i]). */
export const PolicyPoint = obj({
  evidence_id: z.string(),
  document_id: nullableStr,
  url: z.string().default(""),
  title: z.string().default(""),
  passage: z.string().default(""),
  intent_alignment: z.number().min(0).max(1),
  novelty: z.number().min(0).max(1),
  unresolved_alignment: z.number().min(0).max(1),
  action: z.enum(["consider", "investigate", "archive"]),
  reason: z.string().default(""),
  coordinate_source: z.string().default(""),
});

export type ExplorationExportT = z.infer<typeof ExplorationExport>;
export type InvestigationTraceT = z.infer<typeof InvestigationTrace>;
export type TraceEventT = z.infer<typeof TraceEvent>;
export type CheckpointT = z.infer<typeof Checkpoint>;
export type BranchRecordT = z.infer<typeof BranchRecord>;
export type PolicyPointT = z.infer<typeof PolicyPoint>;
