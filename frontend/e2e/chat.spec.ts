import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:38125";
const workspace = async (request: any) =>
  (await request.get(`${api}/workspace`)).json();
const evidence = async (request: any) =>
  (await request.get(`${api}/__test/evidence`)).json();
test.beforeEach(async ({ page, request }) => {
  await request.post(`${api}/__test/reset`);
  await page.route(/^https?:/, (route) =>
    ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname)
      ? route.continue()
      : route.abort(),
  );
});
async function send(page: any, text: string) {
  const input = page.locator(".chat-wrap textarea");
  await expect(input).toBeVisible();
  await input.fill(text);
  await input.press("Enter");
}
async function saveName(page: any) {
  await page.getByLabel("Workspace name").fill("Acme North");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.getByText("REV 2", { exact: true })).toBeVisible();
}

test("production CopilotKit chat checks requirements, prepares exact proposal and leaves separate owner approval", async ({
  page,
  request,
}, info) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await send(page, "Propose mira@acme.example as a member");
  await expect(page.locator(".chat-wrap")).toContainText(
    "Please save a workspace name",
  );
  expect((await workspace(request)).invite_proposals).toHaveLength(0);
  await saveName(page);
  await send(page, "Propose mira@acme.example as a member");
  await expect(page.locator(".chat-wrap")).toContainText(
    "ready for owner review",
  );
  await expect(
    page.getByRole("button", { name: "Approve invite" }),
  ).toBeVisible();
  expect((await workspace(request)).invitations).toHaveLength(0);
  await page.getByRole("button", { name: "Approve invite" }).click();
  await expect(page.getByText("INVITED", { exact: true })).toBeVisible();
  const state = await workspace(request);
  expect(state.invitations).toHaveLength(1);
  expect(state.invitations[0]).toMatchObject({
    email: "mira@acme.example",
    role: "member",
  });
  const traces = (await evidence(request)).receipts;
  expect(
    traces.filter((t: any) => t.status === "completed").length,
  ).toBeGreaterThanOrEqual(2);
  expect(traces.at(-1).native).toHaveLength(3);
  expect(Object.values(traces.at(-1).lifecycle).every(Boolean)).toBe(true);
  await page.screenshot({
    path: info.outputPath("native-chat-approved.png"),
    fullPage: true,
  });
});

test("provider outage and unfinished responses are visible and a later genuine turn recovers", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  for (const mode of ["outage", "truncated"]) {
    await request.post(`${api}/__test/mode/${mode}`);
    await send(page, "Propose mira@acme.example as a member");
    await expect(page.locator(".chat-wrap .error[role=alert]")).toContainText(
      "could not complete",
    );
    expect((await workspace(request)).invite_proposals).toHaveLength(0);
  }
  await request.post(`${api}/__test/mode/normal`);
  await send(page, "Propose mira@acme.example as a member");
  await expect(page.locator(".chat-wrap")).toContainText(
    "ready for owner review",
  );
  await expect(page.locator(".chat-wrap .error[role=alert]")).toHaveCount(0);
  expect((await workspace(request)).invite_proposals).toHaveLength(1);
  expect((await workspace(request)).invitations).toHaveLength(0);
});

test("unauthorized owner error survives polling and rejection adds no member", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  await send(page, "Propose lee@acme.example as an admin");
  await expect(
    page.getByRole("button", { name: "Approve invite" }),
  ).toBeVisible();
  await page.getByLabel("Acting as").fill("stranger@acme.example");
  await page.getByRole("button", { name: "Approve invite" }).click();
  await expect(page.locator(".content > .error")).toContainText(
    "current workspace owner",
  );
  await page.waitForTimeout(3200);
  await expect(page.locator(".content > .error")).toContainText(
    "current workspace owner",
  );
  expect((await workspace(request)).invitations).toHaveLength(0);
  await page.getByLabel("Acting as").fill("owner@acme.example");
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(page.getByText("rejected", { exact: true })).toBeVisible();
  await expect(page.locator(".content > .error")).toHaveCount(0);
  expect((await workspace(request)).invitations).toHaveLength(0);
});

test("edited name keeps its original revision when another owner changes setup", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  await page.getByLabel("Workspace name").fill("Unsaved browser draft");
  await request.patch(`${api}/workspace/name`, {
    data: {
      name: "Other owner update",
      revision: 2,
      actor: "owner@acme.example",
    },
  });
  await expect(
    page.getByText("The workspace changed while you were editing.", {
      exact: false,
    }),
  ).toBeVisible({ timeout: 8000 });
  await expect(page.getByLabel("Workspace name")).toHaveValue(
    "Unsaved browser draft",
  );
  await expect(page.getByRole("button", { name: "Save name" })).toBeDisabled();
  expect((await workspace(request)).setup.name).toBe("Other owner update");
  await page.getByRole("button", { name: "Use current name" }).click();
  await expect(page.getByLabel("Workspace name")).toHaveValue(
    "Other owner update",
  );
  await page.getByLabel("Workspace name").fill("Reviewed current name");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.getByText("REV 4", { exact: true })).toBeVisible();
  expect((await workspace(request)).setup.name).toBe("Reviewed current name");
});

