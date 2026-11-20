import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { EMPTY, MAIN, OTHER, fixtureFetch, raw } from "../test/fixtures";
import { PersistedWorkspace } from "./PersistedWorkspace";

type Exp = { investigation: { question: string }; documents: { id: string; title: string; canonical_url: string }[] };
const mainExp = raw(MAIN, "export") as Exp;
const otherExp = raw(OTHER, "export") as Exp;
const DOC = "doc_a0d452123b0ca0d5";

let calls: string[] = [];
const go = (search: string) => window.history.replaceState(null, "", `/${search}`);
const workspace = () => render(<PersistedWorkspace render3D={() => <div data-testid="space" />} />);

beforeEach(() => {
  calls = [];
  vi.stubGlobal("fetch", fixtureFetch(calls));
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Persisted workspace: real stored investigation", () => {
  it("loads the recorded question, status and data origin for the investigation in the URL", async () => {
    go(`?mode=live&investigation=${MAIN}`);
    workspace();
    expect(screen.getByTestId("pw-loading")).toBeTruthy();
    expect((await screen.findByTestId("research-question")).textContent).toBe(mainExp.investigation.question);
    expect(screen.getByTestId("investigation-status").textContent).toMatch(/budget exhausted/i);
    expect(screen.getByTestId("data-origin").textContent).toMatch(/Persisted/);
    expect(screen.queryByText(/Simulated trace/)).toBeNull();
    expect(calls.every((c) => c.startsWith("GET "))).toBe(true);
    expect(calls.some((c) => c.endsWith(`/investigations/${MAIN}/trace`))).toBe(true);
  });

  it("restores a selected source from the URL and shows its real provenance", async () => {
    go(`?mode=live&investigation=${MAIN}&node=${DOC}`);
    workspace();
    const doc = mainExp.documents.find((d) => d.id === DOC)!;
    await screen.findByText(doc.canonical_url);
    const refs = screen.getAllByTestId("record-ref").map((r) => r.textContent);
    expect(refs.some((t) => t?.includes(`documents · ${DOC}`))).toBe(true);
  });

  it("restores a persisted checkpoint snapshot after reload and shows its recorded state", async () => {
    go(`?mode=live&investigation=${MAIN}&cp=cp_4c05d11bbb4c4856`);
    workspace();
    expect(await screen.findByText(/Checkpoint snapshot loaded · C1/)).toBeTruthy();
    expect(screen.getByText(/Recorded snapshot · step 1/)).toBeTruthy();
    expect(screen.getByText(/Event 5 \/ 11/)).toBeTruthy();
  });

  it("does not restore a checkpoint that does not belong to this investigation", async () => {
    go(`?mode=live&investigation=${MAIN}&cp=cp_not_here`);
    workspace();
    expect(await screen.findByText(/is not part of inv_93606fb27bb74f3c/)).toBeTruthy();
    expect(screen.queryByText(/Checkpoint snapshot loaded/)).toBeNull();
  });

  it("switching investigations replaces all evidence instead of mixing it", async () => {
    go(`?mode=live&investigation=${MAIN}`);
    workspace();
    await screen.findByText(mainExp.investigation.question, { selector: "h1" });
    act(() => {
      go(`?mode=live&investigation=${OTHER}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => expect(screen.getByTestId("research-question").textContent).toBe(otherExp.investigation.question));
    const otherIds = new Set(otherExp.documents.map((d) => d.id));
    for (const d of mainExp.documents.filter((x) => !otherIds.has(x.id))) {
      expect(screen.queryByText(d.title)).toBeNull();
    }
    expect(window.location.search).toContain(OTHER);
  });
});

describe("Persisted workspace: loading, empty and error states", () => {
  it("shows not-found without crashing", async () => {
    go(`?mode=live&investigation=inv_missing`);
    workspace();
    expect((await screen.findByTestId("pw-error")).dataset.kind).toBe("not_found");
  });

  it("shows an unreachable-backend error with retry", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new TypeError("Failed to fetch");
    });
    go(`?mode=live&investigation=${MAIN}`);
    workspace();
    expect((await screen.findByTestId("pw-error")).dataset.kind).toBe("network");
    expect(screen.getByText("Retry")).toBeTruthy();
  });

  it("refuses to render a response that breaks the contract", async () => {
    vi.stubGlobal(
      "fetch",
      fixtureFetch([], { fail: (url) => (url.endsWith("/trace") ? new Response(JSON.stringify({ investigation_id: MAIN }), { status: 200 }) : undefined) }),
    );
    go(`?mode=live&investigation=${MAIN}`);
    workspace();
    expect((await screen.findByTestId("pw-error")).dataset.kind).toBe("contract");
    expect(screen.queryByTestId("research-question")).toBeNull();
  });

  it("keeps working when branch records fail, with a warning", async () => {
    vi.stubGlobal("fetch", fixtureFetch([], { fail: (url) => (url.endsWith("/branches") ? new Response("down", { status: 500 }) : undefined) }));
    go(`?mode=live&investigation=${MAIN}`);
    workspace();
    expect(await screen.findByText(/Branch records could not be loaded/)).toBeTruthy();
    expect(screen.getByTestId("research-question").textContent).toBe(mainExp.investigation.question);
  });

  it("shows an empty state for an investigation with no recorded events", async () => {
    go(`?mode=live&investigation=${EMPTY}`);
    workspace();
    expect(await screen.findByTestId("pw-empty")).toBeTruthy();
    expect(screen.getByText(/No investigation events were recorded/)).toBeTruthy();
  });
});

describe("Demo and live data never mix", () => {
  it("demo mode is labelled and makes no backend requests", async () => {
    go(`?mode=demo`);
    render(<App />);
    expect(screen.getByTestId("demo-ribbon").textContent).toMatch(/simulated/i);
    await new Promise((r) => setTimeout(r, 20));
    expect(calls).toHaveLength(0);
  });

  it("live mode shows no demo ribbon and no simulated trace", async () => {
    go(`?mode=live&investigation=${MAIN}`);
    render(<App />);
    await screen.findByTestId("research-question");
    expect(screen.queryByTestId("demo-ribbon")).toBeNull();
    expect(screen.queryByText(/Simulated trace/)).toBeNull();
    expect(screen.queryByText(/illustrative/i)).toBeNull();
  });
});
