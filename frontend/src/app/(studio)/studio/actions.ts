"use server";

import { headers } from "next/headers";

import type { ActionResult } from "@/features/articles/action-types";
import type {
  ArticleDetail,
  PublishResult,
  VersionDetail,
} from "@/lib/api/types";
import { createApiClient, toProblem, type ApiProblem } from "@/lib/api/server-client";

// Every action reads the Authorization header the browser sent to this app and passes it on.
// The API is the only place that checks it. A 401 is returned as a result; the screen sends the
// browser to /auth/challenge so it asks for the credentials again.
async function api() {
  return createApiClient((await headers()).get("authorization"));
}

function failure(status: number, body: unknown): { ok: false; problem: ReturnType<typeof toProblem> } {
  return { ok: false, problem: toProblem(status, body) };
}

export type CreatedArticle = {
  id: number;
  slug: string;
  published: boolean;
  /** Set when the article was created but publishing was refused. */
  publishProblem?: ApiProblem;
};

/** Create an article from the editor in one step, and publish it right away if asked. */
export async function createArticleDirect(
  input: { title: string; slug: string; body: string; tags: string[] },
  publishNow: boolean,
): Promise<ActionResult<CreatedArticle>> {
  const client = await api();
  const created = await client.POST("/api/v1/articles", { body: input });
  if (!created.data) return failure(created.response.status, created.error);

  const { id, slug, draft_version } = created.data;
  if (!publishNow) return { ok: true, data: { id, slug, published: false } };

  const published = await client.POST("/api/v1/articles/{id}/publish", {
    params: { path: { id } },
    body: { expected_draft_version: draft_version },
  });
  if (published.data) return { ok: true, data: { id, slug, published: true } };
  return {
    ok: true,
    data: { id, slug, published: false, publishProblem: toProblem(published.response.status, published.error) },
  };
}

export async function updateDraft(
  id: number,
  input: { expected_draft_version: number; title: string; body: string; tags: string[] },
): Promise<ActionResult<ArticleDetail>> {
  const { data, error, response } = await (await api()).PATCH("/api/v1/articles/{id}", {
    params: { path: { id } },
    body: input,
  });
  return data ? { ok: true, data } : failure(response.status, error);
}

export async function publishArticle(
  id: number,
  expectedDraftVersion: number,
): Promise<ActionResult<PublishResult>> {
  const { data, error, response } = await (await api()).POST("/api/v1/articles/{id}/publish", {
    params: { path: { id } },
    body: { expected_draft_version: expectedDraftVersion },
  });
  return data ? { ok: true, data } : failure(response.status, error);
}

export async function unpublishArticle(id: number): Promise<ActionResult<ArticleDetail>> {
  const { data, error, response } = await (await api()).POST("/api/v1/articles/{id}/unpublish", {
    params: { path: { id } },
  });
  return data ? { ok: true, data } : failure(response.status, error);
}

export async function getVersion(id: number, n: number): Promise<ActionResult<VersionDetail>> {
  const { data, error, response } = await (await api()).GET("/api/v1/articles/{id}/versions/{n}", {
    params: { path: { id, n } },
  });
  return data ? { ok: true, data } : failure(response.status, error);
}

export async function restoreVersion(
  id: number,
  n: number,
  expectedDraftVersion: number,
): Promise<ActionResult<ArticleDetail>> {
  const { data, error, response } = await (
    await api()
  ).POST("/api/v1/articles/{id}/versions/{n}/restore", {
    params: { path: { id, n } },
    body: { expected_draft_version: expectedDraftVersion },
  });
  return data ? { ok: true, data } : failure(response.status, error);
}

export async function deleteVersion(id: number, n: number): Promise<ActionResult<null>> {
  const { error, response } = await (await api()).DELETE("/api/v1/articles/{id}/versions/{n}", {
    params: { path: { id, n } },
  });
  return response.ok ? { ok: true, data: null } : failure(response.status, error);
}
