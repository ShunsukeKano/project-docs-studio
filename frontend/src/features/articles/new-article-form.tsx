"use client";

import { useRouter } from "next/navigation";
import { useDeferredValue, useState, useTransition } from "react";

import { createArticleDirect } from "@/app/(studio)/studio/actions";
import { Button } from "@/components/ui/button";
import { AiGenerateBar } from "./ai-generate-bar";
import { Input, Label } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { parseTags, slugForNewArticle, slugify, stripAddress } from "@/lib/format";
import { renderMarkdown } from "@/lib/markdown";

// A short random part for the fallback slug, made in the browser when the button is pressed.
const randomPart = () => Math.random().toString(36).slice(2, 8);

/**
 * Write a new article directly: nothing exists until "Save draft" or "Save & publish" is pressed.
 * The slug follows the title until it is edited by hand, because it cannot be changed later.
 */
export function NewArticleForm({ aiEnabled }: { aiEnabled: boolean }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [body, setBody] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, startWork] = useTransition();
  // The preview follows the text with a deferred render, so typing is never blocked.
  const deferredBody = useDeferredValue(body);

  function submit(publishNow: boolean) {
    setMessage(null);
    startWork(async () => {
      const result = await createArticleDirect(
        {
          title,
          slug: slugForNewArticle(title, slug, randomPart),
          body,
          tags: parseTags(tagsText),
        },
        publishNow,
      );
      if (!result.ok) {
        if (result.problem.status === 401) {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = "/auth/challenge";
        } else {
          setMessage(
            result.problem.code === "validation_error"
              ? "Please give a title (up to 200 characters) and check the slug: lowercase letters, digits and single hyphens."
              : result.problem.message,
          );
        }
        return;
      }
      if (publishNow && !result.data.published) {
        setMessage(
          `The draft was saved, but publishing failed: ${result.data.publishProblem?.message ?? "please try again"}. Opening the draft…`,
        );
      }
      router.push(`/studio/${result.data.id}`);
    });
  }

  const canSubmit = title.trim() !== "" && !busy;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) submit(false);
      }}
      className="space-y-4 rounded-xl border border-line bg-surface p-5 shadow-card"
    >
      <div>
        <Label htmlFor="new-title">Title</Label>
        <Input
          id="new-title"
          required
          autoFocus
          maxLength={200}
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
            if (!slugEdited) setSlug(slugify(event.target.value));
          }}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="new-slug" hint="the address; cannot be changed after saving">
            Slug
          </Label>
          <Input
            id="new-slug"
            maxLength={100}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            placeholder="made from the title"
            value={slug}
            onChange={(event) => {
              setSlug(stripAddress(event.target.value));
              setSlugEdited(true);
            }}
          />
        </div>
        <div>
          <Label htmlFor="new-tags" hint="comma separated, up to 10">
            Tags
          </Label>
          <Input id="new-tags" value={tagsText} onChange={(event) => setTagsText(event.target.value)} />
        </div>
      </div>

      <AiGenerateBar
        enabled={aiEnabled}
        title={title}
        tags={parseTags(tagsText)}
        body={body}
        onText={setBody}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <Label htmlFor="new-body" hint="Markdown">
            Body
          </Label>
          <Textarea
            id="new-body"
            rows={18}
            className="h-[30rem] resize-none"
            maxLength={100000}
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </div>
        <div>
          <p className="mb-1 text-sm font-medium">Preview</p>
          <div
            className="prose-docs h-[30rem] overflow-y-auto rounded-md border border-line bg-canvas p-4 text-sm"
            aria-label="Preview"
          >
            {deferredBody.trim() ? (
              renderMarkdown(deferredBody)
            ) : (
              <p className="text-faint">Nothing to preview yet.</p>
            )}
          </div>
        </div>
      </div>

      {message ? (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
          {message}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={!canSubmit}>
          {busy ? "Saving…" : "Save draft"}
        </Button>
        <Button
          variant="primary"
          onClick={() => submit(true)}
          disabled={!canSubmit || body.trim() === ""}
          title={body.trim() === "" ? "Write a body before publishing" : undefined}
        >
          Save &amp; publish
        </Button>
        <span className="text-sm text-muted">Nothing is created until you save.</span>
      </div>
    </form>
  );
}
