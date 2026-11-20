import { expect, test } from "@playwright/test";

// Milestone 2: grounded branching against a RUNNING backend. Creates a real branch record
// (local, no research) in whatever database that backend uses — point it at a copy.
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const ID = process.env.E2E_INVESTIGATION ?? "inv_93606fb27bb74f3c";
const CLAIM = process.env.E2E_CLAIM ?? "clm_195d970aad8a3285";

test("Save Lantern creates a grounded child and leaves the parent unchanged", async ({ page, request }) => {
  const before = await (await request.get(`${API}/api/exploration/investigations/${ID}`)).text();
  const branchesBefore = await (await request.get(`${API}/api/exploration/investigations/${ID}/branches`)).json();
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") posts.push(new URL(r.url()).pathname);
  });

  await page.goto(`/?mode=live&investigation=${ID}&node=${CLAIM}`);
  await page.getByRole("button", { name: /Challenge this claim/ }).click();
  await expect(page.getByTestId("fork-investigate")).toBeDisabled();
  await page.getByTestId("save-lantern").click();
  await expect(page.getByTestId("branch-created")).toBeVisible();

  expect(posts).toEqual([`/api/exploration/investigations/${ID}/branches`]); // no /resume, no step
  const after = await (await request.get(`${API}/api/exploration/investigations/${ID}`)).text();
  expect(after).toBe(before);
  const branches = await (await request.get(`${API}/api/exploration/investigations/${ID}/branches`)).json();
  expect(branches.length).toBe(branchesBefore.length + 1);
  const created = branches[branches.length - 1];
  const childTrace = await (await request.get(`${API}/api/exploration/investigations/${created.child_investigation_id}/trace`)).json();
  expect(childTrace.parent_investigation_id).toBe(ID);
  expect(childTrace.attached_claims.map((c: { id: string }) => c.id)).toEqual([CLAIM]);
  expect(childTrace.events.every((e: { stage: string }) => e.stage === "checkpoint")).toBe(true);

  // The child is reachable, unstarted, and cannot start billable research in this build.
  await page.getByRole("button", { name: "Open child" }).click();
  await expect(page).toHaveURL(new RegExp(`investigation=${created.child_investigation_id}`));
  await expect(page.getByTestId("start-research")).toBeDisabled();

  // It appears in the live Constellation, emerging from its parent checkpoint.
  await page.getByTestId("open-constellation").click();
  await expect(page.getByTestId("explore-parent")).toBeVisible();
  await expect(page.locator(".cx-child").filter({ hasText: childTrace.question.slice(0, 20) }).first()).toBeVisible();
});

test("the stored investigation list comes from the backend", async ({ page, request }) => {
  const list = await (await request.get(`${API}/api/exploration/investigations?limit=100`)).json();
  await page.goto("/?mode=live");
  await expect(page.getByTestId("investigation-row")).toHaveCount(Math.min(100, list.items.length));
  await expect(page.getByTestId("investigation-row").first()).toContainText(list.items[0].id);
});
