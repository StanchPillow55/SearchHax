import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const ID = process.env.E2E_INVESTIGATION ?? "inv_93606fb27bb74f3c";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";
mkdirSync(SHOTS, { recursive: true });

test("vertical slice (reads only): stored investigation → source → checkpoint → reload", async ({ page, request }) => {
  // Ground truth straight from the backend, for comparison with what the UI shows.
  const exp = await (await request.get(`${API}/api/exploration/investigations/${ID}`)).json();
  const tr = await (await request.get(`${API}/api/exploration/investigations/${ID}/trace`)).json();
  const apiCalls: string[] = [];
  page.on("request", (r) => {
    const path = new URL(r.url()).pathname;
    if (path.startsWith("/api/")) apiCalls.push(`${r.method()} ${path}`);
  });

  // 1–2. Open the React frontend and select a stored investigation.
  await page.goto("/?mode=live");
  await page.getByTestId("investigation-id-input").fill(ID);
  await page.getByTestId("investigation-id-input").press("Enter");

  // 3. Original question and actual status.
  await expect(page.getByTestId("research-question")).toHaveText(exp.investigation.question);
  await expect(page.getByTestId("investigation-status")).toContainText(/budget exhausted/i);
  await expect(page.getByTestId("data-origin")).toContainText("Persisted");

  // 4–5. Recorded events and checkpoints drive the Interior timeline.
  await expect(page.getByText(`Event ${tr.events.length} / ${tr.events.length}`)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/1-interior-latest.png` });

  // 6–7. Select a recorded source and inspect its provenance.
  const doc = exp.documents.find((d: { id: string }) => d.id === "doc_a0d452123b0ca0d5") ?? exp.documents[0];
  await page.getByPlaceholder(/Find in investigation/).fill(doc.title.slice(0, 24));
  await page.locator(".ix-search-results button").first().click();
  await expect(page.locator(".ix-inspector")).toContainText(doc.canonical_url);
  await expect(page.locator(".ix-inspector [data-testid=record-ref]")).toContainText(`documents · ${doc.id}`);
  await expect(page).toHaveURL(new RegExp(`node=${doc.id}`));
  await page.screenshot({ path: `${SHOTS}/2-source-provenance.png` });

  // 8–9. Select a persisted checkpoint and view its recorded snapshot.
  const cp = exp.checkpoints[0];
  const snapDocs = (cp.state_json.snapshot?.documents ?? []).length;
  await page.getByRole("button", { name: /← C1|C1 →/ }).click();
  await page.getByRole("button", { name: "View historical snapshot" }).click();
  await expect(page.getByText(/Checkpoint snapshot loaded · C1/)).toBeVisible();
  await expect(page.locator(".ix-inspector")).toContainText(`Recorded snapshot · step ${cp.step}`);
  await expect(page.locator(".ix-snap-counts")).toContainText(`${snapDocs}Documents`, { ignoreCase: true });
  await expect(page).toHaveURL(new RegExp(`cp=${cp.id}`));
  // Branching from a persisted checkpoint is available (Milestone 2) but nothing is written until Save.
  await expect(page.getByRole("button", { name: /Fork Lantern from C1/ })).toBeEnabled();
  await page.screenshot({ path: `${SHOTS}/3-checkpoint-snapshot.png` });

  // 10. Reload and reopen the same investigation at the same checkpoint.
  await page.reload();
  await expect(page.getByTestId("research-question")).toHaveText(exp.investigation.question);
  await expect(page.getByText(/Checkpoint snapshot loaded · C1/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/4-after-reload.png` });

  // Only reads were made on this journey.
  expect(apiCalls.length).toBeGreaterThan(0);
  expect(apiCalls.every((c) => c.startsWith("GET "))).toBe(true);
});

test("demo mode is labelled and isolated from the backend", async ({ page }) => {
  const apiCalls: string[] = [];
  page.on("request", (r) => new URL(r.url()).pathname.startsWith("/api/") && apiCalls.push(r.url()));
  await page.goto("/?mode=demo");
  await expect(page.getByTestId("demo-ribbon")).toContainText(/simulated/i);
  await page.waitForTimeout(500);
  expect(apiCalls).toHaveLength(0);
});

test("switching to the recorded child loads only the child's records", async ({ page, request }) => {
  const child = (await (await request.get(`${API}/api/exploration/investigations/${ID}/branches`)).json())[0];
  test.skip(!child, "no recorded branch for this investigation");
  const childExp = await (await request.get(`${API}/api/exploration/investigations/${child.child_investigation_id}`)).json();
  await page.goto(`/?mode=live&investigation=${ID}`);
  await page.locator(`.ix-fork`).first().dblclick();
  await expect(page).toHaveURL(new RegExp(`investigation=${child.child_investigation_id}`));
  await expect(page.getByTestId("data-origin")).toContainText("Persisted");
  await expect(page.locator("body")).toContainText(childExp.investigation.id);
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`investigation=${ID}`));
});

test("the canvas zoom and position are restored after a reload (this browser only)", async ({ page }) => {
  await page.goto(`/?mode=live&investigation=${ID}`);
  await expect(page.getByTestId("research-question")).toBeVisible();
  const pct = page.locator(".ix-zoom-pct");
  await page.getByTitle("Zoom in").click();
  await page.getByTitle("Zoom in").click();
  const before = (await pct.innerText()).trim();
  await page.waitForTimeout(700);
  await page.reload();
  await expect(page.getByTestId("research-question")).toBeVisible();
  await expect(pct).toHaveText(before);
});

test("the investigation map is usable from the keyboard", async ({ page }) => {
  await page.goto(`/?mode=live&investigation=${ID}`);
  const stage = page.getByRole("region", { name: /Investigation map/ });
  await stage.focus();
  await expect(stage).toBeFocused();
  const pct = page.locator(".ix-zoom-pct");
  const before = (await pct.innerText()).trim();
  await page.keyboard.press("+");
  await expect(pct).not.toHaveText(before);
  await page.keyboard.press("0");
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => document.activeElement?.tagName);
  expect(focused).toBe("BUTTON");
  await page.keyboard.press("Enter");
  await expect(page.locator(".ix-inspector")).toBeVisible();
});
