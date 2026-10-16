import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:38125";
test.beforeEach(async ({ request, page }) => {
  await request.post(`${api}/__test/reset`);
  await request.patch(`${api}/workspace/name`, {
    data: { name: "Acme North", revision: 1, actor: "owner@acme.example" },
  });
  await page.route(/^https?:/, (route) =>
    ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );
});
test("untouched name tracks current API instead of retaining an old value at a new revision", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toHaveValue("Acme North");
  await request.patch(`${api}/workspace/name`, {
    data: {
      name: "Updated by another owner",
      revision: 2,
      actor: "owner@acme.example",
    },
  });
  await expect(page.getByLabel("Workspace name")).toHaveValue(
    "Updated by another owner",
    { timeout: 8000 },
  );
});
test("structured validation errors remain readable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toHaveValue("Acme North");
  await page.getByLabel("Acting as").fill("not an email");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.locator(".content .error[role=alert]")).not.toContainText(
    "[object Object]",
  );
  await expect(page.locator(".content .error[role=alert]")).toContainText(
    /actor|email/i,
  );
});
