import { expect, test } from "@playwright/test";

// M7: a passage selected in the trace shows its OWN recorded Focus point (not its document's).
// Creates one offline Story C fixture investigation (fixture corpus; no provider call).
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";

test("a passage maps to its own recorded point and back to the trace", async ({ page, request }) => {
  const run = await request.post(`${API}/api/exploration/fixtures/story-c`);
  expect(run.ok()).toBe(true);
  const exp = await run.json();
  const id = exp.investigation.id;
  const cp = exp.checkpoints[exp.checkpoints.length - 1];
  const rows = cp.state_json.policy_space_passages ?? [];
  expect(rows.length).toBeGreaterThan(0);
  const tr = await (await request.get(`${API}/api/exploration/investigations/${id}/trace`)).json();
  const spanIds = new Set(rows.map((r: { span_id: string }) => r.span_id));
  const node = tr.nodes.find((n: { type: string; payload: { span_id?: string } }) => n.type === "evidence" && spanIds.has(n.payload.span_id ?? ""));
  test.skip(!node, "no trace passage carries a recorded span id");
  const row = rows.find((r: { span_id: string }) => r.span_id === node.payload.span_id);

  await page.goto(`/?mode=live&investigation=${id}&node=${encodeURIComponent(node.id)}`);
  await expect(page.locator(".ix-inspector")).toContainText("This passage's own recorded point");
  await page.screenshot({ path: `${SHOTS}/m7-passage-point.png` });
  await page.locator(".ix-inspector .inspector-link").last().click();
  await expect(page.locator("body")).toContainText("passages");
  await expect(page.locator("body")).toContainText(row.span_id);
  await page.screenshot({ path: `${SHOTS}/m7-passage-3d.png` });
  await page.getByRole("button", { name: "Show in investigation trace" }).click();
  await expect(page.locator(".ix-inspector [data-testid=record-ref]").first()).toContainText(`evidence_spans · ${row.span_id}`);
});
