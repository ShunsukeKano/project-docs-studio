import { expect, test } from "@playwright/test";

import { API, articleCount, getArticle, publicArticle } from "./helpers";

test.describe("writing a new article", () => {
  test("nothing is created until the first save", async ({ page, request }) => {
    const before = await articleCount(request);
    await page.goto("/studio/new");
    await page.locator("#new-title").fill("Not saved yet");
    await page.locator("#new-body").fill("Some text");
    expect(await articleCount(request)).toBe(before);
  });

  test("the slug follows the title until it is edited, and holds only the slug", async ({ page }) => {
    await page.goto("/studio/new");
    await page.locator("#new-title").fill("Hello Brave World");
    await expect(page.locator("#new-slug")).toHaveValue("hello-brave-world");

    await page.locator("#new-slug").fill("/docs/my-own-slug");
    await expect(page.locator("#new-slug")).toHaveValue("my-own-slug");

    await page.locator("#new-title").fill("A different title");
    await expect(page.locator("#new-slug")).toHaveValue("my-own-slug"); // no longer follows the title
  });

  test("the preview renders the Markdown as it is typed", async ({ page }) => {
    await page.goto("/studio/new");
    await page.locator("#new-body").fill("## Preview heading\n\nSome **bold** text");
    const preview = page.getByLabel("Preview");
    await expect(preview.getByRole("heading", { name: "Preview heading" })).toBeVisible();
    await expect(preview.locator("strong")).toHaveText("bold");
  });

  test("Save draft creates a private draft", async ({ page, request }) => {
    await page.goto("/studio/new");
    await page.locator("#new-title").fill("A private draft");
    await page.locator("#new-body").fill("Only for me");
    await page.getByRole("button", { name: "Save draft" }).click();
    await page.waitForURL(/\/studio\/\d+$/);

    const id = Number(page.url().split("/").pop());
    const article = await getArticle(request, id);
    expect(article.status).toBe("draft");
    expect((await publicArticle(request, article.slug)).status()).toBe(404);
  });

  test("Save & publish creates the article and publishes it in one step, and again after an edit", async ({
    page,
    request,
  }) => {
    await page.goto("/studio/new");
    await page.locator("#new-title").fill("Published in one step");
    await page.locator("#new-tags").fill("e2e, one-step");
    await page.locator("#new-body").fill("# Hello from the browser\n\nCreated and published together.");
    await page.getByRole("button", { name: "Save & publish" }).click();
    await page.waitForURL(/\/studio\/\d+$/);

    const id = Number(page.url().split("/").pop());
    let article = await getArticle(request, id);
    expect(article.status).toBe("published");
    expect(article.live_version_number).toBe(1);
    const live = await publicArticle(request, article.slug);
    expect(live.status()).toBe(200);
    expect((await live.json()).body).toContain("Created and published together.");

    // Edit in the editor: the button now says "Save & publish" and publishes the new text as version 2.
    await page.locator("#draft-body").fill("Changed text");
    await expect(page.getByRole("button", { name: "Save & publish" })).toBeVisible();
    await page.getByRole("button", { name: "Save & publish" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Saved and published as version 2" })).toBeVisible();

    article = await getArticle(request, id);
    expect(article.live_version_number).toBe(2);
    expect(((await (await publicArticle(request, article.slug)).json()) as { body: string }).body).toBe("Changed text");
  });

  test("an empty body cannot be published, and the draft is not lost", async ({ page }) => {
    await page.goto("/studio/new");
    await page.locator("#new-title").fill("No body yet");
    await expect(page.getByRole("button", { name: "Save & publish" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Save draft" })).toBeEnabled();
  });

  test("the API address and keys never appear in the page", async ({ page }) => {
    await page.goto("/studio/new");
    const html = await page.content();
    expect(html).not.toContain(API);
    expect(html).not.toContain("ANTHROPIC_API_KEY=sk-");
  });
});
