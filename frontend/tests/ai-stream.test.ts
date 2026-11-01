import { describe, expect, it } from "vitest";

import { parseSse } from "@/lib/ai-stream";

const event = (payload: object) => `data: ${JSON.stringify(payload)}\n\n`;

describe("parseSse", () => {
  it("reads several complete events", () => {
    const buffer = event({ type: "delta", text: "Hello" }) + event({ type: "delta", text: " world" });
    const { events, rest } = parseSse(buffer);
    expect(events).toEqual([
      { type: "delta", text: "Hello" },
      { type: "delta", text: " world" },
    ]);
    expect(rest).toBe("");
  });

  it("keeps an unfinished event for the next read", () => {
    const first = parseSse(event({ type: "delta", text: "A" }) + 'data: {"type":"delta","te');
    expect(first.events).toEqual([{ type: "delta", text: "A" }]);

    const second = parseSse(first.rest + 'xt":"B"}\n\n');
    expect(second.events).toEqual([{ type: "delta", text: "B" }]);
    expect(second.rest).toBe("");
  });

  it("reads the done and error events", () => {
    const { events } = parseSse(
      event({ type: "error", code: "ai_unavailable", message: "Cut off." }) + event({ type: "done" }),
    );
    expect(events).toEqual([
      { type: "error", code: "ai_unavailable", message: "Cut off." },
      { type: "done" },
    ]);
  });

  it("skips comments, unknown events and malformed JSON without stopping", () => {
    const buffer =
      ": keep-alive\n\n" +
      event({ type: "mystery" }) +
      "data: {not json}\n\n" +
      event({ type: "delta", text: "still here" });
    expect(parseSse(buffer).events).toEqual([{ type: "delta", text: "still here" }]);
  });

  it("keeps text that contains line breaks and special characters intact", () => {
    const text = "## Title\n\n- one\n- two\n\n`code` and \u65e5\u672c\u8a9e";
    expect(parseSse(event({ type: "delta", text })).events).toEqual([{ type: "delta", text }]);
  });
});
