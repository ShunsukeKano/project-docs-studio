import { expect, test } from "@playwright/test";

import { articleWithTwoVersions, getArticle, updateDraft } from "./helpers";

test.describe("editing the same draft from two places", () => {
  test("a stale save is refused, keeps my text, and can be resubmitted on purpose", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);
    await expect(page.locator("#draft-body")).toHaveValue("Version two");

    // Another writer saves first (through the API, which is the same situation as a second tab).
    await updateDraft(request, article.id, article.draft_version, { body: "Written by someone else" });

    await page.locator("#draft-body").fill("My unsent text");
    await page.getByRole("button", { name: "Save draft" }).click();

    await expect(page.getByText("The server copy changed")).toBeVisible();
    await expect(page.locator("#draft-body")).toHaveValue("My unsent text"); // my input is kept
    expect((await getArticle(request, article.id)).draft_body).toBe("Written by someone else"); // nothing overwritten

    await page.getByRole("button", { name: /Resubmit mine/ }).click();
    await expect.poll(async () => (await getArticle(request, article.id)).draft_body).toBe("My unsent text");
    await expect(page.getByText("The server copy changed")).toBeHidden();
  });

  test("Publish with an out-of-date version is refused and creates no snapshot", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);
    await updateDraft(request, article.id, article.draft_version, { body: "Changed elsewhere" });

    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByText("The server copy changed")).toBeVisible();
    expect((await getArticle(request, article.id)).live_version_number).toBe(2); // still version 2
  });
});
