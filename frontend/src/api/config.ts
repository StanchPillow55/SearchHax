/** Centralised API configuration. All values come from Vite environment variables. */
const env = import.meta.env as Record<string, string | undefined>;

export const API_CONFIG = {
  /** Empty string = same origin; in dev Vite proxies /api to the FastAPI service. */
  baseUrl: (env.VITE_API_BASE_URL ?? "").replace(/\/+$/, ""),
  timeoutMs: Number(env.VITE_API_TIMEOUT_MS ?? 20000) || 20000,
  prefix: "/api/exploration",
  /**
   * Resuming a branch runs real research (search, fetch, LLM calls) and may cost money.
   * It is OFF unless VITE_ALLOW_BILLABLE_RESEARCH is exactly "true".
   */
  allowBillableResearch: env.VITE_ALLOW_BILLABLE_RESEARCH === "true",
};

export function apiUrl(path: string) {
  return `${API_CONFIG.baseUrl}${API_CONFIG.prefix}${path}`;
}

/** Human-readable description of where data is loaded from (shown in the UI as provenance). */
export function apiOriginLabel() {
  return API_CONFIG.baseUrl || `${typeof window !== "undefined" ? window.location.origin : ""} (proxied)`;
}
