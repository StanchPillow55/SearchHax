import type { z } from "zod";
import { API_CONFIG, apiUrl } from "./config";
import {
  BranchList,
  BranchRecord,
  ExplorationExport,
  InvestigationList,
  InvestigationTrace,
  type BranchRecordT,
  type CreateBranchBody,
  type ExplorationExportT,
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

  private async request<S extends z.ZodTypeAny>(method: "GET" | "POST", path: string, schema: S, body?: unknown, signal?: AbortSignal, timeoutMs = API_CONFIG.timeoutMs): Promise<z.infer<S>> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
    const onAbort = () => controller.abort("aborted");
    signal?.addEventListener("abort", onAbort);
    let res: Response;
    try {
      res = await this.fetchImpl(apiUrl(path), {
        method,
        headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
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

  /** Creates a child investigation from a persisted checkpoint. Local only: no search, fetch or LLM call. */
  createBranch(parentId: string, body: CreateBranchBody): Promise<BranchRecordT> {
    return this.request("POST", `/investigations/${encodeURIComponent(parentId)}/branches`, BranchRecord, body);
  }

  /**
   * Runs one research step on a branch's child investigation. BILLABLE: performs real
   * searches, fetches and LLM calls. Refuses unless VITE_ALLOW_BILLABLE_RESEARCH=true and
   * the caller passes an explicit confirmation.
   */
  resumeBranch(branchId: string, confirmation: { confirmedBillable: true }): Promise<ExplorationExportT> {
    if (!API_CONFIG.allowBillableResearch || confirmation?.confirmedBillable !== true) {
      return Promise.reject(new ApiError("http", "Billable research is disabled in this build (VITE_ALLOW_BILLABLE_RESEARCH is not true)."));
    }
    return this.request("POST", `/branches/${encodeURIComponent(branchId)}/resume`, ExplorationExport, {}, undefined, 300_000);
  }
}

export const explorationClient = new ExplorationClient();
