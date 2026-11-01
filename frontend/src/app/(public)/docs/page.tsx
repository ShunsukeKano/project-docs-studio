import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { EmptyState } from "@/components/ui/empty-state";
import { TagList } from "@/components/ui/tag";
import { createApiClient } from "@/lib/api/server-client";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Documentation" };

export default async function DocsPage() {
  const { data, error } = await createApiClient().GET("/api/v1/public/articles", {
    params: { query: { limit: 100 } },
  });
  if (error || !data) throw new Error("The article list could not be loaded");

  return (
    <>
      <section className="relative isolate overflow-hidden rounded-2xl border border-line shadow-card">
        <Image
          src="/images/hero-blue.jpg"
          alt=""
          fill
          priority
          unoptimized
          sizes="(min-width: 768px) 768px, 100vw"
          className="-z-10 object-cover"
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-br from-ink/55 via-ink/25 to-transparent" />
        <div className="p-8 sm:p-10">
          <p className="text-sm font-medium text-white/80">Documentation</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Guides and references
          </h1>
          <p className="mt-3 max-w-xl text-white/85">
            Everything here is a published snapshot, so what you read is exactly what the writers
            signed off.
          </p>
          <p className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-ink">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-success" />
            {data.length} {data.length === 1 ? "article" : "articles"} published
          </p>
        </div>
      </section>

      <div className="mt-8">
        {data.length === 0 ? (
          <EmptyState title="Nothing has been published yet">
            Check back soon: new articles will appear here as soon as they are published.
          </EmptyState>
        ) : (
          <ul className="space-y-3">
            {data.map((article) => (
              <li key={article.slug}>
                <Link
                  href={`/docs/${article.slug}`}
                  className="group block rounded-xl border border-line bg-surface p-5 shadow-card transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lift focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="text-lg font-semibold text-ink group-hover:text-accent">
                      {article.title}
                    </h2>
                    <span aria-hidden className="mt-1 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent">
                      →
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted">
                    Published {formatDate(article.published_at)}
                    {article.updated_at ? <> · Updated {formatDate(article.updated_at)}</> : null}
                  </p>
                  <div className="mt-3">
                    <TagList tags={article.tags} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
