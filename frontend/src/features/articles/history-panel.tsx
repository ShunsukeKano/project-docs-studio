"use client";

import { useState, useTransition } from "react";

import { getVersion } from "@/app/(studio)/studio/actions";
import { Button } from "@/components/ui/button";
import { TagList } from "@/components/ui/tag";
import type { ArticleStatus, VersionDetail, VersionSummary } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { renderMarkdown } from "@/lib/markdown";

export function HistoryPanel({
  articleId,
  status,
  versions,
  busy,
  onRestore,
  onDelete,
  onUnauthorized,
}: {
  articleId: number;
  status: ArticleStatus;
  versions: VersionSummary[];
  busy: boolean;
  onRestore: (versionNumber: number) => void;
  onDelete: (versionNumber: number) => void;
  onUnauthorized: () => void;
}) {
  const [opened, setOpened] = useState<VersionDetail | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, startLoading] = useTransition();
  // After Unpublish the pointer is kept, so `is_live` stays true; the screen must not call it "Live".
  const articleIsPublished = status === "published";

  function open(versionNumber: number) {
    setMessage(null);
    startLoading(async () => {
      const result = await getVersion(articleId, versionNumber);
      if (result.ok) {
        setOpened(result.data);
      } else if (result.problem.status === 401) {
        onUnauthorized();
      } else {
        setOpened(null);
        setMessage(result.problem.message);
      }
    });
  }

  return (
    <section aria-labelledby="history-heading" className="rounded-xl border border-line bg-surface shadow-card">
      <h2 id="history-heading" className="border-b border-line px-5 py-3 text-base font-semibold">
        Version history
      </h2>
      {versions.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted">
          No versions yet. Each time you publish, a numbered snapshot is saved here.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {versions.map((version) => (
            <li key={version.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  Version {version.version_number}
                  {version.is_live ? (
                    articleIsPublished ? (
                      <span className="ml-2 rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success">
                        Live
                      </span>
                    ) : (
                      <span className="ml-2 rounded-full bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">
                        Last published
                      </span>
                    )
                  ) : null}
                </p>
                <p className="truncate text-xs text-muted">
                  {version.title} · {formatDateTime(version.created_at)}
                </p>
                {version.is_live && !articleIsPublished ? (
                  <p className="text-xs text-muted">
                    The article is taken down. This version is kept, so it cannot be deleted.
                  </p>
                ) : null}
              </div>
              <div className="flex gap-1.5">
                <Button variant="ghost" onClick={() => open(version.version_number)} disabled={loading}>
                  View
                </Button>
                <Button variant="secondary" onClick={() => onRestore(version.version_number)} disabled={busy}>
                  Restore to draft
                </Button>
                <Button
                  variant="danger"
                  onClick={() => onDelete(version.version_number)}
                  disabled={busy || version.is_live}
                  title={
                    version.is_live
                      ? articleIsPublished
                        ? "The live version is protected and cannot be deleted"
                        : "The last published version is kept after Unpublish and cannot be deleted"
                      : undefined
                  }
                >
                  Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {message ? (
        <p role="alert" className="border-t border-line px-5 py-3 text-sm text-danger">
          {message}
        </p>
      ) : null}
      {opened ? (
        <div className="border-t border-line px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-sm font-semibold">
              Version {opened.version_number}: {opened.title}
            </h3>
            <Button variant="ghost" onClick={() => setOpened(null)}>
              Close
            </Button>
          </div>
          <div className="mt-2">
            <TagList tags={opened.tags} />
          </div>
          <div className="prose-docs mt-3 text-sm">{renderMarkdown(opened.body)}</div>
        </div>
      ) : null}
    </section>
  );
}
