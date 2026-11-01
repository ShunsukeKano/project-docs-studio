"use client";

import { useRouter } from "next/navigation";
import { flushSync } from "react-dom";
import { useRef, useState, useTransition } from "react";

import {
  deleteVersion,
  publishArticle,
  restoreVersion,
  unpublishArticle,
  updateDraft,
} from "@/app/(studio)/studio/actions";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ArticleDetail, VersionSummary } from "@/lib/api/types";
import type { ApiProblem } from "@/lib/api/server-client";
import { formatDateTime, parseTags } from "@/lib/format";

import { ConflictView } from "./conflict-view";
import { EditorForm, type DraftFields } from "./editor-form";
import { HistoryPanel } from "./history-panel";

type Notice = { tone: "good" | "bad"; text: string };

// /auth/challenge is a route handler (it sets WWW-Authenticate), so this is a full page load.
function goToChallenge() {
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/auth/challenge";
}

const fieldsOf = (article: ArticleDetail): DraftFields => ({
  title: article.draft_title,
  body: article.draft_body,
  tagsText: article.draft_tags.join(", "),
});

export function ArticleWorkspace({
  article: initial,
  versions,
  aiEnabled,
}: {
  article: ArticleDetail;
  versions: VersionSummary[];
  aiEnabled: boolean;
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  // The last copy the server confirmed. Its draft_version is what every change is based on.
  const [saved, setSaved] = useState(initial);
  const [fields, setFields] = useState<DraftFields>(fieldsOf(initial));
  const [conflict, setConflict] = useState<ApiProblem | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, startWork] = useTransition();

  const dirty =
    fields.title !== saved.draft_title ||
    fields.body !== saved.draft_body ||
    parseTags(fields.tagsText).join("\u0000") !== saved.draft_tags.join("\u0000");

  function adopt(article: ArticleDetail) {
    setSaved(article);
    setFields(fieldsOf(article));
    setConflict(null);
  }

  /** Common handling for a failed call. Returns true when the caller has nothing more to do. */
  function handleProblem(problem: ApiProblem): void {
    if (problem.status === 401) {
      goToChallenge();
    } else if (problem.code === "version_conflict") {
      setConflict(problem);
      setNotice(null);
    } else {
      setNotice({ tone: "bad", text: problem.message });
    }
  }

  function save(expectedVersion: number = saved.draft_version) {
    setNotice(null);
    startWork(async () => {
      const result = await updateDraft(saved.id, {
        expected_draft_version: expectedVersion,
        title: fields.title,
        body: fields.body,
        tags: parseTags(fields.tagsText),
      });
      if (result.ok) {
        adopt(result.data);
        setNotice({ tone: "good", text: "Draft saved." });
      } else {
        handleProblem(result.problem);
      }
    });
  }

  function resubmitAgainstNewVersion() {
    if (!conflict?.currentDraftVersion) return;
    const version = conflict.currentDraftVersion;
    flushSync(() => setConflict(null));
    save(version);
  }

  /** Publish. With unsaved changes it saves the draft first, then publishes what was just saved. */
  function publish() {
    setNotice(null);
    const hadUnsavedChanges = dirty;
    startWork(async () => {
      let base = saved;
      if (hadUnsavedChanges) {
        const saveResult = await updateDraft(saved.id, {
          expected_draft_version: saved.draft_version,
          title: fields.title,
          body: fields.body,
          tags: parseTags(fields.tagsText),
        });
        if (!saveResult.ok) return handleProblem(saveResult.problem);
        adopt(saveResult.data);
        base = saveResult.data;
      }

      const result = await publishArticle(base.id, base.draft_version);
      if (!result.ok) {
        const problem = result.problem;
        if (hadUnsavedChanges && problem.status !== 401 && problem.code !== "version_conflict") {
          // The save went through, so say so: only the publish step failed.
          setNotice({
            tone: "bad",
            text: `Your changes were saved, but publishing failed: ${problem.message}`,
          });
          return;
        }
        return handleProblem(problem);
      }
      const published = result.data;
      setSaved((current) => ({
        ...current,
        status: published.status,
        published_at: published.published_at,
        draft_version: published.draft_version,
        live_version_number: published.version_number,
      }));
      setNotice({
        tone: "good",
        text: published.created
          ? `${hadUnsavedChanges ? "Saved and published" : "Published"} as version ${published.version_number}.`
          : `Nothing changed: version ${published.version_number} is already live.`,
      });
      router.refresh();
    });
  }

  function unpublish() {
    setNotice(null);
    startWork(async () => {
      const result = await unpublishArticle(saved.id);
      if (!result.ok) return handleProblem(result.problem);
      setSaved(result.data);
      setNotice({ tone: "good", text: "Taken down. Every version is kept." });
      router.refresh();
    });
  }

  function restore(versionNumber: number) {
    if (dirty && !window.confirm("Restoring replaces your unsaved changes. Continue?")) return;
    setNotice(null);
    startWork(async () => {
      const result = await restoreVersion(saved.id, versionNumber, saved.draft_version);
      if (!result.ok) return handleProblem(result.problem);
      adopt(result.data);
      setNotice({
        tone: "good",
        text: `Version ${versionNumber} copied into the draft. It is not published.`,
      });
      router.refresh();
    });
  }

  function remove(versionNumber: number) {
    if (!window.confirm(`Delete version ${versionNumber}? This cannot be undone.`)) return;
    setNotice(null);
    startWork(async () => {
      const result = await deleteVersion(saved.id, versionNumber);
      if (!result.ok) return handleProblem(result.problem);
      setNotice({ tone: "good", text: `Version ${versionNumber} deleted.` });
      router.refresh();
    });
  }

  const canPublish = fields.title.trim() !== "" && fields.body.trim() !== "";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-line bg-surface p-5 shadow-card">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold tracking-tight">{saved.draft_title}</h1>
          <p className="mt-1 text-sm text-muted">
            {saved.status === "published" ? (
              <a
                href={`/docs/${saved.slug}`}
                className="text-accent underline underline-offset-2"
                target="_blank"
                rel="noopener noreferrer"
              >
                {saved.slug} ↗
              </a>
            ) : (
              <>{saved.slug}</>
            )}{" "}
            · draft version {saved.draft_version}
            {saved.published_at ? <> · first published {formatDateTime(saved.published_at)}</> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={saved.status} />
          <Button variant="primary" onClick={publish} disabled={busy || !canPublish}>
            {dirty ? "Save & publish" : "Publish"}
          </Button>
          <Button onClick={unpublish} disabled={busy || saved.status !== "published"}>
            Unpublish
          </Button>
        </div>
      </div>

      {dirty ? (
        <p className="text-sm text-muted">
          You have unsaved changes. “Save &amp; publish” saves them and publishes in one step; “Save
          draft” keeps them private.
        </p>
      ) : null}

      <div aria-live="polite">
        {notice ? (
          <p
            role={notice.tone === "bad" ? "alert" : "status"}
            className={`rounded-md px-3 py-2 text-sm ${
              notice.tone === "bad" ? "bg-danger-soft text-danger" : "bg-success-soft text-success"
            }`}
          >
            {notice.text}
          </p>
        ) : null}
      </div>

      {conflict ? (
        <ConflictView
          currentDraftVersion={conflict.currentDraftVersion}
          busy={busy}
          onReload={() => window.location.reload()}
          onResubmit={resubmitAgainstNewVersion}
        />
      ) : null}

      <EditorForm
        fields={fields}
        setFields={setFields}
        dirty={dirty}
        busy={busy}
        formRef={formRef}
        aiEnabled={aiEnabled}
        onSave={() => save()}
      />

      <HistoryPanel
        articleId={saved.id}
        versions={versions}
        busy={busy}
        onRestore={restore}
        onDelete={remove}
        onUnauthorized={goToChallenge}
      />
    </div>
  );
}
