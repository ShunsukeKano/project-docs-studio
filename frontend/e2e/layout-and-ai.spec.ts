import { expect, test } from "@playwright/test";

import { API, articleWithTwoVersions } from "./helpers";

test.describe("layout", () => {
  test("Body and Preview have the same height and top, in both editors", async ({ page, request }) => {
    await page.goto("/studio/new");
    await page.locator("#new-body").fill(Array.from({ length: 60 }, (_, i) => `## Heading ${i}\n\nText ${i}`).join("\n\n"));
    const body = (await page.locator("#new-body").boundingBox())!;
    const preview = (await page.getByLabel("Preview").boundingBox())!;
    expect(Math.abs(body.height - preview.height)).toBeLessThan(1);
    expect(Math.abs(body.y - preview.y)).toBeLessThan(1);

    const article = await articleWithTwoVersions(request);
    await page.goto(`/studio/${article.id}`);
    const body2 = (await page.locator("#draft-body").boundingBox())!;
    const preview2 = (await page.getByLabel("Preview").boundingBox())!;
    expect(Math.abs(body2.height - preview2.height)).toBeLessThan(1);
  });

  test("the public page and the editor use the same content width", async ({ page, request }) => {
    const article = await articleWithTwoVersions(request);
    await page.goto(`/docs/${article.slug}`);
    const publicWidth = (await page.locator("main").boundingBox())!.width;
    await page.goto(`/studio/${article.id}`);
    const studioWidth = (await page.locator("main").boundingBox())!.width;
    expect(Math.abs(publicWidth - studioWidth)).toBeLessThan(1);
  });
});

test.describe("the optional AI extra", () => {
  test("the button is always visible; with the feature off it is disabled and says how to turn it on", async ({
    page,
    request,
  }) => {
    const status = (await (await request.get(`${API}/api/v1/ai/status`)).json()) as { enabled: boolean };
    expect(status.enabled).toBe(false); // the throwaway system forces it off, so no test can reach the real model

    await page.goto("/studio/new");
    const button = page.getByRole("button", { name: /Generate with AI/ });
    await expect(button).toBeVisible();
    await expect(button).toBeDisabled();
    await page.locator("#new-title").fill("A title");
    await expect(button).toBeDisabled(); // still off, whatever is typed
    await expect(page.getByText(/AI drafting is off\. To turn it on, set AI_ENABLED=true/)).toBeVisible();
  });
});
