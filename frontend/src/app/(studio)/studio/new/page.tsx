import { headers } from "next/headers";
import Link from "next/link";

import { NewArticleForm } from "@/features/articles/new-article-form";
import { isAiDraftingOn } from "@/lib/api/ai-status";

export const dynamic = "force-dynamic";

export default async function NewArticlePage() {
  const aiEnabled = await isAiDraftingOn((await headers()).get("authorization"));
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
      <h1 className="text-2xl font-bold tracking-tight">New article</h1>
      <NewArticleForm aiEnabled={aiEnabled} />
    </div>
  );
}
