import type { z } from "zod";
import { API_CONFIG, apiUrl } from "./config";
import {
  BranchList,
  BranchRecord,
  ExplorationExport,
  Investigation,
  InvestigationList,
  InvestigationTrace,
  KnowledgeGraph,
  type KnowledgeAssertionBody,
  type KnowledgeGraphT,
  type BranchRecordT,
  type CreateBranchBody,
  type ExplorationExportT,
  type InvestigationT,
  type InvestigationTraceT,
} from "./schemas";

export type ApiErrorKind = "network" | "timeout" | "not_found" | "http" | "contract" | "aborted";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status?: number,
    public path?: string,
    public issues?: string[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type FetchLike = typeof fetch;

/**
 * Typed, validated, read-only client for the FastAPI exploration service.
 * Reads are GET. The only writes are createBranch (local) and the gated, billable resumeBranch.
 */
export class ExplorationClient {
  constructor(private fetchImpl: FetchLike = (...a) => fetch(...a)) {}

  private get<S extends z.ZodTypeAny>(path: string, schema: S, signal?: AbortSignal): Promise<z.infer<S>> {
    return this.request("GET", path, schema, undefined, signal);
  }

  private async request<S extends z.ZodTypeAny>(
    method: "GET" | "POST",
    path: string,
    schema: S,
    body?: unknown,
    signal?: AbortSignal,
    timeoutMs = API_CONFIG.timeoutMs,
    idempotencyKey?: string,
  ): Promise<z.infer<S>> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
    const onAbort = () => controller.abort("aborted");
    signal?.addEventListener("abort", onAbort);
    let res: Response;
    try {
      res = await this.fetchImpl(apiUrl(path), {
        method,
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      if (controller.signal.aborted) {
        const reason = controller.signal.reason === "timeout" ? "timeout" : "aborted";
        throw new ApiError(reason, reason === "timeout" ? `Request timed out after ${timeoutMs} ms` : "Request was cancelled", undefined, path);
      }
      throw new ApiError("network", `Backend unreachable: ${(err as Error).message}`, undefined, path);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    }
    if (res.status === 404) throw new ApiError("not_found", "Not found on the backend", 404, path);
    if (!res.ok) {
      let detail = "";
      try {
        detail = (await res.text()).slice(0, 300);
      } catch {
        /* ignore */
      }
      throw new ApiError("http", `Backend returned HTTP ${res.status}${detail ? `: ${detail}` : ""}`, res.status, path);
    }
    let parsedBody: unknown;
    try {
      parsedBody = await res.json();
    } catch {
      throw new ApiError("contract", "Response was not valid JSON", res.status, path);
    }
    const parsed = schema.safeParse(parsedBody);
    if (!parsed.success) {
      const issues = parsed.error.issues.slice(0, 8).map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`);
      throw new ApiError("contract", "Response did not match the expected contract", res.status, path, issues);
    }
    return parsed.data;
  }

  getInvestigation(id: string, signal?: AbortSignal): Promise<ExplorationExportT> {
    return this.get(`/investigations/${encodeURIComponent(id)}`, ExplorationExport, signal);
  }
  getTrace(id: string, signal?: AbortSignal): Promise<InvestigationTraceT> {
    return this.get(`/investigations/${encodeURIComponent(id)}/trace`, InvestigationTrace, signal);
  }
  getBranches(id: string, signal?: AbortSignal): Promise<BranchRecordT[]> {
    return this.get(`/investigations/${encodeURIComponent(id)}/branches`, BranchList, signal);
  }
  listInvestigations(limit = 50, offset = 0, signal?: AbortSignal) {
    return this.get(`/investigations?limit=${limit}&offset=${offset}`, InvestigationList, signal);
  }

  /**
   * Creates a child investigation from a persisted checkpoint. Local only: no search, fetch or LLM call.
   * Pass the same idempotencyKey when retrying the same user action; the backend then returns the
   * first result instead of creating a second child.
   */
  createBranch(parentId: string, body: CreateBranchBody, idempotencyKey?: string): Promise<BranchRecordT> {
    return this.request("POST", `/investigations/${encodeURIComponent(parentId)}/branches`, BranchRecord, body, undefined, undefined, idempotencyKey);
  }

  /** The profile/knowledge view for an investigation (profile interests, priors, encountered sources, user assertions). */
  getKnowledgeGraph(investigationId: string, signal?: AbortSignal): Promise<KnowledgeGraphT> {
    return this.get(`/profile/knowledge-graph?investigation_id=${encodeURIComponent(investigationId)}`, KnowledgeGraph, signal);
  }

  /** Records an explicit user assertion about their own knowledge. Local only. Returns the updated graph. */
  addKnowledgeAssertion(body: KnowledgeAssertionBody, idempotencyKey?: string): Promise<KnowledgeGraphT> {
    return this.request("POST", "/profile/knowledge-assertions", KnowledgeGraph, body, undefined, undefined, idempotencyKey);
  }

  /** Stores a new research question. Local only: nothing is searched until a (billable) step runs. */
  createInvestigation(question: string, budget: { max_searches: number; max_fetched_urls: number; max_llm_calls: number } | undefined, idempotencyKey?: string): Promise<InvestigationT> {
    return this.request("POST", "/investigations", Investigation, { question, ...(budget ? { budget } : {}) }, undefined, undefined, idempotencyKey);
  }

  /** Runs one research step on a root investigation. BILLABLE; same gate as resumeBranch. */
  stepInvestigation(id: string, confirmation: { confirmedBillable: true }, idempotencyKey?: string): Promise<ExplorationExportT> {
    if (!API_CONFIG.allowBillableResearch || confirmation?.confirmedBillable !== true) {
      return Promise.reject(new ApiError("http", "Billable research is disabled in this build (VITE_ALLOW_BILLABLE_RESEARCH is not true)."));
    }
    return this.request("POST", `/investigations/${encodeURIComponent(id)}/step`, ExplorationExport, {}, undefined, 300_000, idempotencyKey);
  }

  /**
   * Runs one research step on a branch's child investigation. BILLABLE: performs real
   * searches, fetches and LLM calls. Refuses unless VITE_ALLOW_BILLABLE_RESEARCH=true and
   * the caller passes an explicit confirmation.
   */
  resumeBranch(branchId: string, confirmation: { confirmedBillable: true }, idempotencyKey?: string): Promise<ExplorationExportT> {
    if (!API_CONFIG.allowBillableResearch || confirmation?.confirmedBillable !== true) {
      return Promise.reject(new ApiError("http", "Billable research is disabled in this build (VITE_ALLOW_BILLABLE_RESEARCH is not true)."));
    }
    return this.request("POST", `/branches/${encodeURIComponent(branchId)}/resume`, ExplorationExport, {}, undefined, 300_000, idempotencyKey);
  }
}

export const explorationClient = new ExplorationClient();

/** Random key for the Idempotency-Key header. */
export function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
