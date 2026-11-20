import { describe, expect, it } from "vitest";
import { ApiError, ExplorationClient } from "./client";
import { CHILD, EMPTY, MAIN, OTHER, fixtureFetch } from "../test/fixtures";

describe("ExplorationClient parses real backend responses", () => {
  const client = new ExplorationClient(fixtureFetch());

  it.each([MAIN, CHILD, OTHER, EMPTY])("parses export, trace and branches for %s", async (id) => {
    const exp = await client.getInvestigation(id);
    const trace = await client.getTrace(id);
    const branches = await client.getBranches(id);
    expect(exp.investigation.id).toBe(id);
    expect(trace.investigation_id).toBe(id);
    expect(Array.isArray(branches)).toBe(true);
  });

  it("keeps the immutable question and recorded status of the main investigation", async () => {
    const exp = await client.getInvestigation(MAIN);
    expect(exp.investigation.question).toMatch(/^How do NVIDIA's investments/);
    expect(exp.investigation.status).toBe("stopped");
    expect(exp.investigation.stop_reason).toBe("budget_exhausted");
    expect(exp.checkpoints.map((c) => c.id)).toEqual(["cp_4c05d11bbb4c4856", "cp_c92da0e30bac4932"]);
  });

  it("only issues GET requests", async () => {
    const log: string[] = [];
    const c = new ExplorationClient(fixtureFetch(log));
    await c.getInvestigation(MAIN);
    await c.getTrace(MAIN);
    await c.getBranches(MAIN);
    expect(log.every((l) => l.startsWith("GET "))).toBe(true);
  });
});

describe("ExplorationClient error handling", () => {
  it("maps 404 to not_found", async () => {
    const c = new ExplorationClient(fixtureFetch());
    await expect(c.getInvestigation("inv_missing")).rejects.toMatchObject({ kind: "not_found", status: 404 });
  });

  it("maps a contract mismatch to a contract error with issue paths", async () => {
    const c = new ExplorationClient(async () => new Response(JSON.stringify({ investigation: { id: 3 } }), { status: 200 }));
    const err = await c.getInvestigation(MAIN).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe("contract");
    expect(err.issues.length).toBeGreaterThan(0);
  });

  it("maps a network failure to a network error", async () => {
    const c = new ExplorationClient(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(c.getTrace(MAIN)).rejects.toMatchObject({ kind: "network" });
  });

  it("maps a 500 to an http error", async () => {
    const c = new ExplorationClient(async () => new Response("boom", { status: 500 }));
    await expect(c.getBranches(MAIN)).rejects.toMatchObject({ kind: "http", status: 500 });
  });

  it("rejects non-JSON bodies as contract errors", async () => {
    const c = new ExplorationClient(async () => new Response("<html>", { status: 200 }));
    await expect(c.getTrace(MAIN)).rejects.toMatchObject({ kind: "contract" });
  });
});
