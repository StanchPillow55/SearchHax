import { expect, test } from "@playwright/test";

// M8: inspect → correct → reload and still see the correction → start a frontier question.
// Writes one knowledge assertion (local, no provider call). Point E2E_API_URL at a DB copy.
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";

test("a knowledge correction persists across reload and encountered is never known", async ({ page, request }) => {
  const list = (await (await request.get(`${API}/api/exploration/investigations?limit=200`)).json()).items as { id: string }[];
  let id: string | null = null;
  for (const item of list) {
    const g = await (await request.get(`${API}/api/exploration/profile/knowledge-graph?investigation_id=${item.id}`)).json();
    if (g.profile_id && g.nodes.some((n: { epistemic_state: string }) => n.epistemic_state === "encountered") && g.nodes.some((n: { epistemic_state: string }) => n.epistemic_state === "frontier")) {
      id = item.id;
      break;
    }
  }
  test.skip(!id, "no investigation with a research profile in this database");
  const before = await (await request.get(`${API}/api/exploration/profile/knowledge-graph?investigation_id=${id}`)).json();

  await page.goto(`/?mode=live&investigation=${id}`);
  await page.getByTestId("open-knowledge").click();
  await expect(page.getByTestId("knowledge-profile")).toContainText(before.profile_id);
  for (const state of ["known", "interested", "frontier", "encountered"]) {
    const n = before.nodes.filter((x: { epistemic_state: string }) => x.epistemic_state === state).length;
    await expect(page.getByTestId(`knowledge-${state}`).getByTestId("knowledge-node")).toHaveCount(n);
  }
  await page.screenshot({ path: `${SHOTS}/m8-knowledge.png` });

  const encountered = page.getByTestId("knowledge-encountered").getByTestId("knowledge-node").first();
  const label = (await encountered.locator(".fx-claim-head > span").first().innerText()).trim();
  await encountered.getByRole("button", { name: "I know this" }).click();
  await expect(page.getByTestId("knowledge-known")).toContainText(label);

  await page.reload();
  await page.getByTestId("open-knowledge").click();
  await expect(page.getByTestId("knowledge-known").getByTestId("knowledge-node").filter({ hasText: label })).toContainText("confirmed by you");
  // The retrieved source itself is still only "encountered".
  await expect(page.getByTestId("knowledge-encountered")).toContainText(label);

  // Frontier → pre-filled New Investigation (nothing is created until the user saves).
  const frontier = page.getByTestId("knowledge-frontier").getByTestId("knowledge-node").first();
  const topic = (await frontier.locator(".fx-claim-head > span").first().innerText()).trim();
  const posts: string[] = [];
  page.on("request", (r) => r.method() === "POST" && posts.push(r.url()));
  await frontier.getByTestId("investigate-frontier").click();
  await expect(page.getByTestId("new-question")).toHaveValue(topic);
  expect(posts).toEqual([]);
});
