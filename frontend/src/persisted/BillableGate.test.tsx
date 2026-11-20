import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAIN, fixtureFetch, raw } from "../test/fixtures";

// Force the billable flag ON for this file only. The backend is mocked: nothing real runs.
vi.mock("../api/config", async (orig) => {
  const mod = await orig<typeof import("../api/config")>();
  return { ...mod, API_CONFIG: { ...mod.API_CONFIG, allowBillableResearch: true } };
});
const { PersistedWorkspace } = await import("./PersistedWorkspace");

const CLAIM = "clm_195d970aad8a3285";
let posts: string[] = [];

beforeEach(() => {
  posts = [];
  window.history.replaceState(null, "", `/?mode=live&investigation=${MAIN}&node=${CLAIM}`);
  vi.stubGlobal(
    "fetch",
    fixtureFetch([], {
      handle: (url, init) => {
        if (init?.method !== "POST") return undefined;
        posts.push(new URL(url, "http://x").pathname);
        if (url.endsWith("/resume")) return new Response(JSON.stringify(raw(MAIN, "export")), { status: 200 });
        const body = JSON.parse(String(init.body));
        return new Response(
          JSON.stringify({ id: "branch_b", parent_investigation_id: MAIN, child_investigation_id: "inv_child_b", from_checkpoint_id: body.from_checkpoint_id, intervention_type: body.intervention_type, objective: body.objective, created_at: "2026-11-20T00:00:00Z" }),
          { status: 200 },
        );
      },
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Fork & Investigate with billing enabled", () => {
  it("requires an explicit authorisation before creating the branch and running one research step", async () => {
    render(<PersistedWorkspace render3D={() => <div />} />);
    fireEvent.click(await screen.findByRole("button", { name: /Challenge this claim/ }));
    const fork = (await screen.findByTestId("fork-investigate")) as HTMLButtonElement;
    expect(fork.disabled).toBe(false);

    fireEvent.click(fork); // first click only asks for confirmation
    expect(posts).toHaveLength(0);
    const confirm = screen.getByTestId("billable-confirm");
    expect(confirm.textContent).toMatch(/billable/);
    expect((screen.getByTestId("fork-investigate") as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(confirm.querySelector("input")!);
    fireEvent.click(screen.getByTestId("fork-investigate"));
    await screen.findByTestId("branch-created");
    expect(posts).toEqual([`/api/exploration/investigations/${MAIN}/branches`, "/api/exploration/branches/branch_b/resume"]);
    expect(screen.getByTestId("branch-created").textContent).toMatch(/research step run/);
  });
});
