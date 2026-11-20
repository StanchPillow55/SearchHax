import { expect, test } from "@playwright/test";

// M5: the Findings view shows recorded claims, evidence and outcome for a persisted run. Read-only.
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";
const ID = process.env.E2E_INVESTIGATION ?? "inv_93606fb27bb74f3c";
const SHOTS = process.env.E2E_SCREENSHOT_DIR ?? "e2e/artifacts";

test("Findings lists every stored claim with its status and an honest outcome", async ({ page, request }) => {
  const exp = await (await request.get(`${API}/api/exploration/investigations/${ID}`)).json();
  const methods: string[] = [];
  page.on("request", (r) => new URL(r.url()).pathname.startsWith("/api/") && methods.push(r.method()));
  await page.goto(`/?mode=live&investigation=${ID}`);
  await page.getByTestId("open-findings").click();
  await expect(page.getByTestId("findings-question")).toHaveText(exp.investigation.question);
  const groups = new Set<string>(exp.claims.map((c: { status: string; text: string }) => `${c.status}|${c.text.toLowerCase().replace(/\s+/g, " ").trim()}`));
  await expect(page.getByTestId("finding")).toHaveCount(groups.size);
  const supported = [...groups].filter((g) => g.startsWith("supported|")).length;
  await expect(page.locator('[data-testid=finding][data-status=supported]')).toHaveCount(supported);
  await expect(page.getByTestId("findings-outcome")).toContainText(`${exp.claims.filter((c: { status: string }) => c.status === "supported").length} supported`);
  if (exp.investigation.stop_reason !== "evidence_sufficient") {
    await expect(page.getByTestId("findings-outcome")).toContainText(/Partial/);
  }
  await expect(page.getByTestId("findings-open")).toContainText(exp.unresolved_questions[0].text.slice(0, 30));
  await page.screenshot({ path: `${SHOTS}/m5-findings.png`, fullPage: false });

  // "Show in trace" returns to the same claim node in the Interior.
  const first = page.getByTestId("finding").first();
  await first.getByRole("button", { name: "Show in trace" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
  await expect(page.locator(".ix-inspector [data-testid=record-ref]").first()).toContainText("claims ·");
  expect(methods.every((m) => m === "GET")).toBe(true);
});
