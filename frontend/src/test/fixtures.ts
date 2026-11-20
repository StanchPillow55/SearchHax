import { readFileSync } from "node:fs";
import { join } from "node:path";

const dir = join(__dirname, "fixtures");
export const MAIN = "inv_93606fb27bb74f3c";
export const CHILD = "inv_c8b5e2eabdab485e";
export const OTHER = "inv_390477badbf24e65";
export const EMPTY = "inv_4f2b0308b2cf4c74";

export function raw(id: string, name: "export" | "trace" | "branches"): unknown {
  return JSON.parse(readFileSync(join(dir, id, `${name}.json`), "utf8"));
}

/** fetch stub that serves captured real responses by URL, and 404 for anything else. */
export function fixtureFetch(
  log: string[] = [],
  opts: { fail?: (url: string) => Response | undefined; handle?: (url: string, init?: RequestInit) => Response | undefined | Promise<Response | undefined> } = {},
) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    log.push(`${init?.method ?? "GET"} ${url}${init?.body ? ` ${init.body}` : ""}`);
    const forced = opts.fail?.(url);
    if (forced) return forced;
    const handled = await opts.handle?.(url, init);
    if (handled) return handled;
    const m = url.match(/\/api\/exploration\/investigations\/([^/?]+)(\/trace|\/branches)?$/);
    if (!m) return new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
    const [, id, sub] = m;
    const name = sub === "/trace" ? "trace" : sub === "/branches" ? "branches" : "export";
    try {
      return new Response(JSON.stringify(raw(decodeURIComponent(id), name)), { status: 200, headers: { "content-type": "application/json" } });
    } catch {
      return new Response(JSON.stringify({ detail: "investigation not found" }), { status: 404 });
    }
  };
}
