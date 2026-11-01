import { toProblem, type ApiProblem } from "@/lib/api/problem";

export type StreamEvent =
  | { type: "delta"; text: string }
  | { type: "done" }
  | { type: "error"; code: string; message: string };

/**
 * Split a buffer of server-sent events into complete events and the unfinished rest.
 * An event is a `data: {json}` line ended by a blank line; anything else is ignored.
 */
export function parseSse(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    const line = block.split("\n").find((l) => l.startsWith("data: "));
    if (!line) continue;
    try {
      const parsed = JSON.parse(line.slice("data: ".length)) as StreamEvent;
      if (parsed.type === "delta" || parsed.type === "done" || parsed.type === "error") {
        events.push(parsed);
      }
    } catch {
      // A malformed event is skipped rather than breaking the whole stream.
    }
  }
  return { events, rest };
}

export type AiStreamResult =
  | { kind: "done"; text: string }
  /** The writer pressed Stop: what arrived is kept. */
  | { kind: "stopped"; text: string }
  /** The stream broke after some text arrived: that text is kept. */
  | { kind: "cut"; text: string; message: string }
  /** Nothing arrived: the request was refused or failed at the start. */
  | { kind: "failed"; problem: ApiProblem };

/**
 * Ask for a body and report it as it arrives. `onText` gets the whole text so far each time a piece
 * comes in. The request goes to this app's own route, which forwards the sign-in and the stream.
 */
export async function streamAiDraft(
  input: { title: string; tags: string[]; notes: string; instructions: string },
  onText: (textSoFar: string) => void,
  signal: AbortSignal,
): Promise<AiStreamResult> {
  let text = "";
  try {
    const response = await fetch("/studio/ai-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: input.title,
        tags: input.tags,
        notes: input.notes,
        instructions: input.instructions.trim() === "" ? null : input.instructions,
      }),
      signal,
    });
    if (!response.ok || !response.body) {
      const body: unknown = await response.json().catch(() => null);
      return { kind: "failed", problem: toProblem(response.status, body) };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSse(buffer);
      buffer = parsed.rest;
      for (const event of parsed.events) {
        if (event.type === "delta") {
          text += event.text;
          onText(text);
        } else if (event.type === "error") {
          return text === ""
            ? { kind: "failed", problem: toProblem(502, { error: event }) }
            : { kind: "cut", text, message: event.message };
        }
      }
    }
    return { kind: "done", text };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return { kind: "stopped", text };
    }
    return text === ""
      ? { kind: "failed", problem: toProblem(502, null) }
      : { kind: "cut", text, message: "The connection was lost." };
  }
}
