"use client";

import { useDeferredValue, type Dispatch, type FormEvent, type Ref, type SetStateAction } from "react";

import { Button } from "@/components/ui/button";
import { parseTags } from "@/lib/format";
import { AiGenerateBar } from "./ai-generate-bar";
import { Input, Label } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { renderMarkdown } from "@/lib/markdown";

export type DraftFields = { title: string; body: string; tagsText: string };

export function EditorForm({
  fields,
  setFields,
  dirty,
  busy,
  formRef,
  aiEnabled,
  onSave,
}: {
  fields: DraftFields;
  setFields: Dispatch<SetStateAction<DraftFields>>;
  dirty: boolean;
  busy: boolean;
  formRef: Ref<HTMLFormElement>;
  aiEnabled: boolean;
  onSave: () => void;
}) {
  // The preview follows the text with a deferred render, so typing is never blocked.
  const deferredBody = useDeferredValue(fields.body);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave();
  }

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      className="space-y-4 rounded-xl border border-line bg-surface p-5 shadow-card"
    >
      <div>
        <Label htmlFor="draft-title">Title</Label>
        <Input
          id="draft-title"
          required
          maxLength={200}
          value={fields.title}
          onChange={(event) => setFields((current) => ({ ...current, title: event.target.value }))}
        />
      </div>
      <div>
        <Label htmlFor="draft-tags" hint="comma separated, up to 10">
          Tags
        </Label>
        <Input
          id="draft-tags"
          value={fields.tagsText}
          onChange={(event) => setFields((current) => ({ ...current, tagsText: event.target.value }))}
        />
      </div>
      <AiGenerateBar
        enabled={aiEnabled}
        title={fields.title}
        tags={parseTags(fields.tagsText)}
        body={fields.body}
        onText={(text) => setFields((current) => ({ ...current, body: text }))}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <Label htmlFor="draft-body" hint="Markdown">
            Body
          </Label>
          <Textarea
            id="draft-body"
            rows={18}
            className="h-[30rem] resize-none"
            maxLength={100000}
            value={fields.body}
            onChange={(event) => setFields((current) => ({ ...current, body: event.target.value }))}
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
      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={busy || !dirty}>
          {busy ? "Saving…" : "Save draft"}
        </Button>
        <span className="text-sm text-muted" aria-live="polite">
          {dirty ? "Unsaved changes" : "All changes saved"}
        </span>
      </div>
    </form>
  );
}
