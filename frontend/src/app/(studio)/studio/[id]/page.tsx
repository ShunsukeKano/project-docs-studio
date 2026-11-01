import { headers } from "next/headers";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ArticleWorkspace } from "@/features/articles/article-workspace";
import { isAiDraftingOn } from "@/lib/api/ai-status";
import { createApiClient } from "@/lib/api/server-client";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export default async function StudioArticlePage({ params }: Props) {
  const { id: rawId } = await params;
  if (!/^[1-9]\d{0,17}$/.test(rawId)) notFound();
  const id = Number(rawId);

  const authorization = (await headers()).get("authorization");
  const api = createApiClient(authorization);
  const [article, versions, aiEnabled] = await Promise.all([
    api.GET("/api/v1/articles/{id}", { params: { path: { id } } }),
    api.GET("/api/v1/articles/{id}/versions", { params: { path: { id } } }),
    isAiDraftingOn(authorization),
  ]);

  if (article.response.status === 401 || versions.response.status === 401) {
    redirect("/auth/challenge");
  }
  if (article.response.status === 404) notFound();
  if (!article.data || !versions.data) throw new Error("The article could not be loaded");

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <Link
          href="/studio"
          className="rounded-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          ← All articles
        </Link>
      </p>
      <ArticleWorkspace article={article.data} versions={versions.data} aiEnabled={aiEnabled} />
    </div>
  );
}
