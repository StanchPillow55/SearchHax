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
  // Contract 1.1.0: the child keeps the original question; the objective is separate; it is saved, not running.
  const parentQuestion = JSON.parse(before).investigation.question;
  expect(childTrace.question).toBe(parentQuestion);
  expect(childTrace.root_question).toBe(parentQuestion);
  expect(childTrace.branch_objective).toBe(created.objective);
  expect(childTrace.lifecycle).toBe("saved");

  // The child is reachable, unstarted, and cannot start billable research in this build.
  await page.getByRole("button", { name: "Open child" }).click();
  await expect(page).toHaveURL(new RegExp(`investigation=${created.child_investigation_id}`));
  await expect(page.getByTestId("research-question")).toHaveText(parentQuestion);
  await expect(page.getByText("This Lantern has not started researching")).toBeVisible();
  await expect(page.getByTestId("start-research")).toBeDisabled();

  // It appears in the live Constellation, emerging from its parent checkpoint.
  await page.getByTestId("open-constellation").click();
  await expect(page.getByTestId("explore-parent")).toBeVisible();
  await expect(page.locator(".cx-child").filter({ hasText: created.objective.slice(0, 20) }).first()).toBeVisible();
});

test("the stored investigation list comes from the backend", async ({ page, request }) => {
  const list = await (await request.get(`${API}/api/exploration/investigations?limit=100`)).json();
  await page.goto("/?mode=live");
  await expect(page.getByTestId("investigation-row")).toHaveCount(Math.min(100, list.items.length));
  await expect(page.getByTestId("investigation-row").first()).toContainText(list.items[0].id);
});

test("a legacy branch whose question was overwritten shows the original question and says so", async ({ page, request }) => {
  const LEGACY = process.env.E2E_LEGACY_BRANCH ?? "inv_c07010e29b434741";
  const tr = await request.get(`${API}/api/exploration/investigations/${LEGACY}/trace`);
  test.skip(!tr.ok(), "legacy branch record not present in this database");
  const trace = await tr.json();
  test.skip(!trace.root_question || trace.root_question === trace.question, "record is not an overwritten legacy branch");
  await page.goto(`/?mode=live&investigation=${LEGACY}`);
  await expect(page.getByTestId("research-question")).toHaveText(trace.root_question);
  await expect(page.locator("body")).toContainText("Legacy branch:");
  await expect(page.getByText("This Lantern has not started researching")).toBeVisible();
  await page.screenshot({ path: `${process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts"}/m2-legacy-branch.png` });
});

test("a vague challenge with no selected claim cannot be saved", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => r.method() === "POST" && posts.push(r.url()));
  const exp = await (await page.request.get(`${API}/api/exploration/investigations/${ID}`)).json();
  const cp = exp.checkpoints[exp.checkpoints.length - 1].id;
  await page.goto(`/?mode=live&investigation=${ID}&node=${cp}`);
  await page.getByRole("button", { name: /Fork Lantern from/ }).click();
  await page.getByRole("button", { name: "Challenge claim" }).click();
  await page.getByTestId("branch-objective").fill("Is this true?");
  await expect(page.getByTestId("save-lantern")).toBeDisabled();
  await expect(page.getByTestId("challenge-grounding")).toBeVisible();
  await page.screenshot({ path: `${process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts"}/m2-vague-challenge.png` });
  expect(posts).toEqual([]);
});

test("a child can be compared with its parent from stored records", async ({ page, request }) => {
  const CHILD_RUN = process.env.E2E_CHILD_WITH_RESEARCH ?? "inv_390477badbf24e65";
  const tr = await request.get(`${API}/api/exploration/investigations/${CHILD_RUN}/trace`);
  test.skip(!tr.ok(), "child record not present");
  const trace = await tr.json();
  test.skip(!trace.parent_investigation_id, "record is not a child");
  const methods: string[] = [];
  page.on("request", (r) => new URL(r.url()).pathname.startsWith("/api/") && methods.push(r.method()));
  await page.goto(`/?mode=live&investigation=${CHILD_RUN}`);
  await page.getByTestId("compare-parent").click();
  await expect(page.getByTestId("lc-parent")).toContainText(trace.parent_investigation_id);
  await expect(page.getByTestId("lc-child")).toContainText(CHILD_RUN);
  await expect(page.getByTestId("lc-child")).toContainText(`${trace.usage_search_calls} searches`);
  await page.screenshot({ path: `${process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts"}/m6-lineage-compare.png` });
  expect(methods.every((m) => m === "GET")).toBe(true);
});
