"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { streamAiDraft } from "@/lib/ai-stream";

/**
 * Optional extra: one button that asks the AI to write the body from the title, tags and notes
 * already entered, and shows it as it is written. It is always shown; when the feature is off it is
 * disabled and says how to turn it on. The text only fills the body field (unsaved): nothing is saved
 * or published from here. The title and tags are never changed.
 */
export function AiGenerateBar({
  enabled,
  title,
  tags,
  body,
  onText,
}: {
  enabled: boolean;
  title: string;
  tags: string[];
  body: string;
  onText: (text: string) => void;
}) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "good" | "bad"; text: string } | null>(null);
  const abort = useRef<AbortController | null>(null);

  const hasBody = body.trim() !== "";
  const canGenerate = enabled && !busy && title.trim() !== "";

  async function generate() {
    if (hasBody && !window.confirm("Replace the body with an AI draft? Your current text is used as notes.")) {
      return;
    }
    setMessage(null);
    setBusy(true);
    const controller = new AbortController();
    abort.current = controller;

    // The current body goes to the model as notes; the field is replaced only once text arrives.
    const result = await streamAiDraft({ title, tags, notes: body, instructions }, onText, controller.signal);

    abort.current = null;
    setBusy(false);
    switch (result.kind) {
      case "done":
        setMessage({
          tone: "good",
          text: "AI draft loaded into the body. It is a proposal: read it, check the facts and edit it. Nothing has been saved.",
        });
        break;
      case "stopped":
        setMessage({ tone: "good", text: "Stopped. What had arrived was kept in the body. Nothing has been saved." });
        break;
      case "cut":
        setMessage({ tone: "bad", text: `${result.message} The text that had arrived was kept in the body.` });
        break;
      case "failed": {
        const { problem } = result;
        if (problem.status === 401) {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = "/auth/challenge";
          return;
        }
        setMessage({
          tone: "bad",
          text:
            problem.code === "validation_error"
              ? "The title (up to 200 characters), notes (5,000) or instructions (1,000) are too long, or the title is empty."
              : problem.message,
        });
        break;
      }
    }
  }

  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center gap-2">
        {busy ? (
          <Button variant="danger" onClick={() => abort.current?.abort()}>
            ■ Stop
          </Button>
        ) : (
          <Button variant="secondary" onClick={() => void generate()} disabled={!canGenerate}>
            ✨ Generate with AI
          </Button>
        )}
        {enabled ? (
          <Input
            aria-label="Instructions for the AI (optional)"
            className="min-w-48 flex-1"
            maxLength={1000}
            placeholder="Optional: tone, audience, length"
            value={instructions}
            disabled={busy}
            onChange={(event) => setInstructions(event.target.value)}
          />
        ) : null}
      </div>
      <p className="mt-2 text-xs text-muted" aria-live="polite">
        {!enabled
          ? "AI drafting is off. To turn it on, set AI_ENABLED=true and your ANTHROPIC_API_KEY in .env, then restart."
          : busy
            ? "Writing… the text appears in the body as it is written. Press Stop to keep what has arrived."
            : title.trim() === ""
              ? "Enter a title first. The AI writes the body from your title, tags and notes; you review it before saving."
              : "Writes the body from your title, tags and notes. AI text can contain mistakes: review it before you publish."}
      </p>
      {message ? (
        <p
          role={message.tone === "bad" ? "alert" : "status"}
          className={`mt-2 rounded-md px-3 py-2 text-sm ${
            message.tone === "bad" ? "bg-danger-soft text-danger" : "bg-success-soft text-success"
          }`}
        >
          {message.text}
        </p>
      ) : null}
    </div>
  );
}
