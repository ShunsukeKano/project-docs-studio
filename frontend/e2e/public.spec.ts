import { expect, test } from "@playwright/test";

import { createArticle, publish, uniqueSlug, updateDraft } from "./helpers";

test.describe("the public site", () => {
  test("lists a published article and opens it", async ({ page, request }) => {
    const slug = uniqueSlug("public");
    const article = await createArticle(request, { title: "Public title", slug, body: "Public **body**", tags: ["e2e"] });
    await publish(request, article.id, 1);

    await page.goto("/docs");
    await page.locator(`a[href="/docs/${slug}"]`).click();
    await expect(page).toHaveURL(new RegExp(`/docs/${slug}$`));
    await expect(page.getByRole("heading", { name: "Public title" })).toBeVisible();
    await expect(page.locator("strong", { hasText: "body" })).toBeVisible();
  });

  test("shows the published text, never the draft", async ({ page, request }) => {
    const slug = uniqueSlug("public");
    const article = await createArticle(request, { title: "Live title", slug, body: "Live text" });
    await publish(request, article.id, 1);
    await updateDraft(request, article.id, 2, { title: "Draft title", body: "Draft text only" });

    await page.goto(`/docs/${slug}`);
    await expect(page.getByText("Live text")).toBeVisible();
    await expect(page.getByText("Draft text only")).toHaveCount(0);
    await expect(page.getByText("Draft title")).toHaveCount(0);
  });

  test("a draft, an unpublished article and a made-up address all give the same 404", async ({ page, request }) => {
    const draft = await createArticle(request, { title: "Only a draft", body: "x" });
    const taken = await createArticle(request, { title: "Taken down", body: "y" });
    await publish(request, taken.id, 1);
    await request.post(`${process.env.E2E_API_URL ?? "http://localhost:18000"}/api/v1/articles/${taken.id}/unpublish`);

    const bodies: string[] = [];
    for (const slug of [draft.slug, taken.slug, "no-such-article-xyz"]) {
      const response = await page.goto(`/docs/${slug}`);
      expect(response?.status()).toBe(404);
      bodies.push(await page.locator("body").innerText());
    }
    expect(new Set(bodies).size).toBe(1);
  });

  test("no page loads anything from another site", async ({ page, request }) => {
    const article = await createArticle(request, { title: "Offsite check", body: "text" });
    await publish(request, article.id, 1);
    const outside: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (!["localhost", "127.0.0.1"].includes(url.hostname) && url.protocol.startsWith("http")) outside.push(r.url());
    });
    for (const path of ["/docs", `/docs/${article.slug}`, "/studio", "/studio/new"]) {
      await page.goto(path);
    }
    expect(outside).toEqual([]);
  });
});
