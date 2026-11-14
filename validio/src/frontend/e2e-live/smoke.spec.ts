import { connector, requested } from "./connector";
import { expect, fresh, test, connectMcpAgent } from "./kitchen";

// The public-deploy shape (playwright.live.config.ts): the built web app and the API from one process, no
// Vite. The login page lets a juror into a demo copy, an MCP agent connects through the Agent page and
// orders; Home and Activity read it through /api on the same origin, a reload is served by the fallback.

test.describe.configure({ mode: "serial" });

test("app and API from one process, every page behind the login", async ({ browser, baseURL }) => {
  const anon = await browser.newContext({ baseURL });
  const r = anon.request;
  expect((await r.get("/api/health")).status()).toBe(200);
  expect((await r.get("/api/nope")).status()).toBe(404);
  expect((await r.get("/api/account")).status()).toBe(401);
  // a deep link is the SPA's index.html, not a 404, and the SPA sends a visitor to the login page
  const deep = await r.get("/activity/R-9");
  expect(deep.status()).toBe(200);
  expect(await deep.text()).toContain("<html");
  const p = await anon.newPage();
  await p.goto("/activity/R-9");
  await expect(p).toHaveURL(/\/login$/);
  await expect(p.getByTestId("try-demo")).toBeVisible();
  await anon.close();
});

test("the connected agent orders automatically, the row opens from Activity", async ({ page, kitchen }) => {
  await fresh(kitchen);
  const url = await connectMcpAgent(kitchen);
  const run = connector(url);
  expect(run.ok, run.out).toBe(true);
  const { id } = requested(run.out);
  await page.goto("/");
  await expect(page.getByTestId("demo-bar")).toBeVisible();
  await expect(page.getByTestId("home-agent")).toContainText("active");
  await page.getByTestId("nav-activity").click();
  await page.getByTestId(`activity-${id}`).click();
  await expect(page).toHaveURL(new RegExp(`/activity/${id}$`));
  await expect(page.getByTestId("detail-status")).toHaveText("Ordered automatically");
  await page.reload(); // served by FastAPI's fallback
  await expect(page.getByTestId("detail-status")).toHaveText("Ordered automatically");
});

test("Reset in the demo bar starts the copy again", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("demo-reset").click();
  await expect.poll(async () => (await (await page.request.get("/api/agent")).json()).state).toBe("none");
});
