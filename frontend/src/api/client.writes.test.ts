import { describe, expect, it } from "vitest";
import { API_CONFIG } from "./config";
import { ExplorationClient } from "./client";
import { MAIN, raw } from "../test/fixtures";

const branch = {
  id: "branch_new",
  parent_investigation_id: MAIN,
  child_investigation_id: "inv_child_new",
  from_checkpoint_id: "cp_c92da0e30bac4932",
  intervention_type: "challenge_evidence",
  objective: "x",
  created_at: "2026-11-20T00:00:00Z",
  constraints: {},
};

describe("ExplorationClient writes", () => {
  it("createBranch POSTs JSON to the parent's branches route and validates the record", async () => {
    const seen: { url: string; init?: RequestInit }[] = [];
    const c = new ExplorationClient(async (u, init) => {
      seen.push({ url: String(u), init });
      return new Response(JSON.stringify(branch), { status: 200 });
    });
    const res = await c.createBranch(MAIN, { from_checkpoint_id: branch.from_checkpoint_id, objective: "x", intervention_type: "challenge_evidence", attached_claim_ids: ["clm_1"] });
    expect(res.child_investigation_id).toBe("inv_child_new");
    expect(seen[0].url).toBe(`/api/exploration/investigations/${MAIN}/branches`);
    expect(seen[0].init?.method).toBe("POST");
    expect((seen[0].init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(seen[0].init?.body))).toMatchObject({ intervention_type: "challenge_evidence", attached_claim_ids: ["clm_1"] });
  });

  it("surfaces backend validation errors (422) as http errors", async () => {
    const c = new ExplorationClient(async () => new Response(JSON.stringify({ detail: "attachments not recorded" }), { status: 422 }));
    await expect(c.createBranch(MAIN, { from_checkpoint_id: "cp", objective: "", intervention_type: "fork" })).rejects.toMatchObject({ kind: "http", status: 422 });
  });

  it("resumeBranch refuses without the billable flag and never touches the network", async () => {
    expect(API_CONFIG.allowBillableResearch).toBe(false);
    let called = 0;
    const c = new ExplorationClient(async () => {
      called++;
      return new Response("{}");
    });
    await expect(c.resumeBranch("branch_new", { confirmedBillable: true })).rejects.toThrow(/Billable research is disabled/);
    expect(called).toBe(0);
  });

  it("createInvestigation sends profile_from_investigation_id only when a profile source is given", async () => {
    const bodies: unknown[] = [];
    const inv = (raw(MAIN, "export") as { investigation: unknown }).investigation;
    const c = new ExplorationClient(async (_u, init) => {
      bodies.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify(inv), { status: 200 });
    });
    await c.createInvestigation("advanced packaging supply", undefined, "k1", MAIN);
    await c.createInvestigation("advanced packaging supply", undefined, "k2");
    expect(bodies[0]).toEqual({ question: "advanced packaging supply", profile_from_investigation_id: MAIN });
    expect(bodies[1]).toEqual({ question: "advanced packaging supply" });
  });

  it("listInvestigations validates the listing", async () => {
    const c = new ExplorationClient(async () =>
      new Response(JSON.stringify({ items: [{ id: MAIN, question: "q", status: "stopped", stop_reason: "budget_exhausted", created_at: "t", updated_at: "t", event_count: 11, checkpoint_count: 2 }], total: 1, limit: 50, offset: 0 }), { status: 200 }),
    );
    const res = await c.listInvestigations();
    expect(res.items[0]).toMatchObject({ id: MAIN, event_count: 11 });
    expect(res.items[0].parent_investigation_id ?? null).toBeNull();
  });
});
