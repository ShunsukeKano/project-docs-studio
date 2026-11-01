import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { buttonClasses } from "@/components/ui/button";
import { createApiClient } from "@/lib/api/server-client";
import { formatDateTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function StudioPage() {
  const authorization = (await headers()).get("authorization");
  const { data, response } = await createApiClient(authorization).GET("/api/v1/articles", {
    params: { query: { limit: 100 } },
  });
  if (response.status === 401) redirect("/auth/challenge");
  if (!data) throw new Error("The article list could not be loaded");

  const count = (status: string) => data.filter((article) => article.status === status).length;

  return (
    <div className="space-y-8">
      <div>
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Your articles</h1>
          <Link href="/studio/new" className={buttonClasses("primary")}>
            + New article
          </Link>
        </div>
          <p className="mt-1 text-sm text-muted">
            Edit freely: nothing is public until you publish it, and readers always see the last
            published version.
          </p>
          <dl className="mt-4 grid grid-cols-3 gap-3 sm:max-w-md">
            {[
              ["Published", count("published")],
              ["Drafts", count("draft")],
              ["Unpublished", count("unpublished")],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <section aria-labelledby="articles-heading">
        <h2 id="articles-heading" className="text-base font-semibold">
          All articles
        </h2>
        <div className="mt-3">
          {data.length === 0 ? (
            <EmptyState title="No articles yet">
              Press “New article” to write your first draft. Nothing is public until you publish it.
            </EmptyState>
          ) : (
            <ul className="space-y-2">
              {data.map((article) => (
                <li key={article.id}>
                  <Link
                    href={`/studio/${article.id}`}
                    className="group flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-5 py-4 shadow-card transition hover:border-accent/40 hover:shadow-lift focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-ink group-hover:text-accent">{article.title}</p>
                      <p className="truncate text-sm text-muted">
                        {article.slug} · changed {formatDateTime(article.updated_at)}
                      </p>
                    </div>
                    <StatusBadge status={article.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
