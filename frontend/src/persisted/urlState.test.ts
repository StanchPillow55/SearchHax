import { beforeEach, describe, expect, it } from "vitest";
import { readCanvas, writeCanvas } from "./urlState";

describe("canvas layout memory (M6)", () => {
  beforeEach(() => window.localStorage.clear());

  it("round-trips per investigation and keeps investigations apart", () => {
    writeCanvas("inv_a", { zoom: 1.5, pan: { x: 10, y: -20 }, expanded: ["doc_1"], collapsedRounds: [2], granularity: "round" });
    expect(readCanvas("inv_a")).toEqual({ zoom: 1.5, pan: { x: 10, y: -20 }, expanded: ["doc_1"], collapsedRounds: [2], granularity: "round" });
    expect(readCanvas("inv_b")).toBeNull();
  });

  it("rejects malformed stored values instead of applying them", () => {
    window.localStorage.setItem("searchhax:canvas:inv_x", "{not json");
    expect(readCanvas("inv_x")).toBeNull();
    window.localStorage.setItem("searchhax:canvas:inv_y", JSON.stringify({ zoom: "big", pan: { x: 0, y: 0 } }));
    expect(readCanvas("inv_y")).toBeNull();
    window.localStorage.setItem("searchhax:canvas:inv_z", JSON.stringify({ zoom: 99, pan: { x: 1, y: 2 }, expanded: [1, "ok"] }));
    expect(readCanvas("inv_z")).toMatchObject({ zoom: 4, expanded: ["ok"], granularity: "event" });
  });
});