test("late poll response cannot overwrite the confirmed save", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  let enter!: () => void, release!: () => void;
  const started = new Promise<void>((r) => (enter = r)),
    blocked = new Promise<void>((r) => (release = r));
  await page.route(
    "**/workspace",
    async (route) => {
      const response = await route.fetch();
      enter();
      await blocked;
      try {
        await route.fulfill({ response });
      } catch {}
    },
    { times: 1 },
  );
  try {
    await started;
    await page.getByLabel("Workspace name").fill("Confirmed new name");
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(page.getByText("REV 3", { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByLabel("Workspace name")).toHaveValue(
    "Confirmed new name",
  );
  expect((await workspace(request)).setup.revision).toBe(3);
});

test("API outage disables writes and recovery clears only the read error", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await page.route("**/workspace", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Controlled unavailable"}',
    }),
  );
  await expect(page.locator(".content > .error")).toContainText(
    "Workspace API unavailable",
    { timeout: 8000 },
  );
  await expect(page.getByRole("button", { name: "Save name" })).toBeDisabled();
  await page.unroute("**/workspace");
  await expect(page.locator(".content > .error")).toHaveCount(0, {
    timeout: 8000,
  });
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
});

test("actual assistant math renders through patched KaTeX without raw script or unsafe links", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  await request.post(`${api}/__test/mode/markup`);
  await send(page, "Propose mira@acme.example as a member");
  await expect(page.locator(".chat-wrap")).toContainText(
    "Local proposal ready",
  );
  await expect(page.locator(".chat-wrap .katex").first()).toBeVisible();
  await expect(
    page.locator('.chat-wrap script, .chat-wrap a[href^="javascript:"]'),
  ).toHaveCount(0);
  expect(await page.evaluate(() => "syntheticUnsafe" in window)).toBe(false);
});

test("stopping real browser chat drains the owned native request before any proposal", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Workspace name")).toBeEnabled();
  await saveName(page);
  await request.post(`${api}/__test/mode/pending`);
  const before = (await evidence(request)).requests;
  await send(page, "Propose mira@acme.example as a member");
  await expect
    .poll(async () => (await evidence(request)).requests)
    .toBe(before + 1);
  await page.getByRole("button", { name: /stop/i }).click();
  await expect
    .poll(async () => (await evidence(request)).active, { timeout: 8000 })
    .toBe(0);
  const state = await workspace(request);
  expect(state.invite_proposals).toHaveLength(0);
  await request.post(`${api}/__test/mode/normal`);
});

test("busy imported queue is searchable and one exact approval preserves unrelated records", async ({
  page,
  request,
}, info) => {
  await request.post(`${api}/__test/reset?case_id=busy-team`);
  const before = await workspace(request);
  await page.goto("/");
  await expect(page.getByText("24 PENDING", { exact: true })).toBeVisible();
  await page.getByLabel("Find invitation").fill("candidate080@acme.example");
  await expect(
    page.getByRole("button", { name: "Approve invite" }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Approve invite" }).click();
  await expect(page.getByText("23 PENDING", { exact: true })).toBeVisible();
  const after = await workspace(request);
  expect(after.invitations).toHaveLength(65);
  expect(after.invitations.at(-1)).toMatchObject({
    email: "candidate080@acme.example",
    role: "admin",
  });
  expect(
    after.invite_proposals.filter(
      (p: any) => p.email !== "candidate080@acme.example",
    ),
  ).toEqual(
    before.invite_proposals.filter(
      (p: any) => p.email !== "candidate080@acme.example",
    ),
  );
  expect(after.invitations.slice(0, 64)).toEqual(before.invitations);
  await page.screenshot({
    path: info.outputPath("busy-imported-queue-approved.png"),
    fullPage: true,
  });
});

test("alternate domain and owner come from the API and hostile workspace text is escaped", async ({
  page,
  request,
}) => {
  await request.post(`${api}/__test/reset?case_id=alternate-domain`);
  await page.goto("/");
  await expect(page.getByLabel("Acting as")).toHaveValue("owner@cedar.example");
  await send(page, "Propose jordan@cedar.example as an admin");
  await expect(page.locator(".chat-wrap")).toContainText(
    "ready for owner review",
  );
  await page.getByRole("button", { name: "Approve invite" }).click();
  await expect(page.getByText("INVITED", { exact: true })).toBeVisible();
  expect((await workspace(request)).invitations[0]).toMatchObject({
    email: "jordan@cedar.example",
    role: "admin",
  });
  await request.post(`${api}/__test/reset?case_id=hostile-source`);
  await page.reload();
  await expect(page.getByLabel("Workspace name")).toHaveValue(
    "<script>window.syntheticUnsafe=true</script>",
  );
  expect(await page.evaluate(() => "syntheticUnsafe" in window)).toBe(false);
});
