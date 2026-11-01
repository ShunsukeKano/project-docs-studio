import { expect, type APIRequestContext } from "@playwright/test";

/** Address of the API of the system under test (the writer login is off in that system). */
export const API = process.env.E2E_API_URL ?? "http://localhost:18000";

/** A slug no other test uses, so tests never depend on each other. */
export const uniqueSlug = (prefix = "e2e") =>
  `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

export type Article = {
  id: number;
  slug: string;
  status: string;
  draft_title: string;
  draft_body: string;
  draft_tags: string[];
  draft_version: number;
  live_version_number: number | null;
  published_at: string | null;
};

export async function createArticle(
  request: APIRequestContext,
  fields: { title: string; body?: string; tags?: string[]; slug?: string },
): Promise<Article> {
  const response = await request.post(`${API}/api/v1/articles`, {
    data: { title: fields.title, slug: fields.slug ?? uniqueSlug(), body: fields.body ?? "", tags: fields.tags ?? [] },
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as Article;
}

export async function getArticle(request: APIRequestContext, id: number): Promise<Article> {
  const response = await request.get(`${API}/api/v1/articles/${id}`);
  expect(response.status()).toBe(200);
  return (await response.json()) as Article;
}

export async function updateDraft(
  request: APIRequestContext,
  id: number,
  expected: number,
  fields: { title?: string; body?: string; tags?: string[] },
) {
  const response = await request.patch(`${API}/api/v1/articles/${id}`, {
    data: { expected_draft_version: expected, ...fields },
  });
  expect(response.status()).toBe(200);
  return (await response.json()) as Article;
}

export async function publish(request: APIRequestContext, id: number, expected: number) {
  const response = await request.post(`${API}/api/v1/articles/${id}/publish`, {
    data: { expected_draft_version: expected },
  });
  expect([200, 201]).toContain(response.status());
  return response.json();
}

export async function listVersions(request: APIRequestContext, id: number) {
  const response = await request.get(`${API}/api/v1/articles/${id}/versions`);
  expect(response.status()).toBe(200);
  return (await response.json()) as { version_number: number; is_live: boolean }[];
}

export async function publicArticle(request: APIRequestContext, slug: string) {
  return request.get(`${API}/api/v1/public/articles/${slug}`);
}

export async function articleCount(request: APIRequestContext): Promise<number> {
  const response = await request.get(`${API}/api/v1/articles?limit=100`);
  return ((await response.json()) as unknown[]).length;
}

/** An article with published versions 1 ("Version one") and 2 ("Version two"); version 2 is live. */
export async function articleWithTwoVersions(request: APIRequestContext): Promise<Article> {
  const article = await createArticle(request, { title: "History test", body: "Version one", tags: ["e2e"] });
  await publish(request, article.id, 1); // draft_version 2
  await updateDraft(request, article.id, 2, { body: "Version two" }); // draft_version 3
  await publish(request, article.id, 3); // version 2 is live, draft_version 4
  return getArticle(request, article.id);
}
