import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHILD, MAIN, fixtureFetch, raw } from "../test/fixtures";
import { PersistedWorkspace } from "./PersistedWorkspace";

const CLAIM = "clm_195d970aad8a3285";
const C2 = "cp_c92da0e30bac4932";
const go = (search: string) => window.history.replaceState(null, "", `/${search}`);
const workspace = () => render(<PersistedWorkspace render3D={() => <div />} />);

let calls: string[] = [];
let posts: { url: string; body: Record<string, unknown> }[] = [];
let postResponse: () => Response;
const newBranch = (body: Record<string, unknown>) => ({
  id: "branch_test",
  parent_investigation_id: MAIN,
  child_investigation_id: "inv_child_test",
  from_checkpoint_id: body.from_checkpoint_id,
  intervention_type: body.intervention_type,
  objective: body.objective ?? "",
  created_at: "2026-11-20T00:00:00Z",
  constraints: body.constraints ?? {},
});

beforeEach(() => {
  calls = [];
  posts = [];
  postResponse = () => new Response("unused", { status: 500 });
  window.localStorage.clear();
  vi.stubGlobal(
    "fetch",
    fixtureFetch(calls, {
      handle: async (url, init) => {
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body ?? "{}"));
          posts.push({ url, body });
          if (url.endsWith("/resume")) return new Response(JSON.stringify({ detail: "must not be called" }), { status: 500 });
          await new Promise((r) => setTimeout(r, 30));
          const res = postResponse();
          return res.status === 200 ? new Response(JSON.stringify(newBranch(body)), { status: 200 }) : res;
        }
        if (url.includes("/investigations?")) {
          return new Response(
            JSON.stringify({
              items: [
                { id: MAIN, question: "How do NVIDIA's investments…", status: "stopped", stop_reason: "budget_exhausted", created_at: "2026-11-15T02:04:17Z", updated_at: "2026-11-15T02:04:45Z", event_count: 11, checkpoint_count: 2 },
                { id: CHILD, question: "How do NVIDIA's investments…", status: "created", created_at: "2026-11-15T02:05:22Z", updated_at: "2026-11-15T02:05:22Z", parent_investigation_id: MAIN, intervention_type: "fork", from_checkpoint_id: C2, event_count: 1, checkpoint_count: 1 },
              ],
              total: 2,
              limit: 100,
              offset: 0,
            }),
            { status: 200 },
          );
        }
        return undefined;
      },
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function openComposerForClaim() {
  go(`?mode=live&investigation=${MAIN}&node=${CLAIM}`);
  workspace();
  await screen.findByTestId("research-question");
  fireEvent.click(await screen.findByRole("button", { name: /Challenge this claim/ }));
  return screen.findByTestId("save-lantern");
}

describe("Save Lantern creates a grounded branch", () => {
  it("POSTs the checkpoint, intervention, budget and attachments, then shows the child", async () => {
    postResponse = () => new Response("ok", { status: 200 });
    const save = await openComposerForClaim();
    fireEvent.click(save);
    await screen.findByTestId("branch-created");
    expect(posts).toHaveLength(1);
    const { url, body } = posts[0];
    expect(url).toBe(`/api/exploration/investigations/${MAIN}/branches`);
    expect(body).toMatchObject({ from_checkpoint_id: C2, intervention_type: "challenge_evidence", constraints: { max_searches: 1 }, attached_claim_ids: [CLAIM] });
    expect(String(body.objective)).toContain("NVIDIA has invested $2 billion in CoreWeave");
    const exp = raw(MAIN, "export") as { checkpoints: { id: string; state_json: { snapshot: { documents: { id: string }[] } } }[] };
    const snapDocs = new Set(exp.checkpoints.find((c) => c.id === C2)!.state_json.snapshot.documents.map((d) => d.id));
    for (const id of body.attached_source_ids as string[]) expect(snapDocs.has(id)).toBe(true);
    expect(screen.getByTestId("branch-created").textContent).toContain("inv_child_test");
    expect(posts.some((p) => p.url.endsWith("/resume"))).toBe(false);
    // the parent was re-read afterwards (silent refresh), not mutated locally
    await waitFor(() => expect(calls.filter((c) => c === `GET /api/exploration/investigations/${MAIN}/branches`).length).toBeGreaterThan(1));
  });

  it("ignores a double submit while the first request is in flight", async () => {
    postResponse = () => new Response("ok", { status: 200 });
    const save = await openComposerForClaim();
    act(() => {
      fireEvent.click(save);
      fireEvent.click(save);
    });
    await screen.findByTestId("branch-created");
    expect(posts).toHaveLength(1);
  });

  it("shows a backend validation error without crashing and keeps the composer open", async () => {
    postResponse = () => new Response(JSON.stringify({ detail: "attachments not recorded at checkpoint" }), { status: 422 });
    const save = await openComposerForClaim();
    fireEvent.click(save);
    expect((await screen.findByTestId("branch-error")).textContent).toMatch(/422/);
    expect(screen.getByTestId("save-lantern")).toBeTruthy();
    expect(screen.queryByTestId("branch-created")).toBeNull();
  });

  it("Continue keeps the original question: empty objective, continue intervention", async () => {
    postResponse = () => new Response("ok", { status: 200 });
    go(`?mode=live&investigation=${MAIN}&node=${C2}`);
    workspace();
    fireEvent.click(await screen.findByRole("button", { name: /Continue from here/ }));
    expect(await screen.findByTestId("continue-note")).toBeTruthy();
    fireEvent.click(screen.getByTestId("save-lantern"));
    await screen.findByTestId("branch-created");
    expect(posts[0].body).toMatchObject({ intervention_type: "continue", objective: "", from_checkpoint_id: C2 });
  });
});

describe("challenge grounding (contract 1.1.0)", () => {
  async function challengeWithoutClaim(objective: string) {
    go(`?mode=live&investigation=${MAIN}&node=${C2}`);
    workspace();
    fireEvent.click(await screen.findByRole("button", { name: /Fork Lantern from/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Challenge claim" }));
    fireEvent.change(screen.getByTestId("branch-objective"), { target: { value: objective } });
    return screen.getByTestId("save-lantern") as HTMLButtonElement;
  }

  it("refuses a vague challenge with no selected claim before sending anything", async () => {
    const save = await challengeWithoutClaim("Is this true?");
    expect(save.disabled).toBe(true);
    expect(screen.getByTestId("challenge-grounding").textContent).toMatch(/not\s+specific enough/);
    fireEvent.click(save);
    expect(posts).toHaveLength(0);
  });

  it("allows a challenge whose objective names what to test", async () => {
    postResponse = () => new Response("ok", { status: 200 });
    const save = await challengeWithoutClaim("NVIDIA CoreWeave $2 billion stake size");
    expect(save.disabled).toBe(false);
    expect(screen.queryByTestId("challenge-grounding")).toBeNull();
    fireEvent.click(save);
    await screen.findByTestId("branch-created");
    expect(posts[0].body).toMatchObject({ intervention_type: "challenge_evidence", attached_claim_ids: [] });
  });

  it("allows a vague objective when a claim is selected (the claim grounds it)", async () => {
    const save = (await openComposerForClaim()) as HTMLButtonElement;
    fireEvent.change(screen.getByTestId("branch-objective"), { target: { value: "Is this true?" } });
    expect(save.disabled).toBe(false);
  });
});

describe("billable research is gated", () => {
  it("Fork & Investigate is disabled with a reason when the billable flag is off", async () => {
    await openComposerForClaim();
    const btn = screen.getByTestId("fork-investigate") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.title).toMatch(/VITE_ALLOW_BILLABLE_RESEARCH/);
  });

  it("an unstarted child cannot start research when billing is off", async () => {
    go(`?mode=live&investigation=${CHILD}`);
    workspace();
    const start = (await screen.findByTestId("start-research")) as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    fireEvent.click(start);
    expect(posts).toHaveLength(0);
  });
});

describe("listing and family navigation", () => {
  it("lists stored investigations from the API, marking children", async () => {
    go(`?mode=live`);
    workspace();
    const rows = await screen.findAllByTestId("investigation-row");
    expect(rows).toHaveLength(2);
    expect(rows[1].textContent).toContain(`child of ${MAIN}`);
  });

  it("falls back to ID entry when the backend has no list endpoint", async () => {
    vi.stubGlobal("fetch", fixtureFetch([]));
    go(`?mode=live`);
    workspace();
    expect(await screen.findByText(/List unavailable/)).toBeTruthy();
  });

  it("the live Constellation shows the recorded family from the API", async () => {
    go(`?mode=live&investigation=${CHILD}`);
    workspace();
    await screen.findByTestId("research-question");
    fireEvent.click(screen.getByTestId("open-constellation"));
    await screen.findByTestId("explore-parent");
    expect(screen.getByTestId("data-origin").textContent).toMatch(/Persisted/);
    // root resolved by walking the child's recorded parent link
    expect(calls.some((c) => c.endsWith(`/investigations/${MAIN}/branches`))).toBe(true);
    expect(screen.getAllByText(/Recorded child|Created · no steps recorded|Stopped/).length).toBeGreaterThan(0);
  });
});
