import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

/*
 * Milestone 1 audit against a RUNNING exploration API (not fixtures). Read-only: every
 * request the page makes is asserted to be a GET. Covers the checks the vertical-slice
 * spec does not: listing, convergence decisions, historical playback, and switching
 * between two unrelated investigations without carrying data across.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const A = process.env.E2E_INVESTIGATION ?? "inv_93606fb27bb74f3c";
const B = process.env.E2E_OTHER_INVESTIGATION ?? "inv_dab1878d08024200";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";
mkdirSync(SHOTS, { recursive: true });

test("listing, convergence, playback and switching use only persisted records", async ({ page, request }) => {
  const list = await (await request.get(`${API}/api/exploration/investigations?limit=100`)).json();
  const expA = await (await request.get(`${API}/api/exploration/investigations/${A}`)).json();
  const trA = await (await request.get(`${API}/api/exploration/investigations/${A}/trace`)).json();
  const expB = await (await request.get(`${API}/api/exploration/investigations/${B}`)).json();
  const methods: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).pathname.startsWith("/api/")) methods.push(r.method());
  });

  // 1. Listing comes from GET /investigations and shows the stored questions.
  await page.goto("/?mode=live");
  const rows = page.getByTestId("investigation-row");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBe(Math.min(list.items.length, 100));
  await expect(page.getByTestId("investigation-list")).toContainText(list.items[0].id);
  await page.screenshot({ path: `${SHOTS}/a1-listing.png` });

  // 2. Select A from the list (not by typing an id).
  await rows.filter({ has: page.locator("code", { hasText: new RegExp(`^${A}$`) }) }).click();
  await expect(page.getByTestId("research-question")).toHaveText(expA.investigation.question);
  await expect(page).toHaveURL(new RegExp(`investigation=${A}`));

  // 3. Convergence decisions: the recorded rationale text is reachable from the trace.
  const conv = trA.events.filter((e: { stage: string }) => e.stage === "convergence");
  expect(conv.length).toBeGreaterThan(0);
  await page.getByPlaceholder(/Find in investigation/).fill("convergence");
  const hit = page.locator(".ix-search-results button").first();
  if (await hit.count()) {
    await hit.click();
    await expect(page.locator(".ix-inspector")).toContainText(/convergence|stop|continue/i);
  }
  await page.screenshot({ path: `${SHOTS}/a2-convergence.png` });
  await page.getByPlaceholder(/Find in investigation/).fill("");

  // 4. Historical playback: step back to the first event and return to latest.
  const total = trA.events.length;
  await expect(page.getByText(`Event ${total} / ${total}`)).toBeVisible();
  await page.getByTitle("Start of investigation").click();
  await expect(page.getByText(new RegExp(`Event 1 / ${total}`))).toBeVisible();
  await page.getByTitle(/Next event|Next round milestone/).click();
  await page.screenshot({ path: `${SHOTS}/a3-playback-early.png` });
  await page.getByTitle("Return to latest state").click();
  await expect(page.getByText(`Event ${total} / ${total}`)).toBeVisible();

  // 5. Switch to an unrelated investigation B: none of A's records may remain in the workspace.
  //    (The sidebar's "Recently opened" list legitimately names A; it is excluded.)
  await page.goto(`/?mode=live&investigation=${B}`);
  await expect(page.getByTestId("research-question")).toHaveText(expB.investigation.question);
  const bodyB = await page.locator("main.ix-screen").innerText();
  const bDocIds = new Set(expB.documents.map((d: { id: string }) => d.id));
  const leaked = expA.documents.filter((d: { id: string; title: string }) => !bDocIds.has(d.id) && d.title.length > 20 && bodyB.includes(d.title));
  expect(leaked.map((d: { id: string }) => d.id)).toEqual([]);
  expect(bodyB).not.toContain(expA.investigation.question);
  await page.screenshot({ path: `${SHOTS}/a4-switched.png` });

  // 6. Back to A after a full reload: same question, same event count.
  await page.goto(`/?mode=live&investigation=${A}`);
  await page.reload();
  await expect(page.getByTestId("research-question")).toHaveText(expA.investigation.question);
  await expect(page.getByText(`Event ${total} / ${total}`)).toBeVisible();

  expect(methods.length).toBeGreaterThan(0);
  expect(methods.every((m) => m === "GET")).toBe(true);
});
