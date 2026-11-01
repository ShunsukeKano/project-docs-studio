import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { TagList } from "@/components/ui/tag";
import { createApiClient } from "@/lib/api/server-client";
import { formatDate } from "@/lib/format";
import { renderMarkdown } from "@/lib/markdown";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

// One request serves both the page and its metadata.
const loadArticle = cache(async (slug: string) => {
  const { data, response } = await createApiClient().GET("/api/v1/public/articles/{slug}", {
    params: { path: { slug } },
  });
  if (response.status === 404) return null;
  if (!data) throw new Error("The article could not be loaded");
  return data;
});

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const article = await loadArticle((await params).slug);
  return article ? { title: article.title } : { title: "Not found" };
}

export default async function ArticlePage({ params }: Props) {
  const article = await loadArticle((await params).slug);
  if (!article) notFound();

  return (
    <article className="rounded-2xl border border-line bg-surface p-6 shadow-card sm:p-10">
      <p className="text-sm">
        <Link
          href="/docs"
          className="rounded-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          ← All articles
        </Link>
      </p>
      <h1 className="mt-5 text-3xl font-bold tracking-tight sm:text-4xl">{article.title}</h1>
      <p className="mt-2 text-sm text-muted">
        Published {formatDate(article.published_at)}
        {article.live_created_at !== article.published_at &&
        formatDate(article.live_created_at) !== formatDate(article.published_at) ? (
          <> · Updated {formatDate(article.live_created_at)}</>
        ) : null}
      </p>
      <div className="mt-3">
        <TagList tags={article.tags} />
      </div>
      <div className="prose-docs mt-8 max-w-[72ch] border-t border-line pt-8">{renderMarkdown(article.body)}</div>
    </article>
  );
}
