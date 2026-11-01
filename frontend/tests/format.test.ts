import { describe, expect, it } from "vitest";

import { parseTags, slugForNewArticle, slugify, stripAddress } from "@/lib/format";

describe("stripAddress", () => {
  it("keeps only the slug when an address is typed or pasted", () => {
    expect(stripAddress("/docs/getting-started")).toBe("getting-started");
    expect(stripAddress("docs/getting-started")).toBe("getting-started");
    expect(stripAddress("https://example.com/docs/getting-started")).toBe("getting-started");
  });

  it("leaves a plain slug alone", () => {
    expect(stripAddress("getting-started")).toBe("getting-started");
    expect(stripAddress("docs-and-more")).toBe("docs-and-more");
  });
});

describe("slugify", () => {
  it("makes lowercase words joined by single hyphens", () => {
    expect(slugify("  Getting  Started: the Basics! ")).toBe("getting-started-the-basics");
  });

  it("returns an empty string when nothing usable is left", () => {
    expect(slugify("!!!")).toBe("");
  });
});

describe("parseTags", () => {
  it("trims, lowercases, drops empties and duplicates, keeping order", () => {
    expect(parseTags(" API , docs,, api ,Guide")).toEqual(["api", "docs", "guide"]);
  });
});

describe("slugForNewArticle", () => {
  const random = () => "x1y2z3";

  it("uses the typed slug first", () => {
    expect(slugForNewArticle("Any title", "/docs/my-slug", random)).toBe("my-slug");
  });

  it("falls back to a slug made from the title", () => {
    expect(slugForNewArticle("Getting Started", "", random)).toBe("getting-started");
  });

  it("falls back to a generated name when the title gives nothing usable", () => {
    expect(slugForNewArticle("\u65e5\u672c\u8a9e\u306e\u8a18\u4e8b", "", random)).toBe("article-x1y2z3");
  });
});
