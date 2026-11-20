import { expect, test } from "@playwright/test";

// M3 (non-billable part): saving a new question through React creates exactly one real backend
// investigation in the "saved" lifecycle, with no search. Point E2E_API_URL at a DB copy.
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";

test("New investigation stores one saved investigation and runs nothing", async ({ page, request }) => {
  const question = `How do HBM supply constraints shape AI capacity plans? (e2e ${Date.now()})`;
  const before = (await (await request.get(`${API}/api/exploration/investigations?limit=1`)).json()).total;
  const posts: string[] = [];
  page.on("request", (r) => r.method() === "POST" && posts.push(new URL(r.url()).pathname));

  await page.goto("/?mode=live");
  await page.getByRole("button", { name: /New investigation/ }).click();
  await expect(page.getByTestId("new-question")).toBeFocused();
  await page.getByTestId("new-question").fill(question);
  await page.getByTestId("create-investigation").dblclick();
  await expect(page.getByTestId("research-question")).toHaveText(question);
  await expect(page.getByTestId("investigation-status")).toContainText(/not started/i);
  await expect(page.getByTestId("start-research")).toBeDisabled();
  await page.screenshot({ path: `${SHOTS}/m3-new-investigation.png` });

  expect(posts).toEqual(["/api/exploration/investigations"]);
  const list = await (await request.get(`${API}/api/exploration/investigations?limit=5`)).json();
  expect(list.total).toBe(before + 1);
  const row = list.items.find((i: { question: string }) => i.question === question);
  expect(row.lifecycle).toBe("saved");
  expect(row.status).toBe("created");
  const tr = await (await request.get(`${API}/api/exploration/investigations/${row.id}/trace`)).json();
  expect(tr.search_event_count).toBe(0);
  expect(tr.usage_search_calls).toBe(0);
});
