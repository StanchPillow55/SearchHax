/*
 * The URL is the source of truth for what persisted investigation (and selection) is open,
 * so a browser reload reopens the same record. Demo mode never writes these params.
 *   ?mode=live&investigation=inv_…&node=…&cp=…
 */
export type AppMode = "live" | "demo";

export interface UrlState {
  mode: AppMode;
  investigation: string | null;
  node: string | null;
  checkpoint: string | null;
}

const ID_RE = /^[A-Za-z0-9_:.-]{1,200}$/;
const clean = (v: string | null) => (v && ID_RE.test(v) ? v : null);

export function readUrlState(search = typeof window !== "undefined" ? window.location.search : ""): UrlState {
  const q = new URLSearchParams(search);
  const investigation = clean(q.get("investigation"));
  const mode: AppMode = q.get("mode") === "demo" ? "demo" : "live";
  return { mode, investigation: mode === "live" ? investigation : null, node: clean(q.get("node")), checkpoint: clean(q.get("cp")) };
}

export function writeUrlState(next: Partial<UrlState>, opts: { push?: boolean } = {}) {
  if (typeof window === "undefined") return;
  const cur = readUrlState();
  const merged = { ...cur, ...next };
  const q = new URLSearchParams();
  q.set("mode", merged.mode);
  if (merged.mode === "live") {
    if (merged.investigation) q.set("investigation", merged.investigation);
    if (merged.investigation && merged.node) q.set("node", merged.node);
    if (merged.investigation && merged.checkpoint) q.set("cp", merged.checkpoint);
  }
  const url = `${window.location.pathname}?${q.toString()}`;
  if (url === `${window.location.pathname}${window.location.search}`) return;
  if (opts.push) window.history.pushState(null, "", url);
  else window.history.replaceState(null, "", url);
}

const RECENT_KEY = "searchhax.recentInvestigations";

export function readRecent(): { id: string; question: string; status: string; openedAt: string }[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((r) => r && typeof r.id === "string" && ID_RE.test(r.id)).slice(0, 12) : [];
  } catch {
    return [];
  }
}

export function rememberRecent(entry: { id: string; question: string; status: string }) {
  try {
    const list = readRecent().filter((r) => r.id !== entry.id);
    list.unshift({ ...entry, openedAt: new Date().toISOString() });
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 12)));
  } catch {
    /* storage unavailable: recent list is a convenience only */
  }
}
