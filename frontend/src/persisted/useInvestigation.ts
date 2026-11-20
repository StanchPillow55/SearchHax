import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, explorationClient, type ExplorationClient } from "../api/client";
import { adaptInvestigation, type AdaptedInvestigation } from "./adapter";

export type LoadState =
  | { phase: "idle" }
  | { phase: "loading"; id: string }
  | { phase: "ready"; id: string; data: AdaptedInvestigation; loadedAt: string; warnings: string[] }
  | { phase: "error"; id: string; error: ApiError | Error };

/**
 * Loads one persisted investigation. Changing `id` aborts the previous request and clears
 * the previous result first, so data from two investigations is never shown together.
 */
export function useInvestigation(id: string | null, client: ExplorationClient = explorationClient) {
  const [state, setState] = useState<LoadState>({ phase: "idle" });
  const [nonce, setNonce] = useState(0);
  const current = useRef<string | null>(null);
  const silent = useRef(false);

  useEffect(() => {
    current.current = id;
    if (!id) {
      setState({ phase: "idle" });
      return;
    }
    const controller = new AbortController();
    const quiet = silent.current;
    silent.current = false;
    if (!quiet) setState({ phase: "loading", id });
    (async () => {
      try {
        const [exp, trace] = await Promise.all([client.getInvestigation(id, controller.signal), client.getTrace(id, controller.signal)]);
        const warnings: string[] = [];
        let branches: Awaited<ReturnType<ExplorationClient["getBranches"]>> = [];
        try {
          branches = await client.getBranches(id, controller.signal);
        } catch (err) {
          if (controller.signal.aborted) return;
          warnings.push(`Branch records could not be loaded (${(err as Error).message}); child investigations are not shown.`);
        }
        if (controller.signal.aborted || current.current !== id) return;
        if (exp.investigation.id !== id || trace.investigation_id !== id) {
          throw new ApiError("contract", `Backend returned records for a different investigation than ${id}`);
        }
        const data = adaptInvestigation(exp, trace, branches);
        setState({ phase: "ready", id, data, loadedAt: new Date().toISOString(), warnings });
      } catch (err) {
        if (controller.signal.aborted || current.current !== id) return;
        setState({ phase: "error", id, error: err as Error });
      }
    })();
    return () => controller.abort();
  }, [id, nonce, client]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  /** Re-read the same investigation without showing a loading screen (e.g. after creating a branch). */
  const refresh = useCallback(() => {
    silent.current = true;
    setNonce((n) => n + 1);
  }, []);
  return { state, retry, refresh };
}
