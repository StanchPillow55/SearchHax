/*
 * Investigation trace model.
 *
 * Three concepts are kept deliberately separate:
 *  - TraceEvent      what the agent recorded doing (search issued, sources returned, …)
 *  - Checkpoint      a persisted snapshot that may (or may not) be resumable / forkable
 *  - Decision node   a recorded convergence decision (continue / stop …)
 *
 * Everything in this prototype is illustrative. Nothing here is real backend output.
 */

export type PolicyAction = "consider" | "investigate" | "archive";

export type NodeKind =
  | "intent"
  | "inherited"
  | "round"
  | "query"
  | "group"
  | "doc"
  | "passage"
  | "claim"
  | "contradiction"
  | "relation"
  | "question"
  | "decision"
  | "checkpoint"
  | "fork"
  | "pending";

export type EdgeKind =
  | "order" // recorded event order only — no causal claim
  | "retrieved" // returned by the same query
  | "supports"
  | "contradicts"
  | "sharedOrigin"
  | "prompted" // follow-up search prompted by an unresolved question
  | "considered" // evidence referenced by a recorded decision
  | "raised" // evidence that raised an open question
  | "fork";

export type ClaimStatus = "supported" | "qualified" | "mixed" | "contested" | "regional" | "unverified";
export type QuestionStatus = "open" | "partial" | "resolved";
export type DecisionOutcome =
  | "continue"
  | "investigate"
  | "stop-sufficient"
  | "stop-budget"
  | "stop-uncertain"
  | "awaiting";
export type Origin = "primary" | "secondary" | "derivative";

export type Coords = { intent: number; novelty: number; openq: number };

export interface TraceNode {
  id: string;
  kind: NodeKind;
  label: string;
  sub?: string;
  round: number;
  /** event seq at which this node first appears */
  revealAt: number;
  /** disclosure parent: doc → group, passage → doc */
  parent?: string;
  // query
  provider?: string;
  // doc
  publisher?: string;
  origin?: Origin;
  docType?: string;
  // passage
  text?: string;
  policy?: PolicyAction;
  coords?: Coords;
  coordNote?: string;
  evId?: string;
  relevance?: string;
  // claim / question status history
  history?: { at: number; status: ClaimStatus | QuestionStatus; note: string }[];
  independent?: number;
  // decision
  outcome?: DecisionOutcome;
  did?: string;
  rationale?: { label: string; value: string }[];
  // checkpoint
  checkpointId?: string;
  // fork
  lanternId?: string;
  // free description
  body?: string;
}

export interface TraceEdge {
  id: string;
  from: string;
  to: string;
  kind: EdgeKind;
  label?: string;
}

export type EventKind =
  | "intent"
  | "inherit"
  | "plan"
  | "search"
  | "retrieve"
  | "extract"
  | "evaluate"
  | "relate"
  | "question"
  | "decide"
  | "checkpoint"
  | "pending";

export interface TraceEvent {
  seq: number;
  kind: EventKind;
  round: number;
  label: string;
  detail: string;
  /** node to select / focus when the user lands on this event */
  focus?: string;
}

export interface Checkpoint {
  id: string;
  short: string;
  label: string;
  seq: number;
  nodeId: string;
  persisted: true;
  resumable: boolean;
  forkable: boolean;
  notResumableReason?: string;
  status: string;
  summary: string;
  frontier: string[] | null; // null = not recorded at this checkpoint
  recordsClaims: boolean;
  recordsCoords: boolean;
  why?: string;
}

export interface Trace {
  lanternId: string;
  nodes: TraceNode[];
  edges: TraceEdge[];
  events: TraceEvent[];
  checkpoints: Checkpoint[];
  rounds: { n: number; title: string; phase: string }[];
}

export type LanternStatus =
  | "stopped-uncertain"
  | "researching"
  | "completed"
  | "awaiting"
  | "not-started";

export interface Lantern {
  id: string;
  title: string;
  objective: string;
  status: LanternStatus;
  parentId?: string;
  fromCheckpoint?: string; // checkpoint id in parent trace
  attachedClaim?: string; // node id in parent trace
  attachedSources?: string[];
  userCreated?: boolean;
  createdMode?: "saved" | "investigate";
  slot?: number;
}

export type Selection = { id: string } | null;

export interface ViewState {
  cursor: number; // event seq currently shown
  snapshot: string | null; // loaded checkpoint id
  selected: string | null;
  expanded: string[]; // expanded group / doc ids
  collapsedRounds: number[];
  zoom: number;
  pan: { x: number; y: number };
  fitted: boolean;
  granularity: "event" | "round";
  composer: ComposerDraft | null;
  focusNonce: number;
  focusIds: string[];
}

export interface ComposerDraft {
  intent: "challenge" | "confirm" | "uncertainty" | "custom";
  claimId: string | null;
  sourceIds: string[];
  checkpointId: string | null;
  title: string;
  objective: string;
}
