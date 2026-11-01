import { expect, test } from "@playwright/test";

import { articleWithTwoVersions, getArticle, listVersions, publicArticle } from "./helpers";

test.describe("history, restore, delete, unpublish", () => {
  test("the history marks the live version and protects it from deletion", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);

    const live = page.locator("li", { hasText: "Version 2" });
    await expect(live.getByText("Live")).toBeVisible();
    await expect(live.getByRole("button", { name: "Delete" })).toBeDisabled();
    await expect(page.locator("li", { hasText: "Version 1" }).getByRole("button", { name: "Delete" })).toBeEnabled();
  });

  test("a version can be opened and shows its full text", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);
    await page.locator("li", { hasText: "Version 1" }).getByRole("button", { name: "View" }).click();
    await expect(page.getByRole("heading", { name: /Version 1:/ })).toBeVisible();
    await expect(page.getByText("Version one").first()).toBeVisible();
  });

  test("Restore copies the old text into the draft and changes nothing else", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);
    await page.locator("li", { hasText: "Version 1" }).getByRole("button", { name: "Restore to draft" }).click();

    await expect(page.locator("#draft-body")).toHaveValue("Version one");
    await expect.poll(async () => (await getArticle(request, article.id)).draft_body).toBe("Version one");

    const after = await getArticle(request, article.id);
    expect(after.status).toBe("published");
    expect(after.live_version_number).toBe(2);
    expect(after.published_at).toBe(article.published_at);
    expect(((await (await publicArticle(request, article.slug)).json()) as { body: string }).body).toBe("Version two");
    expect(await listVersions(request, article.id)).toHaveLength(2); // no snapshot added or removed
  });

  test("an old version can be deleted (after a confirmation); the live one stays", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    page.on("dialog", (dialog) => void dialog.accept());
    await page.goto(`/studio/${article.id}`);
    await page.locator("li", { hasText: "Version 1" }).getByRole("button", { name: "Delete" }).click();

    await expect.poll(async () => (await listVersions(request, article.id)).map((v) => v.version_number)).toEqual([2]);
    await expect(page.getByRole("status").filter({ hasText: "Version 1 deleted" })).toBeVisible();
  });

  test("Unpublish takes the article down and keeps its history; Publish brings it back", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);

    await page.getByRole("button", { name: "Unpublish" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Taken down" })).toBeVisible();
    expect((await publicArticle(request, article.slug)).status()).toBe(404);
    expect(await listVersions(request, article.id)).toHaveLength(2);
    expect((await getArticle(request, article.id)).published_at).toBe(article.published_at);
    await expect(page.getByRole("button", { name: "Unpublish" })).toBeDisabled();

    // The draft equals the live snapshot, so publishing again creates nothing new and goes live again.
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "already live" })).toBeVisible();
    expect((await publicArticle(request, article.slug)).status()).toBe(200);
    expect(await listVersions(request, article.id)).toHaveLength(2);
  });
});
