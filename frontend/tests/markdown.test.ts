import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { renderMarkdown } from "@/lib/markdown";

const html = (source: string) => renderToStaticMarkup(renderMarkdown(source));

describe("renderMarkdown", () => {
  it("renders plain Markdown", () => {
    const out = html("# Title\n\nSome **bold** text and a list:\n\n- one\n- two");
    expect(out).toContain("<h1>Title</h1>");
    expect(out).toContain("<strong>bold</strong>");
    expect(out).toContain("<li>one</li>");
  });

  it("keeps http, https and mailto links", () => {
    const out = html(
      "[a](http://example.com) [b](https://example.com/x) [c](mailto:someone@example.com)",
    );
    expect(out).toContain('href="http://example.com"');
    expect(out).toContain('href="https://example.com/x"');
    expect(out).toContain('href="mailto:someone@example.com"');
  });

  it("removes a javascript: link", () => {
    const out = html("[click](javascript:alert(1))");
    expect(out).not.toContain("javascript:");
    expect(out).toContain("click");
  });

  it("removes other schemes, including data: and vbscript:", () => {
    expect(html("[x](data:text/html;base64,PHNjcmlwdD4=)")).not.toContain("data:");
    expect(html("[x](vbscript:msgbox(1))")).not.toContain("vbscript:");
    expect(html("[x](JaVaScRiPt:alert(1))").toLowerCase()).not.toContain("javascript:");
  });

  it("does not render a raw script element", () => {
    const out = html("Hello <script>alert(1)</script> world");
    expect(out).not.toContain("<script");
    expect(out).toContain("Hello");
  });

  it("does not render raw HTML elements or event handlers", () => {
    const out = html('<img src="x" onerror="alert(1)"> <a href="https://e.com" onclick="x()">t</a>');
    expect(out).not.toContain("<img");
    expect(out).not.toContain("onerror");
    expect(out).not.toContain("onclick");
  });

  it("does not render images from Markdown (no tracking pixels)", () => {
    const out = html("![alt text](https://tracker.example/pixel.png)");
    expect(out).not.toContain("<img");
    expect(out).not.toContain("tracker.example");
  });

  it("opens no link in a way that leaks the opener", () => {
    const out = html("[a](https://example.com)");
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it("renders an empty string as nothing", () => {
    expect(html("")).toBe("");
  });
});
